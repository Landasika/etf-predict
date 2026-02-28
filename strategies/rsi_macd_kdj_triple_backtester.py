"""
RSI+MACD+KDJ 三指标共振策略回测引擎（重构版）

核心特点：
1. 趋势铁律：多头/震荡/空头三种仓位管理
2. 绑定趋势的止损止盈
3. T+1执行（避免未来函数）
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import database
from .rsi_macd_kdj_triple import RSIMACDKDJTripleSignalGenerator


class RSIMACDKDJTripleBacktester:
    """RSI+MACD+KDJ 三指标共振策略回测引擎（重构版）"""

    def __init__(self, initial_capital: float = 2000, total_positions: int = 10):
        self.initial_capital = initial_capital
        self.total_positions = total_positions
        self.position_value = initial_capital / total_positions  # 每仓价值

    def run_backtest(self, etf_code: str, start_date: str, end_date: str = None,
                     strategy_params: Dict = None) -> Dict:
        """运行回测"""
        # 1. 加载数据
        data = self._load_data(etf_code, start_date, end_date)

        if data is None or len(data) == 0:
            return {
                'success': False,
                'message': f'没有数据: {etf_code} from {start_date}',
                'trades': [],
                'performance': [],
                'metrics': {}
            }

        # 2. 生成信号
        signal_gen = RSIMACDKDJTripleSignalGenerator(strategy_params)
        data = signal_gen.generate_signals(data)

        # 3. 执行交易（严格T+1）
        trades, performance = self._execute_trades(data, strategy_params)

        # 4. 计算指标
        metrics = self._calculate_metrics(trades, performance, data)

        return {
            'success': True,
            'trades': trades,
            'performance': performance.to_dict('records') if isinstance(performance, pd.DataFrame) else performance,
            'metrics': metrics,
            'strategy_params': strategy_params or signal_gen.params
        }

    def _load_data(self, etf_code: str, start_date: str = None,
                   end_date: str = None) -> pd.DataFrame:
        """加载ETF价格数据"""
        data = database.get_etf_daily_data(
            ts_code=etf_code,
            start_date=start_date,
            end_date=end_date
        )

        if data is None or len(data) == 0:
            return None

        if isinstance(data, list):
            data = pd.DataFrame(data)

        # 标准化列名
        if 'trade_date' in data.columns:
            data = data.rename(columns={'trade_date': 'date'})
        elif 'cal_date' in data.columns:
            data = data.rename(columns={'cal_date': 'date'})

        # 确保必要列存在
        required_cols = ['date', 'open', 'high', 'low', 'close', 'vol']
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"缺少必要列: {col}")

        data = data.sort_values('date').reset_index(drop=True)
        data = data.dropna(subset=['close']).reset_index(drop=True)

        return data

    def _execute_trades(self, df: pd.DataFrame, params: Dict = None) -> Tuple[List[Dict], pd.DataFrame]:
        """
        执行交易逻辑（带止损止盈）

        关键：使用exec_position（已shift(1)），避免未来函数
        """
        cash = self.initial_capital
        position_shares = 0.0
        entry_price = 0.0
        entry_date = None
        trades = []
        performance_records = []

        # 获取参数
        if params is None:
            params = RSIMACDKDJTripleSignalGenerator.default_params()

        stop_loss_bull = params.get('stop_loss_bull', 0.05)
        stop_loss_flat = params.get('stop_loss_flat', 0.03)
        stop_loss_bear = params.get('stop_loss_bear', 0.02)
        take_profit_bull = params.get('take_profit_bull', 0.15)
        take_profit_flat = params.get('take_profit_flat', 0.08)
        extreme_overbought = params.get('extreme_overbought', 80)

        for idx, row in df.iterrows():
            price = row['close']
            target_units = int(row['exec_position'])
            current_units = int((position_shares * price) / self.position_value) if position_shares > 0 else 0

            # 计算当前盈亏百分比
            if position_shares > 0 and entry_price > 0:
                pnl_pct = (price - entry_price) / entry_price
            else:
                pnl_pct = 0

            # ========== 止损止盈检查（优先级最高）==========
            if position_shares > 0:
                # 获取当前趋势类型
                trend = row.get('trend_type', 'FLAT')
                rsi = row.get('rsi', 50)

                # 根据趋势类型应用止损止盈
                need_sell = False
                sell_reason = ''

                # 多头趋势止损止盈
                if trend == 'BULL':
                    # 止损：亏损5% 或 跌破MA20
                    if pnl_pct <= -stop_loss_bull or price < row.get('ma20', price * 0.95):
                        need_sell = True
                        sell_reason = f'多头止损({pnl_pct*100:.1f}%或跌破MA20)'
                    # 止盈：盈利15%
                    elif pnl_pct >= take_profit_bull:
                        need_sell = True
                        sell_reason = f'多头止盈({pnl_pct*100:.1f}%)'
                    # 极端超买减仓50%
                    elif rsi > extreme_overbought and current_units > 4:
                        # 减仓50%
                        units_to_close = max(current_units // 2, 1)
                        shares_to_sell = int(position_shares * (units_to_close / current_units))
                        proceeds = shares_to_sell * price * (1 - 0.005)
                        position_shares -= shares_to_sell
                        cash += proceeds

                        trades.append({
                            'date': row['date'],
                            'type': 'SELL',
                            'price': price,
                            'units': units_to_close,
                            'value': proceeds,
                            'reason': f'RSI极度超买({rsi:.1f}>80)，减仓50%'
                        })
                        # 更新入场均价（按比例调整）
                        if position_shares > 0:
                            entry_price = ((position_shares + shares_to_sell) * entry_price) / position_shares
                        else:
                            entry_price = 0
                            entry_date = None

                # 震荡趋势止损止盈
                elif trend == 'FLAT':
                    if pnl_pct <= -stop_loss_flat:
                        need_sell = True
                        sell_reason = f'震荡止损({pnl_pct*100:.1f}%)'
                    elif pnl_pct >= take_profit_flat:
                        need_sell = True
                        sell_reason = f'震荡止盈({pnl_pct*100:.1f}%)'
                    elif row.get('signal_type') == 'SELL':
                        need_sell = True
                        sell_reason = '震荡趋势卖出信号'

                # 空头趋势止损止盈
                elif trend == 'BEAR':
                    if pnl_pct <= -stop_loss_bear:
                        need_sell = True
                        sell_reason = f'空头止损({pnl_pct*100:.1f}%)'
                    elif pnl_pct >= 0.05:  # 空头5%就跑
                        need_sell = True
                        sell_reason = f'空头止盈({pnl_pct*100:.1f}%)'

                # 执行卖出
                if need_sell:
                    proceeds = position_shares * price * (1 - 0.005)
                    cash += proceeds

                    trades.append({
                        'date': row['date'],
                        'type': 'SELL',
                        'price': price,
                        'units': current_units,
                        'value': proceeds,
                        'reason': sell_reason
                    })

                    position_shares = 0
                    entry_price = 0
                    entry_date = None

            # ========== 根据目标仓位调仓 ==========
            target_value = target_units * self.position_value
            current_value = position_shares * price if position_shares > 0 else 0
            delta_value = target_value - current_value

            if abs(delta_value) > 0.01:
                if delta_value > 0 and cash >= delta_value:
                    # 加仓
                    shares_to_buy = delta_value / price
                    old_shares = position_shares
                    position_shares += shares_to_buy
                    cash -= delta_value

                    # 更新入场均价（加权平均）
                    if position_shares > 0:
                        entry_price = ((old_shares * entry_price) + (shares_to_buy * price)) / position_shares
                    else:
                        entry_price = price

                    if entry_date is None:
                        entry_date = row['date']

                    if target_units - current_units >= 2:
                        trades.append({
                            'date': row['date'],
                            'type': 'BUY',
                            'price': price,
                            'units': target_units - current_units,
                            'value': delta_value,
                            'reason': f"仓位{current_units}→{target_units}成: {row.get('position_reason', '')}"
                        })

                elif delta_value < 0:
                    # 减仓
                    shares_to_sell = abs(delta_value) / price
                    if position_shares >= shares_to_sell:
                        old_shares = position_shares
                        position_shares -= shares_to_sell
                        cash += abs(delta_value)

                        if old_shares > 0 and position_shares < old_shares:
                            # 保持入场均价不变
                            pass

                        if current_units - target_units >= 2:
                            trades.append({
                                'date': row['date'],
                                'type': 'SELL',
                                'price': price,
                                'units': current_units - target_units,
                                'value': abs(delta_value),
                                'reason': f"仓位{current_units}→{target_units}成: {row.get('position_reason', '')}"
                            })

            # 记录绩效
            position_value = position_shares * price if position_shares > 0 else 0
            portfolio_value = cash + position_value
            position_units_display = int(position_value / self.position_value) if position_value > 0 else 0

            performance_records.append({
                'date': row['date'],
                'cash': cash,
                'position_units': position_units_display,
                'position_shares': position_shares,
                'position_value': position_value,
                'portfolio_value': portfolio_value,
                'price': price,
                'pnl_pct': pnl_pct if position_shares > 0 else 0,
                'ma20': row.get('ma20', 0),
                'ma60': row.get('ma60', 0),
                'ma_trend': row.get('trend_type', ''),
                'rsi': row.get('rsi', 0),
                'macd_dif': row.get('macd_dif', 0),
                'macd_dea': row.get('macd_dea', 0),
                'macd_hist': row.get('macd_hist', 0),
                'macd_trend': row.get('macd_above_zero', False),
                'kdj_k': row.get('kdj_k', 0),
                'kdj_d': row.get('kdj_d', 0),
                'kdj_j': row.get('kdj_j', 0),
                'kdj_golden_cross': row.get('kdj_golden_cross', False),
                'kdj_dead_cross': row.get('kdj_dead_cross', False),
                'target_position': row.get('target_position', 0),
                'signal_reason': row.get('position_reason', '')
            })

        return trades, pd.DataFrame(performance_records)

    def _calculate_metrics(self, trades: List[Dict], performance: pd.DataFrame,
                          df: pd.DataFrame) -> Dict:
        """计算回测指标"""
        if len(performance) == 0:
            return {
                'total_return_pct': 0,
                'annual_return_pct': 0,
                'max_drawdown_pct': 0,
                'sharpe_ratio': 0,
                'total_trades': 0,
                'final_value': self.initial_capital
            }

        final_value = performance['portfolio_value'].iloc[-1]
        total_return_pct = (final_value - self.initial_capital) / self.initial_capital * 100

        # 年化收益率
        if len(performance) > 1:
            trading_days = len(performance)
            years = trading_days / 252
            if years > 0:
                annual_return_pct = ((final_value / self.initial_capital) ** (1/years) - 1) * 100
            else:
                annual_return_pct = 0
        else:
            annual_return_pct = 0

        # 最大回撤
        performance['cummax'] = performance['portfolio_value'].cummax()
        performance['drawdown'] = (performance['portfolio_value'] - performance['cummax']) / performance['cummax']
        max_drawdown_pct = performance['drawdown'].min() * 100

        # 夏普比率
        if len(performance) > 1:
            performance['daily_return'] = performance['portfolio_value'].pct_change()
            mean_return = performance['daily_return'].mean()
            std_return = performance['daily_return'].std()
            if std_return > 0:
                sharpe_ratio = (mean_return / std_return) * np.sqrt(252)
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        # 交易次数
        total_trades = len(trades)

        # 仓位分布
        position_dist = performance['position_units'].value_counts().to_dict()

        # 持仓时间占比
        holding_days = (performance['position_units'] > 0).sum()
        holding_ratio = holding_days / len(performance) * 100 if len(performance) > 0 else 0

        # Buy & Hold 对比
        if len(df) > 0:
            buy_hold_return_pct = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100
        else:
            buy_hold_return_pct = 0

        return {
            'total_return_pct': round(total_return_pct, 2),
            'annual_return_pct': round(annual_return_pct, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'total_trades': total_trades,
            'final_value': round(final_value, 2),
            'initial_capital': self.initial_capital,
            'position_distribution': position_dist,
            'holding_ratio_pct': round(holding_ratio, 2),
            'buy_hold_return_pct': round(buy_hold_return_pct, 2)
        }
