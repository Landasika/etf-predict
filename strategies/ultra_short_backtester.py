"""
超短线策略回测引擎

特点：
1. 持仓周期限制（1-3天）
2. 更严格的止损（3-5%）
3. 更快的止盈（5-10%）
4. 强制平仓机制
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import database
from .ultra_short_term import UltraShortTermSignalGenerator, get_ultra_short_params


class UltraShortBacktester:
    """超短线策略回测引擎"""

    def __init__(self, style: str = 'scalping_day'):
        """
        初始化超短线回测引擎

        Args:
            style: 交易风格 ('scalping_day', 'swing_3days', 'gap_trading')
        """
        self.params = get_ultra_short_params(style)
        self.style = style
        self.signal_generator = UltraShortTermSignalGenerator(self.params)

        # 交易参数
        self.initial_capital = 2000
        self.num_positions = 10
        self.position_size = self.initial_capital / self.num_positions
        self.sell_fee = 0.005  # 0.5%卖出费率

        # 止损止盈
        self.stop_loss_pct = self.params.get('stop_loss_pct', 0.03)
        self.take_profit_pct1 = self.params.get('take_profit_pct1', 0.05)
        self.take_profit_pct2 = self.params.get('take_profit_pct2', 0.08)

        # 持仓限制
        self.max_holding_days = self.params.get('max_holding_days', 2)

    def run_backtest(self, etf_code: str, start_date: str = None,
                    end_date: str = None) -> Dict:
        """
        运行超短线回测

        Args:
            etf_code: ETF代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            回测结果
        """
        # 加载数据
        data = database.get_etf_daily_data(etf_code, start_date or '20240101')
        if not data or len(data) < 30:
            return {
                'success': False,
                'message': f'数据不足（需要至少30天）',
                'data': None
            }

        df = pd.DataFrame(data)

        # 生成信号
        df = self.signal_generator.generate_signals(df)

        # 执行交易
        trades, performance = self._execute_trades(df)

        # 计算指标
        metrics = self._calculate_metrics(trades, performance, df)

        return {
            'success': True,
            'trades': trades,
            'performance': performance,
            'metrics': metrics,
            'style': self.style
        }

    def _execute_trades(self, df: pd.DataFrame) -> Tuple[List[Dict], pd.DataFrame]:
        """执行超短线交易"""
        cash = self.initial_capital
        position_shares = 0
        avg_cost = 0
        positions_used = 0
        trades = []
        performance_records = []

        entry_idx = None  # 入场索引
        holding_days = 0  # 持仓天数

        for idx, row in df.iterrows():
            price = row['close']
            signal = row.get('ultra_short_signal', 0)
            strength = row.get('ultra_short_strength', 0)

            # 计算当前盈亏
            if position_shares > 0 and avg_cost > 0:
                pnl_pct = (price - avg_cost) / avg_cost
                holding_days = idx - entry_idx if entry_idx is not None else 0
            else:
                pnl_pct = 0
                holding_days = 0

            # === 卖出逻辑（优先级从高到低）===

            # 1. 止损
            if position_shares > 0 and pnl_pct <= -self.stop_loss_pct:
                proceeds = position_shares * price * (1 - self.sell_fee)
                cash += proceeds

                trades.append({
                    'date': row['trade_date'],
                    'type': 'SELL',
                    'price': price,
                    'shares': position_shares,
                    'value': proceeds,
                    'reason': 'STOP_LOSS',
                    'pnl_pct': pnl_pct,
                    'holding_days': holding_days,
                    'signal_strength': signal
                })

                position_shares = 0
                avg_cost = 0
                positions_used = 0
                entry_idx = None

            # 2. 第二止盈
            elif position_shares > 0 and pnl_pct >= self.take_profit_pct2:
                proceeds = position_shares * price * (1 - self.sell_fee)
                cash += proceeds

                trades.append({
                    'date': row['trade_date'],
                    'type': 'SELL',
                    'price': price,
                    'shares': position_shares,
                    'value': proceeds,
                    'reason': 'TAKE_PROFIT_2',
                    'pnl_pct': pnl_pct,
                    'holding_days': holding_days,
                    'signal_strength': signal
                })

                position_shares = 0
                avg_cost = 0
                positions_used = 0
                entry_idx = None

            # 3. 第一止盈（卖出一半）
            elif position_shares > 0 and pnl_pct >= self.take_profit_pct1 and positions_used >= 2:
                shares_to_sell = position_shares // 2
                proceeds = shares_to_sell * price * (1 - self.sell_fee)
                cash += proceeds
                position_shares -= shares_to_sell
                positions_used = max(1, positions_used - 1)

                trades.append({
                    'date': row['trade_date'],
                    'type': 'SELL',
                    'price': price,
                    'shares': shares_to_sell,
                    'value': proceeds,
                    'reason': 'TAKE_PROFIT_1',
                    'pnl_pct': pnl_pct,
                    'holding_days': holding_days,
                    'signal_strength': signal
                })

            # 4. 卖出信号
            elif position_shares > 0 and signal < 0:
                proceeds = position_shares * price * (1 - self.sell_fee)
                cash += proceeds

                trades.append({
                    'date': row['trade_date'],
                    'type': 'SELL',
                    'price': price,
                    'shares': position_shares,
                    'value': proceeds,
                    'reason': 'SIGNAL',
                    'pnl_pct': pnl_pct,
                    'holding_days': holding_days,
                    'signal_strength': signal
                })

                position_shares = 0
                avg_cost = 0
                positions_used = 0
                entry_idx = None

            # 5. 强制平仓（超过最大持仓天数）
            elif position_shares > 0 and holding_days >= self.max_holding_days:
                proceeds = position_shares * price * (1 - self.sell_fee)
                cash += proceeds

                trades.append({
                    'date': row['trade_date'],
                    'type': 'SELL',
                    'price': price,
                    'shares': position_shares,
                    'value': proceeds,
                    'reason': 'MAX_HOLDING',
                    'pnl_pct': pnl_pct,
                    'holding_days': holding_days,
                    'signal_strength': signal
                })

                position_shares = 0
                avg_cost = 0
                positions_used = 0
                entry_idx = None

            # === 买入逻辑 ===
            elif signal > 0 and positions_used < self.num_positions:
                # 根据信号强度决定买入数量
                positions_to_add = min(int(strength * 3) + 1, self.num_positions - positions_used)

                if positions_to_add > 0 and cash > 0:
                    investment = positions_to_add * self.position_size
                    if investment <= cash:
                        shares = int(investment / price)
                        if shares > 0:
                            cost = shares * price
                            cash -= cost

                            # 更新平均成本
                            total_cost = avg_cost * position_shares + cost
                            position_shares += shares
                            avg_cost = total_cost / position_shares
                            positions_used += positions_to_add

                            if entry_idx is None:
                                entry_idx = idx

                            trades.append({
                                'date': row['trade_date'],
                                'type': 'BUY',
                                'price': price,
                                'shares': shares,
                                'value': cost,
                                'reason': 'SIGNAL',
                                'positions_added': positions_to_add,
                                'signal_strength': signal
                            })

            # 记录性能
            position_value = position_shares * price if position_shares > 0 else 0
            portfolio_value = cash + position_value

            performance_records.append({
                'date': row['trade_date'],
                'cash': cash,
                'position_shares': position_shares,
                'positions_used': positions_used,
                'avg_cost': avg_cost,
                'portfolio_value': portfolio_value,
                'price': price,
                'pnl_pct': pnl_pct if position_shares > 0 else 0,
                'holding_days': holding_days
            })

        return trades, pd.DataFrame(performance_records)

    def _calculate_metrics(self, trades: List[Dict], performance: pd.DataFrame,
                          df: pd.DataFrame) -> Dict:
        """计算性能指标"""
        if len(performance) == 0:
            return self._empty_metrics()

        final_value = performance['portfolio_value'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital

        # Buy & Hold
        buy_hold_return = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]

        # 交易统计
        buy_trades = [t for t in trades if t['type'] == 'BUY']
        sell_trades = [t for t in trades if t['type'] == 'SELL']

        # 计算每笔交易的盈亏
        trade_pairs = []
        i = 0
        while i < len(trades):
            if trades[i]['type'] == 'BUY':
                entry = trades[i]
                # 找到对应的卖出
                for j in range(i+1, len(trades)):
                    if trades[j]['type'] == 'SELL':
                        exit_trade = trades[j]
                        # 计算该笔交易的盈亏
                        # 这里简化处理，实际应该根据卖出数量计算
                        break
            i += 1

        # 胜率
        profitable_exits = 0
        total_exits = 0
        for t in sell_trades:
            if 'pnl_pct' in t:
                total_exits += 1
                if t['pnl_pct'] > 0:
                    profitable_exits += 1

        win_rate = profitable_exits / total_exits if total_exits > 0 else 0

        # 平均持仓天数
        avg_holding_days = np.mean([t.get('holding_days', 0) for t in sell_trades]) if sell_trades else 0

        # 总交易成本
        total_costs = sum([t.get('value', 0) * self.sell_fee for t in sell_trades])

        return {
            'style': self.style,
            'description': self.params.get('description', ''),
            'initial_capital': self.initial_capital,
            'final_capital': final_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'buy_hold_return_pct': buy_hold_return * 100,
            'total_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'win_rate': win_rate,
            'avg_holding_days': avg_holding_days,
            'transaction_costs': total_costs,
            'stop_loss_count': len([t for t in sell_trades if t.get('reason') == 'STOP_LOSS']),
            'take_profit_count': len([t for t in sell_trades if 'TAKE_PROFIT' in t.get('reason', '')]),
            'max_holding_count': len([t for t in sell_trades if t.get('reason') == 'MAX_HOLDING'])
        }

    def _empty_metrics(self) -> Dict:
        """返回空指标"""
        return {
            'style': self.style,
            'description': self.params.get('description', ''),
            'initial_capital': self.initial_capital,
            'final_capital': self.initial_capital,
            'total_return': 0,
            'total_return_pct': 0,
            'buy_hold_return_pct': 0,
            'total_trades': 0,
            'sell_trades': 0,
            'win_rate': 0,
            'avg_holding_days': 0,
            'transaction_costs': 0,
            'stop_loss_count': 0,
            'take_profit_count': 0,
            'max_holding_count': 0
        }
