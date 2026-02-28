"""
纯RSI 0-10仓策略回测引擎

核心逻辑：
- 读取exec_position作为T+1执行仓位
- 计算仓位变化并执行交易
- 0.5%卖出手续费，买入无手续费
- 返回标准回测指标
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import database
from .pure_rsi import PureRSISignalGenerator


class PureRSIBacktester:
    """纯RSI策略回测引擎"""

    def __init__(self, initial_capital: float = 2000, total_positions: int = 10):
        """
        初始化回测引擎

        Args:
            initial_capital: 初始资金（默认¥2000）
            total_positions: 总仓位数（默认10）
        """
        self.initial_capital = initial_capital
        self.total_positions = total_positions
        self.position_size = initial_capital / total_positions  # 每仓价值
        self.sell_fee = 0.005  # 卖出手续费0.5%
        self.buy_fee = 0.0  # 买入无手续费

    def run_backtest(self, etf_code: str, start_date: str = None,
                     end_date: str = None, strategy_params: Dict = None) -> Dict:
        """
        运行纯RSI策略回测

        Args:
            etf_code: ETF代码 (例如 '510330.SH')
            start_date: 开始日期 (YYYYMMDD格式)
            end_date: 结束日期 (YYYYMMDD格式)
            strategy_params: 策略参数配置

        Returns:
            回测结果字典，包含success、trades、performance、metrics
        """
        try:
            # 初始化信号生成器
            signal_generator = PureRSISignalGenerator(strategy_params)

            # 加载价格数据
            data = self._load_data(etf_code, start_date, end_date)

            if data is None or len(data) == 0:
                return {
                    'success': False,
                    'message': f"{etf_code} 在指定日期范围内没有数据",
                    'trades': [],
                    'performance': [],
                    'metrics': self._empty_metrics()
                }

            # 生成信号
            data = signal_generator.generate_signals(data)

            # 执行交易
            trades, performance = self._execute_trades(data)

            # 计算指标
            metrics = self._calculate_metrics(trades, performance, data)

            return {
                'success': True,
                'trades': trades,
                'performance': performance.to_dict('records') if isinstance(performance, pd.DataFrame) else performance,
                'metrics': metrics,
                'strategy_params': strategy_params or signal_generator.params
            }
        except Exception as e:
            return {
                'success': False,
                'message': f"回测失败: {str(e)}",
                'trades': [],
                'performance': [],
                'metrics': self._empty_metrics()
            }

    def _load_data(self, etf_code: str, start_date: str = None,
                   end_date: str = None) -> pd.DataFrame:
        """
        从数据库加载ETF价格数据

        Args:
            etf_code: ETF代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            包含OHLCV数据的DataFrame
        """
        # 从ETF数据库加载
        data = database.get_etf_daily_data(
            ts_code=etf_code,
            start_date=start_date,
            end_date=end_date
        )

        if data is None or len(data) == 0:
            return None

        # 转换为DataFrame
        if isinstance(data, list):
            data = pd.DataFrame(data)

        # 标准化列名
        if 'trade_date' in data.columns:
            data = data.rename(columns={'trade_date': 'date'})
        elif 'cal_date' in data.columns:
            data = data.rename(columns={'cal_date': 'date'})

        # 确保必需列存在
        required_cols = ['date', 'open', 'high', 'low', 'close', 'vol']
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"缺少必需的列: {col}")

        # 按日期排序
        data = data.sort_values('date').reset_index(drop=True)

        # 删除关键列中有NaN的行
        data = data.dropna(subset=['close']).reset_index(drop=True)

        return data

    def _execute_trades(self, data: pd.DataFrame) -> Tuple[List[Dict], pd.DataFrame]:
        """
        执行交易，严格按目标仓位执行

        交易规则：
        - 读取exec_position作为T+1执行仓位
        - 根据仓位变化执行买卖
        - 0.5%卖出手续费
        - 买入无手续费
        """
        cash = self.initial_capital
        position_units = 0  # 当前仓位（0-10）
        position_value = 0  # 持仓价值
        trades = []
        performance_records = []

        for idx, row in data.iterrows():
            price = row['close']
            target_units = int(row.get('exec_position', 0))  # T+1后的目标仓位

            # 计算当前持仓价值
            if position_units > 0:
                # 根据当前价格更新持仓价值
                avg_cost_per_unit = position_value / position_units if position_units > 0 else 0
                current_position_value = position_units * self.position_size
            else:
                current_position_value = 0
                avg_cost_per_unit = 0

            # 计算仓位变化
            units_change = target_units - position_units

            if units_change > 0:
                # 加仓（买入）
                investment = units_change * self.position_size

                if cash >= investment and price > 0:
                    # 计算买入股数
                    shares = int(investment // price)

                    if shares > 0:
                        cost = shares * price
                        actual_cash_used = cost
                        cash -= actual_cash_used

                        # 更新持仓
                        position_units = target_units
                        position_value += cost

                        trades.append({
                            'date': row['date'],
                            'type': 'BUY',
                            'price': price,
                            'shares': shares,
                            'value': cost,
                            'reason': 'POSITION_CHANGE',
                            'units': units_change,
                            'target_units': target_units
                        })

            elif units_change < 0:
                # 减仓（卖出）
                units_to_close = abs(units_change)

                if position_units > 0:
                    # 简化：直接按价值计算
                    sell_value = units_to_close * self.position_size
                    proceeds = sell_value * (1 - self.sell_fee)
                    cash += proceeds

                    # 更新持仓
                    position_units = target_units
                    position_value -= sell_value

                    trades.append({
                        'date': row['date'],
                        'type': 'SELL',
                        'price': price,
                        'shares': 0,  # 简化，不追踪具体股数
                        'value': proceeds,
                        'reason': 'POSITION_CHANGE',
                        'units': units_to_close,
                        'target_units': target_units
                    })

            # 计算投资组合价值
            if position_units > 0:
                portfolio_value = cash + position_units * self.position_size
            else:
                portfolio_value = cash

            # 计算收益率
            if position_units > 0:
                avg_cost = position_value / position_units if position_units > 0 else price
                pnl_pct = (price - avg_cost) / avg_cost if avg_cost > 0 else 0
            else:
                pnl_pct = 0

            performance_records.append({
                'date': row['date'],
                'cash': cash,
                'position_units': position_units,
                'position_value': position_value if position_units > 0 else 0,
                'portfolio_value': portfolio_value,
                'price': price,
                'pnl_pct': pnl_pct,
                'vol': row.get('vol', 0),
                'rsi': row.get('rsi', 0),
                'rsi_zone': row.get('rsi_zone', ''),
                'rsi_direction': row.get('rsi_direction', ''),
                'target_position': row.get('target_position', 0),
                'exec_position': row.get('exec_position', 0),
                'position_reason': row.get('position_reason', '')
            })

        return trades, pd.DataFrame(performance_records)

    def _calculate_metrics(self, trades: List[Dict], performance: pd.DataFrame,
                         data: pd.DataFrame) -> Dict:
        """计算综合性能指标"""
        if len(performance) == 0:
            return self._empty_metrics()

        final_value = performance['portfolio_value'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital

        # 买入持有基准
        if len(data) > 0:
            buy_hold_return = (data['close'].iloc[-1] - data['close'].iloc[0]) / data['close'].iloc[0]
        else:
            buy_hold_return = 0

        # 日收益率用于夏普比率
        returns = performance['portfolio_value'].pct_change().dropna()

        if len(returns) > 0 and returns.std() > 0:
            # 年化夏普比率（假设252个交易日）
            sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std()
        else:
            sharpe_ratio = 0

        # 最大回撤
        cummax = performance['portfolio_value'].cummax()
        drawdown = (performance['portfolio_value'] - cummax) / cummax
        max_drawdown = drawdown.min()

        # 胜率计算 - 统计完整的来回交易
        position_entries = []
        profitable_exits = 0
        total_exits = 0

        for trade in trades:
            if trade['type'] == 'BUY':
                position_entries.append({
                    'price': trade['price'],
                    'units': trade['units']
                })
            elif trade['type'] == 'SELL' and position_entries:
                # 匹配最早的入场（FIFO）
                entry = position_entries.pop(0)
                sell_price = trade['price']
                buy_price = entry['price']

                # 考虑交易成本
                effective_sell_price = sell_price * (1 - self.sell_fee)
                if effective_sell_price > buy_price:
                    profitable_exits += 1
                total_exits += 1

        win_rate = profitable_exits / total_exits if total_exits else 0

        # 计算交易成本
        total_costs = sum([t['value'] * self.sell_fee for t in trades if t['type'] == 'SELL'])

        # 计算平均持仓天数
        avg_hold_days = self._calculate_avg_hold_days(trades)

        # 计算仓位统计
        buy_trades = [t for t in trades if t['type'] == 'BUY']
        sell_trades = [t for t in trades if t['type'] == 'SELL']

        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'buy_hold_return_pct': buy_hold_return * 100,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown_pct': max_drawdown * 100,
            'max_drawdown': max_drawdown,
            'win_rate_pct': win_rate * 100,
            'win_rate': win_rate,
            'total_trades': len(trades),
            'buy_signals': len(buy_trades),
            'sell_signals': len(sell_trades),
            'transaction_costs': total_costs,
            'avg_hold_days': avg_hold_days
        }

    def _calculate_avg_hold_days(self, trades: List[Dict]) -> float:
        """计算平均持仓天数"""
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
        """返回空指标"""
        return {
            'initial_capital': self.initial_capital,
            'final_value': self.initial_capital,
            'total_return': 0,
            'total_return_pct': 0,
            'buy_hold_return_pct': 0,
            'sharpe_ratio': 0,
            'max_drawdown_pct': 0,
            'max_drawdown': 0,
            'win_rate_pct': 0,
            'win_rate': 0,
            'total_trades': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'transaction_costs': 0,
            'avg_hold_days': 0
        }
