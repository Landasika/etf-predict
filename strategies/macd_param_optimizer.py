"""
MACD Parameter Optimizer

使用网格搜索优化MACD参数（macd_fast, macd_slow, macd_signal）
目标：最大化近一年收益率

优化策略：
- 两阶段网格搜索（粗粒度 + 精细搜索）
- 参数约束：slow > fast + 5, signal < fast
- 适应度函数：近一年收益率
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_etf_daily_data
from strategies.backtester import MACDBacktester
from strategies.strategies import get_strategy_params


class MACDParamOptimizer:
    """MACD 参数优化器 - 使用网格搜索"""

    def __init__(self, etf_code: str, lookback_days: int = 365):
        """
        初始化优化器

        Args:
            etf_code: ETF代码 (如 '510330.SH')
            lookback_days: 优化回溯天数（默认365天）
        """
        self.etf_code = etf_code
        self.lookback_days = lookback_days

        # 参数搜索空间
        self.param_ranges = {
            'macd_fast': (5, 20),
            'macd_slow': (15, 40),
            'macd_signal': (3, 12)
        }

    def optimize(self) -> Dict:
        """
        执行两阶段优化

        Returns:
            优化结果字典，包含最优参数和性能指标
        """
        # 1. 加载近一年数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_days)

        # 传递 start_str 和 end_str，加载时会返回实际可用数据
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        df = get_etf_daily_data(self.etf_code, start_str, end_str)

        if df is None or len(df) < 200:
            raise ValueError("数据不足，至少需要200天数据")

        # 转换为 DataFrame
        if isinstance(df, list):
            df = pd.DataFrame(df)

        # 重命名列
        if 'trade_date' in df.columns:
            df = df.rename(columns={'trade_date': 'date'})
        elif 'cal_date' in df.columns:
            df = df.rename(columns={'cal_date': 'date'})

        # 确保日期列是字符串格式
        if 'date' in df.columns:
            df['date'] = df['date'].astype(str)

        if len(df) < 200:
            raise ValueError("数据不足，至少需要200天数据")

        # 2. 第一阶段：粗粒度搜索
        print("开始粗粒度网格搜索...")
        best_params = self._coarse_search(df)
        print(f"粗搜索最优参数: {best_params}")

        # 3. 第二阶段：精细搜索
        print("开始精细网格搜索...")
        best_params = self._fine_search(df, best_params)
        print(f"精细搜索最优参数: {best_params}")

        # 4. 使用最优参数运行完整回测
        aggressive_params = get_strategy_params('aggressive')
        # 更新MACD参数
        aggressive_params['macd_fast'] = best_params['macd_fast']
        aggressive_params['macd_slow'] = best_params['macd_slow']
        aggressive_params['macd_signal'] = best_params['macd_signal']

        # 使用与前端一致的回测器参数（激进策略）
        backtester = MACDBacktester(
            initial_capital=2000,
            sell_fee=0.005,
            num_positions=10,
            stop_loss_pct=0.05,      # 5%止损（与前端一致）
            take_profit_pct1=0.10,   # 10%止盈（与前端一致）
            take_profit_pct2=0.20    # 20%止盈（与前端一致）
        )
        result = backtester.run_backtest(
            self.etf_code,
            strategy_params=aggressive_params,
            start_date=start_date.strftime('%Y%m%d'),
            end_date=None  # 使用所有可用数据，与前端回测一致
        )

        # 提取关键指标
        metrics = result['metrics']

        # 获取实际使用的日期范围
        performance = result.get('performance', [])
        if performance and len(performance) > 0:
            actual_start = performance[0]['date']
            actual_end = performance[-1]['date']
        else:
            actual_start = start_date.strftime('%Y-%m-%d')
            actual_end = end_date.strftime('%Y-%m-%d')

        return {
            'best_params': best_params,
            'metrics': {
                'total_return_pct': round(metrics['total_return_pct'], 2),
                'sharpe_ratio': round(metrics['sharpe_ratio'], 2),
                'max_drawdown_pct': round(metrics['max_drawdown'] * 100, 2),  # 转换为百分比
                'win_rate': round(metrics['win_rate'], 2),
                'total_trades': metrics['total_trades']
            },
            'data_period': {
                'start': actual_start,
                'end': actual_end,
                'days': len(df)
            },
            'aggressive_params': aggressive_params
        }

    def _load_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        加载ETF日线数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with OHLCV data
        """
        # 格式化日期为字符串 YYYYMMDD
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')

        # 加载数据
        df = get_etf_daily_data(
            self.etf_code,
            start_str,
            end_str
        )

        if df is None or len(df) == 0:
            raise ValueError(f"无法获取 {self.etf_code} 的数据 (日期范围: {start_str} - {end_str})")

        # 转换为DataFrame
        if isinstance(df, list):
            df = pd.DataFrame(df)

        # 重命名列
        if 'trade_date' in df.columns:
            df = df.rename(columns={'trade_date': 'date'})
        elif 'cal_date' in df.columns:
            df = df.rename(columns={'cal_date': 'date'})

        # 确保日期列是字符串格式
        if 'date' in df.columns:
            df['date'] = df['date'].astype(str)

        return df

    def _coarse_search(self, df: pd.DataFrame) -> Dict:
        """
        粗粒度网格搜索

        搜索步长：
        - fast: 3 (5, 8, 11, 14, 17, 20)
        - slow: 5 (15, 20, 25, 30, 35, 40)
        - signal: 2 (3, 5, 7, 9, 11)

        Args:
            df: 价格数据

        Returns:
            最优参数字典
        """
        best_params = None
        best_fitness = -np.inf
        total_combinations = 0

        # 参数范围限制
        fast_min, fast_max = self.param_ranges['macd_fast']
        slow_min, slow_max = self.param_ranges['macd_slow']
        signal_min, signal_max = self.param_ranges['macd_signal']

        # 粗搜索步长
        for fast in range(fast_min, fast_max + 1, 3):
            for slow in range(fast + 8, slow_max + 1, 5):
                # signal 必须小于 fast 且在范围内
                max_signal = min(fast - 1, signal_max)
                if max_signal < signal_min:
                    continue
                for signal in range(signal_min, max_signal + 1, 2):
                    params = {
                        'macd_fast': fast,
                        'macd_slow': slow,
                        'macd_signal': signal
                    }

                    fitness = self._evaluate_params(df, params)
                    total_combinations += 1

                    if fitness > best_fitness:
                        best_fitness = fitness
                        best_params = params
                        print(f"  新最优: {params} -> 收益率: {fitness:.2f}%")

        print(f"粗搜索完成，测试了 {total_combinations} 组参数")
        return best_params

    def _fine_search(self, df: pd.DataFrame, coarse_params: Dict) -> Dict:
        """
        在最优区域精细搜索

        搜索范围：最优值 ± 3
        搜索步长：1

        Args:
            df: 价格数据
            coarse_params: 粗搜索得到的最优参数

        Returns:
            最优参数字典
        """
        best_params = coarse_params
        best_fitness = self._evaluate_params(df, coarse_params)

        # 参数范围限制
        fast_min, fast_max = self.param_ranges['macd_fast']
        slow_min, slow_max = self.param_ranges['macd_slow']
        signal_min, signal_max = self.param_ranges['macd_signal']

        # 精搜索范围：最优值 ± 3，但必须在参数范围内
        fast_range = range(
            max(fast_min, coarse_params['macd_fast'] - 3),
            min(fast_max, coarse_params['macd_fast'] + 4)
        )
        slow_range = range(
            max(slow_min, coarse_params['macd_slow'] - 5),
            min(slow_max, coarse_params['macd_slow'] + 6)
        )
        signal_range = range(
            max(signal_min, coarse_params['macd_signal'] - 2),
            min(signal_max, coarse_params['macd_signal'] + 3)
        )

        total_combinations = 0

        for fast in fast_range:
            for slow in slow_range:
                # 约束：slow必须大于fast + 5
                if slow <= fast + 5:
                    continue
                for signal in signal_range:
                    # 约束：signal必须小于fast
                    if signal >= fast:
                        continue

                    params = {
                        'macd_fast': fast,
                        'macd_slow': slow,
                        'macd_signal': signal
                    }

                    fitness = self._evaluate_params(df, params)
                    total_combinations += 1

                    if fitness > best_fitness:
                        best_fitness = fitness
                        best_params = params
                        print(f"  新最优: {params} -> 收益率: {fitness:.2f}%")

        print(f"精细搜索完成，测试了 {total_combinations} 组参数")
        return best_params

    def _evaluate_params(self, df: pd.DataFrame, params: Dict) -> float:
        """
        评估参数组合的适应度（近一年收益率）

        Args:
            df: 价格数据
            params: MACD参数字典

        Returns:
            收益率百分比
        """
        # 获取激进策略参数并更新MACD参数
        test_params = get_strategy_params('aggressive')
        test_params['macd_fast'] = params['macd_fast']
        test_params['macd_slow'] = params['macd_slow']
        test_params['macd_signal'] = params['macd_signal']

        # 运行回测（使用与前端一致的激进策略参数）
        try:
            backtester = MACDBacktester(
                initial_capital=2000,
                sell_fee=0.005,
                num_positions=10,
                stop_loss_pct=0.05,      # 5%止损（与前端一致）
                take_profit_pct1=0.10,   # 10%止盈（与前端一致）
                take_profit_pct2=0.20    # 20%止盈（与前端一致）
            )
            result = backtester.run_backtest(
                self.etf_code,
                strategy_params=test_params,
                start_date=df['date'].iloc[0],
                end_date=df['date'].iloc[-1]
            )

            return result['metrics']['total_return_pct']
        except Exception as e:
            print(f"  参数 {params} 回测失败: {e}")
            return -np.inf


