"""
MACD Strategy Backtesting Engine

Reuses the existing backtester architecture with MACD-based signals.
Supports:
- MACDSignalGenerator: Standard MACD aggressive strategy
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import database
from .signals import MACDSignalGenerator


class MACDBacktester:
    """MACD strategy specialized backtesting engine"""

    def __init__(self, initial_capital: float = 2000, sell_fee: float = 0.005,
                 num_positions: int = 10, stop_loss_pct: float = 0.10,
                 take_profit_pct1: float = 0.15, take_profit_pct2: float = 0.30,
                 take_profit_pct3: float = 0.35,
                 enable_trailing_stop: bool = False,
                 trailing_stop_pct: float = 0.05,
                 trailing_stop_activation: float = 0.15):
        """
        Initialize backtester with optimized T-trading parameters.

        Args:
            initial_capital: Starting capital (default ¥2,000)
            sell_fee: Transaction fee on sell (default 0.5%)
            num_positions: Number of position slots (default 10)
            stop_loss_pct: Stop loss percentage (default 10%)
            take_profit_pct1: First take profit level (default 15%)
            take_profit_pct2: Second take profit level (default 30%)
            take_profit_pct3: Third take profit level (default 35%)
            enable_trailing_stop: Enable trailing stop profit
            trailing_stop_pct: Trailing stop percentage (default 5%)
            trailing_stop_activation: Activation profit for trailing stop (default 15%)
        """
        self.initial_capital = initial_capital
        self.sell_fee = sell_fee
        self.buy_fee = 0.0
        self.num_positions = num_positions
        self.position_size = initial_capital / num_positions  # Each position = ¥200
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct1 = take_profit_pct1  # Sell 30% at level 1
        self.take_profit_pct2 = take_profit_pct2  # Sell 30% at level 2
        self.take_profit_pct3 = take_profit_pct3  # Sell 40% at level 3

        # 追踪止盈参数
        self.enable_trailing_stop = enable_trailing_stop
        self.trailing_stop_pct = trailing_stop_pct
        self.trailing_stop_activation = trailing_stop_activation

        self.signal_generator = MACDSignalGenerator()
        self.strategy_type = 'macd'  # Track strategy type

    def run_backtest(self, etf_code: str, strategy_params: Dict = None,
                     start_date: str = None, end_date: str = None) -> Dict:
        """
        Run MACD strategy backtest

        Args:
            etf_code: ETF code (e.g., '510330.SH')
            strategy_params: Strategy parameter configuration
            start_date: Start date (YYYYMMDD format)
            end_date: End date (YYYYMMDD format)

        Returns:
            Backtest results dictionary with trades, performance, and metrics
        """
        # Initialize signal generator (only MACD aggressive strategy)
        self.signal_generator = MACDSignalGenerator(strategy_params)
        self.strategy_type = 'macd'

        # Load price data
        data = self._load_data(etf_code, start_date, end_date)

        if data is None or len(data) == 0:
            raise ValueError(f"No data available for {etf_code} in date range")

        # Generate signals
        data = self.signal_generator.generate_signals(data)

        # Convert signal_type to numeric signal_strength for trading logic
        data = self._convert_signals_to_strength(data)

        # Execute trades (reuses existing logic)
        trades, performance = self._execute_trades(data)

        # Calculate metrics
        metrics = self._calculate_metrics(trades, performance, data)

        return {
            'trades': trades,
            'performance': performance.to_dict('records') if isinstance(performance, pd.DataFrame) else performance,
            'metrics': metrics,
            'strategy_params': strategy_params or self.signal_generator.params
        }

    def _load_data(self, etf_code: str, start_date: str = None,
                   end_date: str = None) -> pd.DataFrame:
        """
        Load ETF price data from database

        Args:
            etf_code: ETF code
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)

        Returns:
            DataFrame with OHLCV data
        """
        # Load from ETF database
        data = database.get_etf_daily_data(
            ts_code=etf_code,
            start_date=start_date,
            end_date=end_date
        )

        if data is None or len(data) == 0:
            return None

        # Convert list to DataFrame if needed
        if isinstance(data, list):
            data = pd.DataFrame(data)

        # Standardize column names
        if 'trade_date' in data.columns:
            data = data.rename(columns={'trade_date': 'date'})
        elif 'cal_date' in data.columns:
            data = data.rename(columns={'cal_date': 'date'})

        # Ensure required columns exist
        required_cols = ['date', 'open', 'high', 'low', 'close', 'vol']
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"Missing required column: {col}")

        # Sort by date
        data = data.sort_values('date').reset_index(drop=True)

        # Drop rows with NaN in critical columns
        data = data.dropna(subset=['close']).reset_index(drop=True)

        return data

    def _convert_signals_to_strength(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Convert signal_type to numeric signal_strength for trading logic

        For MACD strategy:
        - BUY signals: Use signal_strength from generator (6-10)
        - SELL signals: Use signal_strength from generator (-6 to -10)
        - HOLD: 0
        """
        data['trading_strength'] = 0

        # 标准 MACD 策略
        buy_mask = data['signal_type'] == 'BUY'
        data.loc[buy_mask, 'trading_strength'] = data.loc[buy_mask, 'signal_strength']

        sell_mask = data['signal_type'] == 'SELL'
        data.loc[sell_mask, 'trading_strength'] = data.loc[sell_mask, 'signal_strength']

        # IMPORTANT: Shift signals by 1 day to avoid look-ahead bias
        # Use T-1 day's signal to trade on T day (realistic trading scenario)
        # This prevents using future data in backtesting
        data['trading_strength'] = data['trading_strength'].shift(1)

        # Replace signal_strength with trading_strength for compatibility
        data['signal_strength'] = data['trading_strength']

        return data

    def _execute_trades(self, data: pd.DataFrame) -> Tuple[List[Dict], pd.DataFrame]:
        """
        Execute trades with 10-position management system.

        This method reuses the exact same logic as strategies/backtester.py
        but uses MACD signals instead of factor-based signals.

        Position Management Rules:
        - Total capital divided into 10 positions (¥200 each)
        - Signal strength determines positions used (1-10)
        - Stop loss: Sell all if loss >= 10%
        - Take profit 1: Sell 50% if profit >= 15%
        - Take profit 2: Sell remaining if profit >= 30%
        - Signal reversal: Sell positions based on negative signal strength
        """
        cash = self.initial_capital
        position_shares = 0  # Total shares held
        avg_cost = 0  # Weighted average cost per share
        positions_used = 0  # Number of positions currently used
        trades = []
        performance_records = []

        # Track take profit levels that have been triggered
        take_profit1_triggered = False
        take_profit2_triggered = False
        take_profit3_triggered = False

        # Track highest price for trailing stop
        highest_price = 0

        for idx, row in data.iterrows():
            price = row['close']
            signal_strength = row['signal_strength']

            # Calculate current P&L percentage
            if position_shares > 0 and avg_cost > 0:
                pnl_pct = (price - avg_cost) / avg_cost
                # 更新最高价（用于追踪止盈）
                if price > highest_price:
                    highest_price = price
            else:
                pnl_pct = 0
                highest_price = 0

            # ========== PRIORITY 1: Stop Loss ==========
            if position_shares > 0 and pnl_pct <= -self.stop_loss_pct:
                # Stop loss triggered - sell all positions immediately
                proceeds = position_shares * price * (1 - self.sell_fee)
                cash += proceeds

                trades.append({
                    'date': row['date'],
                    'type': 'SELL',
                    'price': price,
                    'shares': position_shares,
                    'value': proceeds,
                    'reason': 'STOP_LOSS',
                    'positions_closed': positions_used,
                    'signal_strength': signal_strength
                })

                position_shares = 0
                avg_cost = 0
                positions_used = 0
                take_profit1_triggered = False
                take_profit2_triggered = False
                take_profit3_triggered = False
                highest_price = 0
                continue

            # ========== PRIORITY 1.5: Trailing Stop (追踪止盈) ==========
            if self.enable_trailing_stop and position_shares > 0 and pnl_pct >= self.trailing_stop_activation:
                # 计算从最高价的回撤
                drawdown_pct = (highest_price - price) / highest_price
                if drawdown_pct >= self.trailing_stop_pct:
                    # 触发追踪止盈，卖出一半
                    positions_to_close = max(1, positions_used // 2)
                    shares_to_sell = int(position_shares * (positions_to_close / positions_used))
                    proceeds = shares_to_sell * price * (1 - self.sell_fee)
                    cash += proceeds
                    position_shares -= shares_to_sell
                    positions_used -= positions_to_close

                    trades.append({
                        'date': row['date'],
                        'type': 'SELL',
                        'price': price,
                        'shares': shares_to_sell,
                        'value': proceeds,
                        'reason': f'TRAILING_STOP(-{drawdown_pct*100:.1f}%)',
                        'positions_closed': positions_to_close,
                        'signal_strength': signal_strength
                    })

                    # 重置追踪止盈
                    highest_price = price

            # ========== PRIORITY 2: Take Profit (分批止盈) ==========
            if position_shares > 0:
                # Level 3: 35% - 卖出40%
                if not take_profit3_triggered and pnl_pct >= self.take_profit_pct3:
                    positions_to_close = max(1, int(positions_used * 0.4))
                    shares_to_sell = int(position_shares * (positions_to_close / positions_used))
                    proceeds = shares_to_sell * price * (1 - self.sell_fee)
                    cash += proceeds
                    position_shares -= shares_to_sell
                    positions_used -= positions_to_close

                    trades.append({
                        'date': row['date'],
                        'type': 'SELL',
                        'price': price,
                        'shares': shares_to_sell,
                        'value': proceeds,
                        'reason': 'TAKE_PROFIT_3',
                        'positions_closed': positions_to_close,
                        'signal_strength': signal_strength
                    })

                    take_profit3_triggered = True
                    if positions_used == 0:
                        # 全部卖出，重置状态
                        position_shares = 0
                        avg_cost = 0
                        take_profit1_triggered = False
                        take_profit2_triggered = False
                        highest_price = 0
                    continue

                # Level 2: 20% - 卖出30%
                elif not take_profit2_triggered and pnl_pct >= self.take_profit_pct2:
                    positions_to_close = max(1, int(positions_used * 0.3))
                    shares_to_sell = int(position_shares * (positions_to_close / positions_used))
                    proceeds = shares_to_sell * price * (1 - self.sell_fee)
                    cash += proceeds
                    position_shares -= shares_to_sell
                    positions_used -= positions_to_close

                    trades.append({
                        'date': row['date'],
                        'type': 'SELL',
                        'price': price,
                        'shares': shares_to_sell,
                        'value': proceeds,
                        'reason': 'TAKE_PROFIT_2',
                        'positions_closed': positions_to_close,
                        'signal_strength': signal_strength
                    })

                    take_profit2_triggered = True
                    continue

                # Level 1: 10% - 卖出30%
                elif not take_profit1_triggered and pnl_pct >= self.take_profit_pct1:
                    positions_to_close = max(1, int(positions_used * 0.3))
                    shares_to_sell = int(position_shares * (positions_to_close / positions_used))
                    proceeds = shares_to_sell * price * (1 - self.sell_fee)
                    cash += proceeds
                    position_shares -= shares_to_sell
                    positions_used -= positions_to_close

                    trades.append({
                        'date': row['date'],
                        'type': 'SELL',
                        'price': price,
                        'shares': shares_to_sell,
                        'value': proceeds,
                        'reason': 'TAKE_PROFIT_1',
                        'positions_closed': positions_to_close,
                        'signal_strength': signal_strength
                    })

                    take_profit1_triggered = True

            # ========== PRIORITY 3: Signal Reversal (Sell) ==========
            if signal_strength < 0 and position_shares > 0:
                # Calculate how many positions to close based on signal strength
                # Strength -1 to -3: Close 1-2 positions
                # Strength -4 to -6: Close 3-5 positions
                # Strength -7 to -10: Close all remaining positions
                if signal_strength >= -3:
                    positions_to_close = min(positions_used, 1 + abs(signal_strength))
                elif signal_strength >= -6:
                    positions_to_close = min(positions_used, 3 + abs(signal_strength) - 3)
                else:
                    positions_to_close = positions_used  # Close all

                positions_to_close = int(positions_to_close)
                shares_to_sell = int(position_shares * (positions_to_close / positions_used))

                if shares_to_sell > 0 and positions_to_close > 0:
                    proceeds = shares_to_sell * price * (1 - self.sell_fee)
                    cash += proceeds
                    position_shares -= shares_to_sell
                    positions_used -= positions_to_close

                    trades.append({
                        'date': row['date'],
                        'type': 'SELL',
                        'price': price,
                        'shares': shares_to_sell,
                        'value': proceeds,
                        'reason': 'SIGNAL_REVERSAL',
                        'positions_closed': positions_to_close,
                        'signal_strength': signal_strength
                    })

                    # Reset take profit flags if all positions closed
                    if positions_used == 0:
                        avg_cost = 0
                        take_profit1_triggered = False
                        take_profit2_triggered = False

            # ========== PRIORITY 4: Add/Open Positions (Buy) ==========
            if signal_strength > 0:
                # Calculate desired number of positions based on signal strength
                # Strength 1-3: 1-2 positions
                # Strength 4-6: 3-5 positions
                # Strength 7-9: 6-9 positions
                # Strength 10: 10 positions (full)
                if signal_strength <= 3:
                    desired_positions = min(signal_strength, 2)
                elif signal_strength <= 6:
                    desired_positions = signal_strength - 1  # 3-5
                elif signal_strength <= 9:
                    desired_positions = signal_strength  # 6-9
                else:
                    desired_positions = 10  # Full position

                desired_positions = int(desired_positions)

                # Calculate how many NEW positions to add
                positions_to_add = max(0, desired_positions - positions_used)
                positions_to_add = min(positions_to_add, self.num_positions - positions_used)

                if positions_to_add > 0:
                    # Calculate investment amount
                    investment = positions_to_add * self.position_size

                    # Only buy if we have enough cash
                    if cash >= investment and price > 0:
                        shares = int(investment // price)
                        if shares > 0:
                            cost = shares * price
                            actual_cash_used = cost
                            cash -= actual_cash_used

                            # Update weighted average cost
                            total_cost = avg_cost * position_shares + cost
                            position_shares += shares
                            avg_cost = total_cost / position_shares
                            positions_used += positions_to_add

                            trades.append({
                                'date': row['date'],
                                'type': 'BUY',
                                'price': price,
                                'shares': shares,
                                'value': cost,
                                'reason': 'SIGNAL_STRENGTH',
                                'positions_added': positions_to_add,
                                'signal_strength': signal_strength
                            })

            # Track portfolio value
            position_value = position_shares * price if position_shares > 0 else 0
            portfolio_value = cash + position_value

            performance_records.append({
                'date': row['date'],
                'cash': cash,
                'position_shares': position_shares,
                'positions_used': positions_used,
                'avg_cost': avg_cost,
                'portfolio_value': portfolio_value,
                'price': price,
                'pnl_pct': pnl_pct if position_shares > 0 else 0,
                'vol': row.get('vol', 0)  # 添加成交量数据
            })

        return trades, pd.DataFrame(performance_records)

    def _calculate_metrics(self, trades: List[Dict], performance: pd.DataFrame,
                         data: pd.DataFrame) -> Dict:
        """Calculate comprehensive performance metrics"""
        if len(performance) == 0:
            return self._empty_metrics()

        final_value = performance['portfolio_value'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital

        # Buy & Hold benchmark
        if len(data) > 0:
            buy_hold_return = (data['close'].iloc[-1] - data['close'].iloc[0]) / data['close'].iloc[0]
        else:
            buy_hold_return = 0

        # Daily returns for Sharpe ratio
        returns = performance['portfolio_value'].pct_change().dropna()

        if len(returns) > 0 and returns.std() > 0:
            # Annualized Sharpe ratio (assuming 252 trading days)
            sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std()
        else:
            sharpe_ratio = 0

        # Max Drawdown
        cummax = performance['portfolio_value'].cummax()
        drawdown = (performance['portfolio_value'] - cummax) / cummax
        max_drawdown = drawdown.min()

        # Win Rate calculation - count complete round trips
        position_entries = []
        profitable_exits = 0
        total_exits = 0

        for trade in trades:
            if trade['type'] == 'BUY':
                position_entries.append({
                    'price': trade['price'],
                    'shares': trade['shares']
                })
            elif trade['type'] == 'SELL' and position_entries:
                # Match with oldest entry (FIFO)
                entry = position_entries.pop(0)
                sell_price = trade['price']
                buy_price = entry['price']

                # Account for transaction cost
                effective_sell_price = sell_price * (1 - self.sell_fee)
                if effective_sell_price > buy_price:
                    profitable_exits += 1
                total_exits += 1

        win_rate = profitable_exits / total_exits if total_exits else 0

        # Calculate transaction costs
        total_costs = sum([t['value'] * self.sell_fee for t in trades if t['type'] == 'SELL'])

        # Calculate average holding period
        avg_hold_days = self._calculate_avg_hold_days(trades)

        # Calculate position statistics
        buy_trades = [t for t in trades if t['type'] == 'BUY']
        sell_trades = [t for t in trades if t['type'] == 'SELL']

        # Count different types of exits
        stop_loss_count = len([t for t in sell_trades if t.get('reason') == 'STOP_LOSS'])
        take_profit_count = len([t for t in sell_trades if 'TAKE_PROFIT' in t.get('reason', '')])
        signal_reversal_count = len([t for t in sell_trades if t.get('reason') == 'SIGNAL_REVERSAL'])

        return {
            'initial_capital': self.initial_capital,
            'final_capital': final_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'buy_hold_return_pct': buy_hold_return * 100,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(trades),
            'buy_signals': len(buy_trades),
            'sell_signals': len(sell_trades),
            'transaction_costs': total_costs,
            'avg_hold_days': avg_hold_days,
            'stop_loss_count': stop_loss_count,
            'take_profit_count': take_profit_count,
            'signal_reversal_count': signal_reversal_count
        }

    def _calculate_avg_hold_days(self, trades: List[Dict]) -> float:
        """Calculate average holding period in days"""
        hold_periods = []
        sell_trades = [t for t in trades if t['type'] == 'SELL']

        for sell in sell_trades:
            buys = [b for b in trades if b['type'] == 'BUY' and b['date'] < sell['date']]
            if buys:
                buy_date = datetime.strptime(str(buys[-1]['date']), '%Y%m%d')
                sell_date = datetime.strptime(str(sell['date']), '%Y%m%d')
                hold_days = (sell_date - buy_date).days
                hold_periods.append(hold_days)

        return np.mean(hold_periods) if hold_periods else 0

    def _empty_metrics(self) -> Dict:
        """Return empty metrics when no data available"""
        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.initial_capital,
            'total_return': 0,
            'total_return_pct': 0,
            'buy_hold_return_pct': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'win_rate': 0,
            'total_trades': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'transaction_costs': 0,
            'avg_hold_days': 0,
            'stop_loss_count': 0,
            'take_profit_count': 0,
            'signal_reversal_count': 0
        }
