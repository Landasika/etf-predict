"""
MACD + KDJ 离散仓位系统 2.0 回测引擎

核心特点：
1. 0-10成离散仓位管理
2. T+1执行（避免未来函数）
3. 严格按目标仓位调仓
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import database
from .macd_kdj_discrete import MACDKDJDiscreteSignalGenerator


class MACDKDJDiscreteBacktester:
    """
    MACD + KDJ 离散仓位系统回测引擎

    核心特点：
    1. 0-10成离散仓位管理
    2. T+1执行（避免未来函数）
    3. 严格按目标仓位调仓
    """

    def __init__(self, initial_capital: float = 2000, total_positions: int = 10):
        """
        初始化回测引擎

        Args:
            initial_capital: 初始资金（默认2000元）
            total_positions: 总仓位数（默认10仓）
        """
        self.initial_capital = initial_capital
        self.total_positions = total_positions
        self.position_value = initial_capital / total_positions  # 每仓价值

    def run_backtest(self, etf_code: str, start_date: str, end_date: str = None,
                     strategy_params: Dict = None) -> Dict:
        """
        运行回测

        Args:
            etf_code: ETF代码
            start_date: 开始日期
            end_date: 结束日期
            strategy_params: 策略参数

        Returns:
            回测结果字典
        """
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
        signal_gen = MACDKDJDiscreteSignalGenerator(strategy_params)
        data = signal_gen.generate_signals(data)

        # 3. 执行交易（严格T+1）
        trades, performance = self._execute_trades(data)

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
        """
        加载ETF价格数据

        Args:
            etf_code: ETF代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            DataFrame with OHLCV data
        """
        # 从数据库加载
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

        # 确保必要列存在
        required_cols = ['date', 'open', 'high', 'low', 'close', 'vol']
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"缺少必要列: {col}")

        # 按日期排序
        data = data.sort_values('date').reset_index(drop=True)

        # 删除NaN行
        data = data.dropna(subset=['close']).reset_index(drop=True)

        return data

    def _execute_trades(self, df: pd.DataFrame) -> Tuple[List[Dict], pd.DataFrame]:
        """
        执行交易逻辑

        关键：使用exec_position（已shift(1)），避免未来函数
        """
        cash = self.initial_capital
        position_shares = 0.0  # 当前持有的股票数量
        entry_price = 0.0  # 买入价格
        trades = []
        performance_records = []

        for idx, row in df.iterrows():
            price = row['close']
            target_units = int(row['exec_position'])  # 已shift(1)
            current_units = int((position_shares * price) / self.position_value) if position_shares > 0 else 0

            # 计算需要调整的仓位（以当前价格计算）
            target_value = target_units * self.position_value
            current_value = position_shares * price if position_shares > 0 else 0
            delta_value = target_value - current_value

            if abs(delta_value) > 0.01:  # 避免微小调整
                if delta_value > 0:
                    # 加仓
                    if cash >= delta_value:
                        # 买入股票
                        shares_to_buy = delta_value / price
                        old_shares = position_shares
                        position_shares += shares_to_buy
                        cash -= delta_value

                        # 更新买入均价（加权平均）
                        if position_shares > 0:
                            entry_price = ((old_shares * entry_price) + (shares_to_buy * price)) / position_shares

                        if target_units - current_units >= 2:  # 记录大额交易
                            trades.append({
                                'date': row['date'],
                                'type': 'BUY',
                                'price': price,
                                'units': target_units - current_units,
                                'value': delta_value,
                                'reason': f"仓位{current_units}→{target_units}成: {row.get('signal_reason', '')}"
                            })
                else:
                    # 减仓
                    shares_to_sell = abs(delta_value) / price
                    if position_shares >= shares_to_sell:
                        old_shares = position_shares
                        position_shares -= shares_to_sell
                        cash += abs(delta_value)

                        if old_shares > 0 and position_shares < old_shares:
                            # 更新买入均价（保持不变，因为只是减仓）
                            pass

                        if current_units - target_units >= 2:
                            trades.append({
                                'date': row['date'],
                                'type': 'SELL',
                                'price': price,
                                'units': current_units - target_units,
                                'value': abs(delta_value),
                                'reason': f"仓位{current_units}→{target_units}成: {row.get('signal_reason', '')}"
                            })

            # 记录绩效
            position_value = position_shares * price if position_shares > 0 else 0
            portfolio_value = cash + position_value

            # 计算当前仓位数（用于显示）
            position_units_display = int(position_value / self.position_value) if position_value > 0 else 0

            performance_records.append({
                'date': row['date'],
                'cash': cash,
                'position_units': position_units_display,
                'position_shares': position_shares,
                'position_value': position_value,
                'portfolio_value': portfolio_value,
                'price': price,
                'trend': row.get('trend', ''),
                'kdj_k': row.get('kdj_k', 0),
                'kdj_d': row.get('kdj_d', 0),
                'target_position': row.get('target_position', 0),
                'signal_reason': row.get('signal_reason', '')
            })

        return trades, pd.DataFrame(performance_records)

    def _calculate_metrics(self, trades: List[Dict], performance: pd.DataFrame,
                          df: pd.DataFrame) -> Dict:
        """
        计算回测指标

        Args:
            trades: 交易列表
            performance: 绩效记录DataFrame
            df: 原始数据

        Returns:
            指标字典
        """
        if len(performance) == 0:
            return {
                'total_return_pct': 0,
                'annual_return_pct': 0,
                'max_drawdown_pct': 0,
                'sharpe_ratio': 0,
                'total_trades': 0,
                'final_value': self.initial_capital
            }

        # 最终资产
        final_value = performance['portfolio_value'].iloc[-1]

        # 总收益率
        total_return_pct = (final_value - self.initial_capital) / self.initial_capital * 100

        # 年化收益率
        if len(performance) > 1:
            # 计算交易日数量
            trading_days = len(performance)
            years = trading_days / 252  # 假设每年252个交易日
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

        # 胜率（计算每次交易的盈亏）
        buy_trades = [t for t in trades if t['type'] == 'BUY']
        sell_trades = [t for t in trades if t['type'] == 'SELL']
        win_rate = 0
        if len(sell_trades) > 0:
            # 简化计算：假设买卖是配对的
            wins = 0  # 这里需要更复杂的配对逻辑，暂时简化
            win_rate = wins / len(sell_trades) * 100 if len(sell_trades) > 0 else 0

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
            'win_rate_pct': round(win_rate, 2),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades)
        }
