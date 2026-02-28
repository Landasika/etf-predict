"""
MACD+KDJ离散仓位系统参数优化器

使用网格搜索优化MACD和KDJ参数
目标：最大化近一年收益率

优化策略：
- 两阶段网格搜索（粗粒度 + 精细搜索）
- 参数约束：slow > fast + 5, signal < fast
- 适应度函数：近一年收益率

可优化参数：
- MACD: macd_fast, macd_slow, macd_signal
- KDJ: kdj_n, kdj_m1, kdj_m2
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_etf_daily_data
from strategies.macd_kdj_discrete_backtester import MACDKDJDiscreteBacktester


class MACDKDJDiscreteParamOptimizer:
    """MACD+KDJ离散仓位系统参数优化器 - 使用网格搜索"""

    def __init__(self, etf_code: str, lookback_days: int = 365):
        """
        初始化优化器

        Args:
            etf_code: ETF代码 (如 '510330.SH')
            lookback_days: 优化回溯天数（默认365天）
        """
        self.etf_code = etf_code
        self.lookback_days = lookback_days

        # MACD参数搜索空间
        self.macd_ranges = {
            'macd_fast': (8, 25),
            'macd_slow': (20, 45),
            'macd_signal': (3, 15)
        }

        # KDJ参数搜索空间
        self.kdj_ranges = {
            'kdj_n': (5, 15),
            'kdj_m1': (2, 5),
            'kdj_m2': (2, 5)
        }

    def optimize(self, optimize_kdj: bool = True) -> Dict:
        """
        执行两阶段优化

        Args:
            optimize_kdj: 是否优化KDJ参数（默认True，如果只优化MACD设为False）

        Returns:
            优化结果字典，包含最优参数和性能指标
        """
        # 1. 加载数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_days)

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
        best_params = self._coarse_search(df, optimize_kdj)
        print(f"粗搜索最优参数: {best_params}")

        # 3. 第二阶段：精细搜索
        print("开始精细网格搜索...")
        best_params = self._fine_search(df, best_params, optimize_kdj)
        print(f"精细搜索最优参数: {best_params}")

        # 4. 使用最优参数运行完整回测
        backtester = MACDKDJDiscreteBacktester(
            initial_capital=2000,
            total_positions=10
        )
        result = backtester.run_backtest(
            self.etf_code,
            start_date=start_date.strftime('%Y%m%d'),
            end_date=None,
            strategy_params=best_params
        )

        # 提取关键指标
        metrics = result.get('metrics', {})

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
                'total_return_pct': round(metrics.get('total_return_pct', 0), 2),
                'sharpe_ratio': round(metrics.get('sharpe_ratio', 0), 2),
                'max_drawdown_pct': round(metrics.get('max_drawdown_pct', 0), 2),
                'win_rate_pct': round(metrics.get('win_rate_pct', 0), 2),
                'total_trades': metrics.get('total_trades', 0)
            },
            'data_period': {
                'start': actual_start,
                'end': actual_end,
                'days': len(df)
            }
        }

    def _coarse_search(self, df: pd.DataFrame, optimize_kdj: bool) -> Dict:
        """
        粗粒度网格搜索

        搜索步长：
        - fast: 3
        - slow: 5
        - signal: 2
        - kdj_n: 3 (如果优化KDJ)
        - kdj_m1, m2: 1 (如果优化KDJ)

        Args:
            df: 价格数据
            optimize_kdj: 是否优化KDJ参数

        Returns:
            最优参数字典
        """
        best_params = None
        best_fitness = -np.inf
        total_combinations = 0

        # MACD参数范围
        fast_min, fast_max = self.macd_ranges['macd_fast']
        slow_min, slow_max = self.macd_ranges['macd_slow']
        signal_min, signal_max = self.macd_ranges['macd_signal']

        # KDJ参数范围（如果要优化）
        if optimize_kdj:
            n_min, n_max = self.kdj_ranges['kdj_n']
            m1_min, m1_max = self.kdj_ranges['kdj_m1']
            m2_min, m2_max = self.kdj_ranges['kdj_m2']

        # 粗搜索步长
        for fast in range(fast_min, fast_max + 1, 3):
            for slow in range(fast + 8, slow_max + 1, 5):
                # signal 可以大于或等于 fast (放宽传统MACD约束)
                for signal in range(signal_min, signal_max + 1, 2):
                    if optimize_kdj:
                        # 同时优化KDJ参数
                        for n in range(n_min, n_max + 1, 3):
                            for m1 in range(m1_min, m1_max + 1):
                                for m2 in range(m2_min, m2_max + 1):
                                    params = {
                                        'macd_fast': fast,
                                        'macd_slow': slow,
                                        'macd_signal': signal,
                                        'kdj_n': n,
                                        'kdj_m1': m1,
                                        'kdj_m2': m2
                                    }

                                    fitness = self._evaluate_params(df, params, optimize_kdj)
                                    total_combinations += 1

                                    if fitness > best_fitness:
                                        best_fitness = fitness
                                        best_params = params
                                        print(f"  新最优: {params} -> 收益率: {fitness:.2f}%")
                    else:
                        # 只优化MACD参数
                        params = {
                            'macd_fast': fast,
                            'macd_slow': slow,
                            'macd_signal': signal,
                            'kdj_n': 9,
                            'kdj_m1': 3,
                            'kdj_m2': 3
                        }

                        fitness = self._evaluate_params(df, params, optimize_kdj)
                        total_combinations += 1

                        if fitness > best_fitness:
                            best_fitness = fitness
                            best_params = params
                            print(f"  新最优: {params} -> 收益率: {fitness:.2f}%")

        print(f"粗搜索完成，测试了 {total_combinations} 组参数")
        return best_params

    def _fine_search(self, df: pd.DataFrame, coarse_params: Dict, optimize_kdj: bool) -> Dict:
        """
        在最优区域精细搜索

        搜索范围：最优值 ± 小范围
        搜索步长：1

        Args:
            df: 价格数据
            coarse_params: 粗搜索得到的最优参数
            optimize_kdj: 是否优化KDJ参数

        Returns:
            最优参数字典
        """
        best_params = coarse_params
        best_fitness = self._evaluate_params(df, coarse_params, optimize_kdj)

        # MACD参数范围
        fast_min, fast_max = self.macd_ranges['macd_fast']
        slow_min, slow_max = self.macd_ranges['macd_slow']
        signal_min, signal_max = self.macd_ranges['macd_signal']

        # KDJ参数范围
        n_min, n_max = self.kdj_ranges['kdj_n']
        m1_min, m1_max = self.kdj_ranges['kdj_m1']
        m2_min, m2_max = self.kdj_ranges['kdj_m2']

        # 精搜索范围
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

        if optimize_kdj:
            n_range = range(
                max(n_min, coarse_params['kdj_n'] - 2),
                min(n_max, coarse_params['kdj_n'] + 3)
            )
            m1_range = range(
                max(m1_min, coarse_params['kdj_m1'] - 1),
                min(m1_max, coarse_params['kdj_m1'] + 2)
            )
            m2_range = range(
                max(m2_min, coarse_params['kdj_m2'] - 1),
                min(m2_max, coarse_params['kdj_m2'] + 2)
            )
        else:
            n_range = [coarse_params['kdj_n']]
            m1_range = [coarse_params['kdj_m1']]
            m2_range = [coarse_params['kdj_m2']]

        total_combinations = 0

        for fast in fast_range:
            for slow in slow_range:
                if slow <= fast + 5:
                    continue
                for signal in signal_range:
                    # signal 可以 >= fast (放宽传统MACD约束)
                    for n in n_range:
                        for m1 in m1_range:
                            for m2 in m2_range:
                                params = {
                                    'macd_fast': fast,
                                    'macd_slow': slow,
                                    'macd_signal': signal,
                                    'kdj_n': n,
                                    'kdj_m1': m1,
                                    'kdj_m2': m2
                                }

                                fitness = self._evaluate_params(df, params, optimize_kdj)
                                total_combinations += 1

                                if fitness > best_fitness:
                                    best_fitness = fitness
                                    best_params = params
                                    print(f"  新最优: {params} -> 收益率: {fitness:.2f}%")

        print(f"精细搜索完成，测试了 {total_combinations} 组参数")
        return best_params

    def _evaluate_params(self, df: pd.DataFrame, params: Dict, optimize_kdj: bool) -> float:
        """
        评估参数组合的适应度（近一年收益率）

        Args:
            df: 价格数据
            params: 参数字典
            optimize_kdj: 是否使用了KDJ参数

        Returns:
            收益率百分比
        """
        try:
            backtester = MACDKDJDiscreteBacktester(
                initial_capital=2000,
                total_positions=10
            )
            result = backtester.run_backtest(
                self.etf_code,
                start_date=df['date'].iloc[0],
                end_date=df['date'].iloc[-1],
                strategy_params=params
            )

            if result.get('success'):
                return result['metrics'].get('total_return_pct', -np.inf)
            else:
                return -np.inf
        except Exception as e:
            print(f"  参数 {params} 回测失败: {e}")
            return -np.inf


# 便捷函数：直接优化并返回结果
def optimize_macd_kdj_discrete_params(etf_code: str, lookback_days: int = 365, optimize_kdj: bool = True) -> Dict:
    """
    优化ETF的MACD+KDJ离散仓位系统参数

    Args:
        etf_code: ETF代码
        lookback_days: 优化回溯天数（默认365天）
        optimize_kdj: 是否优化KDJ参数（默认True）

    Returns:
        优化结果字典
    """
    optimizer = MACDKDJDiscreteParamOptimizer(etf_code, lookback_days)
    return optimizer.optimize(optimize_kdj)


if __name__ == '__main__':
    # 测试代码
    import sys

    if len(sys.argv) < 2:
        print("用法: python macd_kdj_discrete_param_optimizer.py <ETF代码> [回溯天数] [是否优化KDJ: 1/0]")
        print("示例: python macd_kdj_discrete_param_optimizer.py 159300.SZ 365 1")
        sys.exit(1)

    etf_code = sys.argv[1]
    lookback_days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    optimize_kdj = True if len(sys.argv) <= 3 or sys.argv[3] == '1' else False

    print(f"开始优化 {etf_code} 的MACD+KDJ离散参数（回溯 {lookback_days} 天，优化KDJ: {optimize_kdj}）")
    print("=" * 60)

    result = optimize_macd_kdj_discrete_params(etf_code, lookback_days, optimize_kdj)

    print("\n" + "=" * 60)
    print("优化完成！")
    print(f"最优MACD参数:")
    print(f"  - Fast:   {result['best_params']['macd_fast']}")
    print(f"  - Slow:   {result['best_params']['macd_slow']}")
    print(f"  - Signal: {result['best_params']['macd_signal']}")
    if optimize_kdj:
        print(f"最优KDJ参数:")
        print(f"  - N:      {result['best_params']['kdj_n']}")
        print(f"  - M1:     {result['best_params']['kdj_m1']}")
        print(f"  - M2:     {result['best_params']['kdj_m2']}")
    print(f"\n性能指标:")
    print(f"  - 收益率:    {result['metrics']['total_return_pct']:.2f}%")
    print(f"  - 夏普比率:  {result['metrics']['sharpe_ratio']:.2f}")
    print(f"  - 最大回撤:  {result['metrics']['max_drawdown_pct']:.2f}%")
    print(f"  - 胜率:      {result['metrics']['win_rate_pct']:.2f}%")
    print(f"  - 交易次数:  {result['metrics']['total_trades']}")
    print(f"\n数据期间: {result['data_period']['start']} 至 {result['data_period']['end']}")
    print(f"数据天数: {result['data_period']['days']} 天")
