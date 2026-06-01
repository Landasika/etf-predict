"""
MACD Histogram Momentum Backtester

Pure execution engine. Reads df['target_position'] column and executes trades.
Does NOT depend on the signal generator internals — only needs target_position.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
from core import database


class MACDHistogramMomentumBacktester:
    """Target-position-driven backtester for histogram momentum strategy"""

    def __init__(self, initial_capital: float = 2000, num_positions: int = 10,
                 sell_fee: float = 0.005, stop_loss_pct: float = 0.10,
                 take_profit_pct1: float = 0.10, take_profit_pct2: float = 0.20):
        self.initial_capital = initial_capital
        self.num_positions = num_positions
        self.position_size = initial_capital / num_positions
        self.sell_fee = sell_fee
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct1 = take_profit_pct1
        self.take_profit_pct2 = take_profit_pct2

    def run_backtest(self, etf_code: str, start_date: str = None,
                     end_date: str = None, signal_params: dict = None) -> Dict:
        data = self._load_data(etf_code, start_date, end_date)
        if data is None or len(data) == 0:
            return {'success': False, 'message': '无数据', 'data': None}

        from .macd_histogram_momentum import MACDHistogramMomentumSignalGenerator
        signal_gen = MACDHistogramMomentumSignalGenerator(signal_params)
        data = signal_gen.generate_signals(data)

        # Shift target_position by 1 to avoid look-ahead bias
        data['target_position'] = data['target_position'].shift(1).fillna(0).astype(int)

        trades, performance = self._execute_trades(data)
        metrics = self._calculate_metrics(trades, performance, data)

        return {
            'success': True,
            'trades': trades,
            'performance': performance,
            'metrics': metrics,
        }

    def _load_data(self, etf_code: str, start_date: str = None,
                   end_date: str = None) -> pd.DataFrame:
        data = database.get_etf_daily_data(ts_code=etf_code, start_date=start_date,
                                           end_date=end_date)
        if data is None or len(data) == 0:
            return None
        if isinstance(data, list):
            data = pd.DataFrame(data)
        if 'trade_date' in data.columns:
            data = data.rename(columns={'trade_date': 'date'})
        elif 'cal_date' in data.columns:
            data = data.rename(columns={'cal_date': 'date'})

        required_cols = ['date', 'open', 'high', 'low', 'close', 'vol']
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"Missing required column: {col}")

        data = data.sort_values('date').reset_index(drop=True)
        data = data.dropna(subset=['close']).reset_index(drop=True)
        return data

    def _execute_trades(self, data: pd.DataFrame) -> Tuple[List[Dict], pd.DataFrame]:
        cash = self.initial_capital
        position_shares = 0
        avg_cost = 0
        positions_used = 0
        trades = []
        performance_records = []

        take_profit1_triggered = False
        take_profit2_triggered = False

        for idx, row in data.iterrows():
            price = row['close']
            target = int(row['target_position'])

            if position_shares > 0 and avg_cost > 0:
                pnl_pct = (price - avg_cost) / avg_cost
            else:
                pnl_pct = 0

            # Priority 1: Stop loss
            if position_shares > 0 and pnl_pct <= -self.stop_loss_pct:
                proceeds = position_shares * price * (1 - self.sell_fee)
                cash += proceeds
                trades.append({
                    'date': row['date'], 'type': 'SELL', 'price': price,
                    'shares': position_shares, 'value': proceeds,
                    'reason': 'STOP_LOSS', 'positions_closed': positions_used,
                    'pnl': proceeds - position_shares * avg_cost,
                })
                position_shares = 0
                avg_cost = 0
                positions_used = 0
                take_profit1_triggered = False
                take_profit2_triggered = False
                self._record(performance_records, row, cash, position_shares,
                             positions_used, avg_cost, target)
                continue

            # Priority 2: Take profit
            if position_shares > 0:
                if not take_profit2_triggered and pnl_pct >= self.take_profit_pct2:
                    positions_to_close = max(1, int(positions_used * 0.3))
                    shares_to_sell = int(position_shares * (positions_to_close / positions_used))
                    proceeds = shares_to_sell * price * (1 - self.sell_fee)
                    cash += proceeds
                    position_shares -= shares_to_sell
                    positions_used -= positions_to_close
                    trades.append({
                        'date': row['date'], 'type': 'SELL', 'price': price,
                        'shares': shares_to_sell, 'value': proceeds,
                        'reason': 'TAKE_PROFIT_2',
                        'positions_closed': positions_to_close,
                        'pnl': proceeds - shares_to_sell * avg_cost,
                    })
                    take_profit2_triggered = True
                    self._record(performance_records, row, cash, position_shares,
                                 positions_used, avg_cost, target)
                    continue

                if not take_profit1_triggered and pnl_pct >= self.take_profit_pct1:
                    positions_to_close = max(1, int(positions_used * 0.3))
                    shares_to_sell = int(position_shares * (positions_to_close / positions_used))
                    proceeds = shares_to_sell * price * (1 - self.sell_fee)
                    cash += proceeds
                    position_shares -= shares_to_sell
                    positions_used -= positions_to_close
                    trades.append({
                        'date': row['date'], 'type': 'SELL', 'price': price,
                        'shares': shares_to_sell, 'value': proceeds,
                        'reason': 'TAKE_PROFIT_1',
                        'positions_closed': positions_to_close,
                        'pnl': proceeds - shares_to_sell * avg_cost,
                    })
                    take_profit1_triggered = True

            # Priority 3: Target position driven
            if target > positions_used:
                positions_to_add = target - positions_used
                investment = positions_to_add * self.position_size
                if cash >= investment and price > 0:
                    shares = int(investment // price)
                    if shares > 0:
                        cost = shares * price
                        cash -= cost
                        total_cost = avg_cost * position_shares + cost
                        position_shares += shares
                        avg_cost = total_cost / position_shares
                        positions_used += positions_to_add
                        trades.append({
                            'date': row['date'], 'type': 'BUY', 'price': price,
                            'shares': shares, 'value': cost,
                            'reason': 'TARGET_UP', 'positions_added': positions_to_add,
                        })
                        take_profit1_triggered = False
                        take_profit2_triggered = False

            elif target < positions_used:
                positions_to_close = positions_used - target
                shares_to_sell = int(position_shares * (positions_to_close / positions_used))
                if shares_to_sell > 0:
                    proceeds = shares_to_sell * price * (1 - self.sell_fee)
                    cash += proceeds
                    position_shares -= shares_to_sell
                    positions_used -= positions_to_close
                    trades.append({
                        'date': row['date'], 'type': 'SELL', 'price': price,
                        'shares': shares_to_sell, 'value': proceeds,
                        'reason': 'TARGET_DOWN',
                        'positions_closed': positions_to_close,
                        'pnl': proceeds - shares_to_sell * avg_cost,
                    })
                    if positions_used == 0:
                        avg_cost = 0
                        take_profit1_triggered = False
                        take_profit2_triggered = False

            self._record(performance_records, row, cash, position_shares,
                         positions_used, avg_cost, target)

        return trades, pd.DataFrame(performance_records)

    def _record(self, records, row, cash, shares, positions_used, avg_cost, target):
        position_value = shares * row['close'] if shares > 0 else 0
        records.append({
            'date': row['date'],
            'cash': cash,
            'position_shares': shares,
            'positions_used': positions_used,
            'avg_cost': avg_cost,
            'portfolio_value': cash + position_value,
            'price': row['close'],
            'target_position': target,
            'vol': row.get('vol', 0),
        })

    def _calculate_metrics(self, trades: List[Dict], performance: pd.DataFrame,
                           data: pd.DataFrame) -> Dict:
        if len(performance) == 0:
            return self._empty_metrics()

        final_value = performance['portfolio_value'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital

        buy_hold_return = ((data['close'].iloc[-1] - data['close'].iloc[0]) /
                           data['close'].iloc[0]) if len(data) > 0 else 0

        returns = performance['portfolio_value'].pct_change().dropna()
        sharpe = (np.sqrt(252) * returns.mean() / returns.std()
                  if len(returns) > 0 and returns.std() > 0 else 0)

        cummax = performance['portfolio_value'].cummax()
        drawdown = (performance['portfolio_value'] - cummax) / cummax
        max_drawdown = drawdown.min()

        total_exits = 0
        profitable_exits = 0
        position_entries = []
        for t in trades:
            if t['type'] == 'BUY':
                position_entries.append(t)
            elif t['type'] == 'SELL' and position_entries:
                entry = position_entries.pop(0)
                if t['price'] * (1 - self.sell_fee) > entry['price']:
                    profitable_exits += 1
                total_exits += 1
        win_rate = profitable_exits / total_exits if total_exits else 0

        buy_trades = [t for t in trades if t['type'] == 'BUY']
        sell_trades = [t for t in trades if t['type'] == 'SELL']
        stop_loss_count = len([t for t in sell_trades if t.get('reason') == 'STOP_LOSS'])
        take_profit_count = len([t for t in sell_trades if 'TAKE_PROFIT' in t.get('reason', '')])

        return {
            'initial_capital': self.initial_capital,
            'final_capital': final_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'buy_hold_return_pct': buy_hold_return * 100,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'win_rate': win_rate,
            'win_rate_pct': win_rate * 100,
            'total_trades': len(trades),
            'buy_signals': len(buy_trades),
            'sell_signals': len(sell_trades),
            'stop_loss_count': stop_loss_count,
            'take_profit_count': take_profit_count,
        }

    def _empty_metrics(self) -> Dict:
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.initial_capital,
            'total_return': 0,
            'total_return_pct': 0,
            'buy_hold_return_pct': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'max_drawdown_pct': 0,
            'win_rate': 0,
            'win_rate_pct': 0,
            'total_trades': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'stop_loss_count': 0,
            'take_profit_count': 0,
        }