# 便捷函数：直接优化并返回结果
def optimize_macd_params(etf_code: str, lookback_days: int = 365) -> Dict:
    """
    优化ETF的MACD参数

    Args:
        etf_code: ETF代码
        lookback_days: 优化回溯天数（默认365天）

    Returns:
        优化结果字典
    """
    optimizer = MACDParamOptimizer(etf_code, lookback_days)
    return optimizer.optimize()


if __name__ == '__main__':
    # 测试代码
    import sys

    if len(sys.argv) < 2:
        print("用法: python macd_param_optimizer.py <ETF代码> [回溯天数]")
        print("示例: python macd_param_optimizer.py 510330.SH 365")
        sys.exit(1)

    etf_code = sys.argv[1]
    lookback_days = int(sys.argv[2]) if len(sys.argv) > 2 else 365

    print(f"开始优化 {etf_code} 的MACD参数（回溯 {lookback_days} 天）")
    print("=" * 60)

    result = optimize_macd_params(etf_code, lookback_days)

    print("\n" + "=" * 60)
    print("优化完成！")
    print(f"最优MACD参数:")
    print(f"  - Fast:  {result['best_params']['macd_fast']}")
    print(f"  - Slow:  {result['best_params']['macd_slow']}")
    print(f"  - Signal: {result['best_params']['macd_signal']}")
    print(f"\n性能指标:")
    print(f"  - 收益率:    {result['metrics']['total_return_pct']:.2f}%")
    print(f"  - 夏普比率:  {result['metrics']['sharpe_ratio']:.2f}")
    print(f"  - 最大回撤:  {result['metrics']['max_drawdown_pct']:.2f}%")
    print(f"  - 胜率:      {result['metrics']['win_rate']:.2%}")
    print(f"  - 交易次数:  {result['metrics']['total_trades']}")
    print(f"\n数据期间: {result['data_period']['start']} 至 {result['data_period']['end']}")
    print(f"数据天数: {result['data_period']['days']} 天")
