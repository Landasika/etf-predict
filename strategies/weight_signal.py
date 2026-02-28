"""
Weight-Based Signal Generator

Uses optimized factor weights to generate trading signals for short-term trading.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from .factors import FactorBuilder


class WeightedSignalGenerator:
    """
    基于优化权重的信号生成器

    使用优化算法找到的最佳因子权重组合来生成交易信号。
    """

    def __init__(self,
                 weights: Dict[str, float] = None,
                 factor_groups: Dict[str, List[str]] = None,
                 signal_threshold: float = 0.5,
                 use_normalization: bool = True):
        """
        初始化信号生成器

        Args:
            weights: 因子权重字典
            factor_groups: 因子分组
            signal_threshold: 信号阈值（大于此值产生买入信号）
            use_normalization: 是否对因子进行标准化
        """
        self.weights = weights or {}
        self.factor_groups = factor_groups or self._get_default_factor_groups()
        self.signal_threshold = signal_threshold
        self.use_normalization = use_normalization

        # 展平所有因子
        self.all_factors = []
        for group_factors in self.factor_groups.values():
            self.all_factors.extend(group_factors)

        self.factor_builder = FactorBuilder()

        # 存储标准化参数
        self.scaler_params = {}

    def _get_default_factor_groups(self) -> Dict[str, List[str]]:
        """获取默认因子分组"""
        return {
            'macd': ['f_macd_trend', 'f_macd_cross', 'f_macd_hist_slope'],
            'kdj': ['f_k_oversold', 'f_k_overbought', 'f_k_slope', 'f_kd_cross'],
            'boll': ['f_boll_lower_touch', 'f_boll_upper_touch', 'f_boll_position'],
            'volume': ['f_volume_ratio', 'f_volume_spike', 'f_vpt'],
            'trend': ['f_ma60_trend', 'f_price_momentum', 'f_atr_volatility']
        }

    def generate_signals(self,
                        df: pd.DataFrame,
                        weights: Dict[str, float] = None) -> pd.DataFrame:
        """
        生成加权信号

        Args:
            df: 原始OHLCV数据
            weights: 因子权重（如果提供，覆盖初始化的权重）

        Returns:
            DataFrame with added columns:
            - signal_strength: 加权信号强度（连续值）
            - signal_type: BUY/SELL/HOLD
            - signal_direction: LONG/SHORT/NEUTRAL
        """
        df = df.copy()

        # 使用提供的权重或默认权重
        if weights is not None:
            self.weights = weights

        # 构建因子矩阵
        df = self.factor_builder.build_factor_matrix(df)

        # 标准化因子（如果启用）
        if self.use_normalization:
            df = self._normalize_factors(df)

        # 计算加权信号强度
        df['signal_strength'] = self._calculate_weighted_signal(df)

        # 生成信号类型
        df = self._generate_signal_types(df)

        return df

    def _normalize_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化因子（Z-score标准化）

        使用滚动窗口计算均值和标准差，避免未来函数
        """
        for factor in self.all_factors:
            if factor not in df.columns:
                continue

            # 使用60日滚动窗口标准化
            rolling_mean = df[factor].rolling(60, min_periods=20).mean()
            rolling_std = df[factor].rolling(60, min_periods=20).std()

            # 避免除零
            rolling_std = rolling_std.replace(0, 1)

            # 标准化
            normalized = (df[factor] - rolling_mean) / rolling_std

            # 限制在[-3, 3]范围内，避免极端值
            normalized = normalized.clip(-3, 3)

            df[f'{factor}_norm'] = normalized

        return df

    def _calculate_weighted_signal(self, df: pd.DataFrame) -> pd.Series:
        """
        计算加权信号强度

        signal_strength = sum(factor_i * weight_i)
        """
        signal_strength = pd.Series(0.0, index=df.index)

        for factor, weight in self.weights.items():
            # 检查是否使用标准化因子
            if self.use_normalization and f'{factor}_norm' in df.columns:
                factor_values = df[f'{factor}_norm']
            elif factor in df.columns:
                factor_values = df[factor]
            else:
                continue

            signal_strength += factor_values.fillna(0) * weight

        return signal_strength

    def _generate_signal_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成信号类型（BUY/SELL/HOLD）
        """
        # 初始化
        df['signal_type'] = 'HOLD'
        df['signal_direction'] = 'NEUTRAL'

        # 买入信号
        buy_mask = df['signal_strength'] > self.signal_threshold
        df.loc[buy_mask, 'signal_type'] = 'BUY'
        df.loc[buy_mask, 'signal_direction'] = 'LONG'

        # 卖出信号
        sell_mask = df['signal_strength'] < -self.signal_threshold
        df.loc[sell_mask, 'signal_type'] = 'SELL'
        df.loc[sell_mask, 'signal_direction'] = 'SHORT'

        return df

    def get_top_signals(self,
                       df: pd.DataFrame,
                       top_n: int = 5) -> pd.DataFrame:
        """
        获取信号强度最高的N个交易日

        Args:
            df: 包含信号的DataFrame
            top_n: 返回前N个

        Returns:
            DataFrame with top signals
        """
        df_sorted = df.sort_values('signal_strength', ascending=False)
        return df_sorted.head(top_n)

    def analyze_factor_contribution(self,
                                   df: pd.DataFrame,
                                   date: str = None) -> pd.DataFrame:
        """
        分析各因子对信号的贡献度

        Args:
            df: 包含因子的DataFrame
            date: 特定日期（None则分析全部）

        Returns:
            DataFrame with factor contributions
        """
        if date:
            df_analyze = df[df['date'] == date]
        else:
            df_analyze = df.tail(1)

        if len(df_analyze) == 0:
            return pd.DataFrame()

        contributions = []
        for factor, weight in self.weights.items():
            if self.use_normalization and f'{factor}_norm' in df_analyze.columns:
                factor_value = df_analyze[f'{factor}_norm'].iloc[0]
            elif factor in df_analyze.columns:
                factor_value = df_analyze[factor].iloc[0]
            else:
                continue

            contribution = factor_value * weight

            contributions.append({
                'factor': factor,
                'weight': weight,
                'value': factor_value,
                'contribution': contribution
            })

        contrib_df = pd.DataFrame(contributions)
        contrib_df = contrib_df.sort_values('contribution', ascending=False)

        return contrib_df

    def optimize_weights(self,
                        df: pd.DataFrame,
                        objective: str = 'total_return',
                        holding_period: int = 1,
                        method: str = 'genetic',
                        **kwargs) -> Dict:
        """
        优化因子权重

        Args:
            df: 历史数据
            objective: 优化目标
            holding_period: 持仓天数
            method: 优化方法（genetic/grid）
            **kwargs: 传递给优化器的参数

        Returns:
            优化结果字典
        """
        from .optimizer import optimize_for_short_term

        # 构建因子矩阵
        df_factors = self.factor_builder.build_factor_matrix(df)

        # 运行优化
        result = optimize_for_short_term(
            df=df_factors,
            holding_period=holding_period,
            objective=objective,
            method=method,
            factor_groups=self.factor_groups,
            **kwargs
        )

        # 更新权重
        self.weights = result.best_weights

        return {
            'weights': result.best_weights,
            'fitness': result.best_fitness,
            'metrics': result.best_metrics,
            'history': result.history
        }

    def get_signal_strength_range(self,
                                  df: pd.DataFrame,
                                  window: int = 60) -> pd.DataFrame:
        """
        计算信号强度的统计范围

        Args:
            df: 包含signal_strength的DataFrame
            window: 统计窗口

        Returns:
            DataFrame with signal statistics
        """
        stats = df['signal_strength'].rolling(window).agg([
            ('mean', 'mean'),
            ('std', 'std'),
            ('min', 'min'),
            ('max', 'max'),
            ('median', 'median')
        ])

        # 计算百分位数
        df['signal_strength_rolling'] = df['signal_strength'].rolling(window)
        stats['percentile_25'] = df['signal_strength'].rolling(window).quantile(0.25)
        stats['percentile_75'] = df['signal_strength'].rolling(window).quantile(0.75)

        return stats

    def adjust_threshold_by_percentile(self,
                                      df: pd.DataFrame,
                                      percentile: float = 0.75) -> float:
        """
        基于历史百分位数调整信号阈值

        Args:
            df: 包含signal_strength的DataFrame
            percentile: 目标百分位数（0.75表示只在前25%的信号时交易）

        Returns:
            调整后的阈值
        """
        if 'signal_strength' not in df.columns:
            df = self.generate_signals(df)

        threshold = df['signal_strength'].quantile(1 - percentile)
        return threshold


class AdaptiveWeightedSignalGenerator(WeightedSignalGenerator):
    """
    自适应权重信号生成器

    定期重新优化权重以适应市场变化。
    """

    def __init__(self,
                 weights: Dict[str, float] = None,
                 factor_groups: Dict[str, List[str]] = None,
                 rebalance_freq: int = 20,
                 lookback_period: int = 252):
        """
        初始化自适应信号生成器

        Args:
            weights: 初始权重
            factor_groups: 因子分组
            rebalance_freq: 重新平衡频率（天）
            lookback_period: 优化回看期（天）
        """
        super().__init__(weights, factor_groups)
        self.rebalance_freq = rebalance_freq
        self.lookback_period = lookback_period
        self.weight_history = []

    def generate_signals_adaptive(self,
                                 df: pd.DataFrame,
                                 optimize: bool = True) -> pd.DataFrame:
        """
        生成自适应信号（定期重新优化权重）

        Args:
            df: 历史数据
            optimize: 是否执行优化

        Returns:
            DataFrame with signals
        """
        df = df.copy()

        # 构建因子矩阵
        df = self.factor_builder.build_factor_matrix(df)

        # 初始化信号列
        df['signal_strength'] = 0.0
        df['signal_type'] = 'HOLD'

        # 使用初始权重
        current_weights = self.weights.copy()

        # 滚动窗口生成信号
        for i in range(max(self.lookback_period, 60), len(df)):
            # 定期重新优化权重
            if optimize and i % self.rebalance_freq == 0:
                # 使用历史数据优化
                hist_df = df.iloc[i-self.lookback_period:i].copy()

                try:
                    from .optimizer import optimize_for_short_term
                    result = optimize_for_short_term(
                        df=hist_df,
                        holding_period=1,
                        objective='total_return',
                        method='genetic',
                        factor_groups=self.factor_groups,
                        population_size=20,
                        generations=50
                    )

                    current_weights = result.best_weights
                    self.weight_history.append({
                        'date': df.loc[df.index[i], 'date'],
                        'weights': current_weights.copy()
                    })
                except Exception as e:
                    print(f"权重优化失败: {e}")
                    # 保持当前权重

            # 计算当前行的信号强度
            signal_strength = 0.0
            for factor, weight in current_weights.items():
                if factor in df.columns:
                    signal_strength += df.loc[df.index[i], factor] * weight

            df.loc[df.index[i], 'signal_strength'] = signal_strength

        # 生成信号类型
        df = self._generate_signal_types(df)

        return df


def create_equal_weight_signal(factor_groups: Dict[str, List[str]] = None) -> WeightedSignalGenerator:
    """
    创建等权重信号生成器（基准）

    Args:
        factor_groups: 因子分组

    Returns:
        WeightedSignalGenerator
    """
    if factor_groups is None:
        generator = WeightedSignalGenerator()
    else:
        generator = WeightedSignalGenerator(factor_groups=factor_groups)

    # 设置等权重
    weights = {}
    for factor in generator.all_factors:
        weights[factor] = 1.0 / len(generator.all_factors)

    generator.weights = weights

    return generator
