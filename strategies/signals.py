"""
MACD Signal Generator

Implements the four practical MACD trading methods:
1. Zero-axis trend determination
2. Multi-period resonance for precise entry points
3. MA60 filtering for invalid signals
4. Divergence detection for reversals
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from .indicators import MACDIndicators


class MACDSignalGenerator:
    """MACD four practical methods signal generator"""

    def __init__(self, params: Dict = None):
        """
        Initialize strategy parameters

        Args:
            params: Strategy parameter dictionary (uses defaults if None)
        """
        self.params = params or self.default_params()

    @staticmethod
    def default_params() -> Dict:
        """
        Default parameter configuration

        Returns:
            Dictionary with default strategy parameters
        """
        return {
            # Zero-axis trend filtering
            'zero_axis_filter': True,          # Enable zero-axis filtering
            'require_zero_above': True,        # Require DIF above zero for buys

            # Period resonance (multi-timeframe)
            'enable_resonance': False,         # Enable period resonance
            'major_period': 'weekly',          # Major period: weekly/daily
            'minor_period': 'daily',           # Minor period: daily/hourly

            # MA60 filtering
            'ma60_filter': True,               # Enable MA60 filtering
            'ma60_tolerance': 0.02,            # MA60 tolerance (2%)

            # Divergence signals
            'enable_divergence': True,         # Enable divergence signals
            'divergence_confirm': True,        # Require confirmation signal
            'min_divergence_count': 2,         # Minimum divergence occurrences

            # Signal strength
            'volume_confirm': False,           # Require volume confirmation
            'volume_increase_min': 0.3,        # Minimum volume increase (30%)
            'volume_increase_max': 0.5,        # Maximum volume increase (50%)

            # Pattern recognition
            'duck_bill_enable': True,          # Enable duck-bill pattern
            'inverted_duck_enable': True,      # Enable inverted duck-bill pattern

            # 新增：布林带过滤（默认关闭）
            'boll_filter': False,
            'boll_max_position': 0.7,
            'boll_min_position': 0.3,

            # 新增：波动率过滤（默认关闭）
            'volatility_filter': False,
            'low_vol_threshold': 0.015,
            'high_vol_threshold': 0.04
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate complete trading signals

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with added columns:
            - signal_type: BUY/SELL/HOLD
            - signal_strength: -10 to +10
            - signal_reason: Explanation of signal
        """
        df = df.copy()

        # Calculate indicators with custom MACD parameters if provided
        macd_params = {}
        if 'macd_fast' in self.params:
            macd_params['fast'] = self.params['macd_fast']
        if 'macd_slow' in self.params:
            macd_params['slow'] = self.params['macd_slow']
        if 'macd_signal' in self.params:
            macd_params['signal'] = self.params['macd_signal']

        if macd_params:
            df = MACDIndicators.calculate_macd(df, **macd_params)
        else:
            df = MACDIndicators.calculate_macd(df)

        df = MACDIndicators.add_ma60(df)
        df = MACDIndicators.detect_divergence(df)
        df = MACDIndicators.calculate_atr(df)  # ATR用于波动率过滤

        # 添加布林带（如果启用）
        if self.params.get('boll_filter', False):
            df = MACDIndicators.calculate_boll(df)

        # Initialize signal columns
        df['signal_type'] = 'HOLD'
        df['signal_strength'] = 0
        df['signal_reason'] = ''

        # Generate various signals (in order of priority)
        df = self._zero_axis_signals(df)
        df = self._special_patterns(df)
        df = self._divergence_signals(df)
        df = self._crossover_signals(df)
        df = self._ma60_filter_signals(df)

        # 新增：布林带和波动率过滤
        df = self._advanced_filters(df)

        return df

    def _advanced_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        高级过滤器：布林带位置 + 波动率

        用于避免买在半山腰
        """
        df = df.copy()

        # ========== 布林带位置过滤 ==========
        if self.params.get('boll_filter', False):
            # 确保布林带已计算
            if 'boll_upper' not in df.columns:
                df = MACDIndicators.calculate_boll(df)

            boll_max = self.params.get('boll_max_position', 0.7)
            boll_min = self.params.get('boll_min_position', 0.3)

            # 计算布林带位置 (0=下轨, 1=上轨)
            boll_range = df['boll_upper'] - df['boll_lower']
            boll_position = (df['close'] - df['boll_lower']) / boll_range.replace(0, np.finfo(float).eps)

            # 过滤买入信号：不在合理位置的不买
            buy_invalid = (
                (df['signal_type'] == 'BUY') &
                ((boll_position > boll_max) | (boll_position < boll_min))
            )

            # 取消这些买入信号
            df.loc[buy_invalid, 'signal_type'] = 'HOLD'
            df.loc[buy_invalid, 'signal_strength'] = 0
            df.loc[buy_invalid, 'signal_reason'] = '布林带位置不佳'

        # ========== 波动率过滤 ==========
        if self.params.get('volatility_filter', False):
            # 确保ATR已计算
            if 'atr' not in df.columns:
                df = MACDIndicators.calculate_atr(df)

            low_vol = self.params.get('low_vol_threshold', 0.015)
            high_vol = self.params.get('high_vol_threshold', 0.04)

            # 计算ATR百分比
            atr_pct = df['atr'] / df['close']

            # 高波动期，降低买入信号强度
            high_vol_mask = (atr_pct > high_vol) & (df['signal_type'] == 'BUY')
            df.loc[high_vol_mask, 'signal_strength'] = \
                df.loc[high_vol_mask, 'signal_strength'] * 0.5

        return df

    def _zero_axis_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Method 1: Zero-axis trend determination signals

        Logic:
        - Above zero = Bullish trend, golden cross valid, death cross is mostly correction
        - Below zero = Bearish trend, golden cross is mostly rebound, death cross is real decline
        """
        if not self.params['zero_axis_filter']:
            return df

        # Golden cross above zero (air refueling)
        above_cross = (
            (df['macd_dif'].shift(1) <= df['macd_dea'].shift(1)) &
            (df['macd_dif'] > df['macd_dea']) &
            (df['macd_dif'] > 0)
        )

        df.loc[above_cross, 'signal_type'] = 'BUY'
        df.loc[above_cross, 'signal_strength'] = 8
        df.loc[above_cross, 'signal_reason'] = '零轴上方金叉(空中加油)'

        # Death cross below zero (accelerating decline)
        below_death = (
            (df['macd_dif'].shift(1) >= df['macd_dea'].shift(1)) &
            (df['macd_dif'] < df['macd_dea']) &
            (df['macd_dif'] < 0)
        )

        df.loc[below_death, 'signal_type'] = 'SELL'
        df.loc[below_death, 'signal_strength'] = -8
        df.loc[below_death, 'signal_reason'] = '零轴下方死叉(加速下跌)'

        return df

    def _crossover_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standard golden cross and death cross signals
        """
        # Only generate if not already set by higher priority signals
        no_signal = (df['signal_type'] == 'HOLD') | (df['signal_strength'].abs() < 6)

        # Golden cross: DIF crosses above DEA
        golden_cross = (
            (df['macd_dif'].shift(1) <= df['macd_dea'].shift(1)) &
            (df['macd_dif'] > df['macd_dea']) &
            no_signal
        )

        df.loc[golden_cross, 'signal_type'] = 'BUY'
        df.loc[golden_cross, 'signal_strength'] = 6
        df.loc[golden_cross, 'signal_reason'] = 'MACD金叉'

        # Death cross: DIF crosses below DEA
        death_cross = (
            (df['macd_dif'].shift(1) >= df['macd_dea'].shift(1)) &
            (df['macd_dif'] < df['macd_dea']) &
            no_signal
        )

        df.loc[death_cross, 'signal_type'] = 'SELL'
        df.loc[death_cross, 'signal_strength'] = -6
        df.loc[death_cross, 'signal_reason'] = 'MACD死叉'

        return df

    def _divergence_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Method 4: Top and bottom divergence signals

        Logic:
        - Bottom divergence: Price new low + MACD not new low + confirmation break
        - Top divergence: Price new high + MACD not new high + confirmation break
        """
        if not self.params['enable_divergence']:
            return df

        # Only process if no stronger signal exists
        no_signal = (df['signal_type'] == 'HOLD') | (df['signal_strength'].abs() < 7)

        # Bullish divergence buy (requires confirmation)
        bull_div = (df['bullish_divergence'] == 1) & no_signal

        if self.params['divergence_confirm']:
            # Require price breakout confirmation
            bull_div_confirm = bull_div & (
                df['close'] > df['close'].shift(5)
            )
        else:
            bull_div_confirm = bull_div

        df.loc[bull_div_confirm, 'signal_type'] = 'BUY'
        df.loc[bull_div_confirm, 'signal_strength'] = 7
        df.loc[bull_div_confirm, 'signal_reason'] = '底背离(价格新低+MACD未新低)'

        # Bearish divergence sell
        bear_div = (df['bearish_divergence'] == 1) & no_signal

        if self.params['divergence_confirm']:
            # Require price breakdown confirmation
            bear_div_confirm = bear_div & (
                df['close'] < df['close'].shift(5)
            )
        else:
            bear_div_confirm = bear_div

        df.loc[bear_div_confirm, 'signal_type'] = 'SELL'
        df.loc[bear_div_confirm, 'signal_strength'] = -7
        df.loc[bear_div_confirm, 'signal_reason'] = '顶背离(价格新高+MACD未新高)'

        return df

    def _ma60_filter_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Method 3: 60-day moving average filtering

        Logic:
        - Above MA60 + MACD zero-axis golden cross = high win rate buy point
        - Below MA60 + MACD death cross = avoid
        - Price pulls back to MA60 without breaking + MACD golden cross = optimal buy point
        """
        if not self.params['ma60_filter']:
            return df

        tolerance = self.params['ma60_tolerance']

        # Above MA60 golden cross (enhancement)
        ma60_above_buy = (
            (df['close'] > df['ma60'] * (1 - tolerance)) &
            (df['signal_type'] == 'BUY') &
            (df['macd_dif'] > 0)
        )

        df.loc[ma60_above_buy, 'signal_strength'] = \
            df.loc[ma60_above_buy, 'signal_strength'] + 2
        df.loc[ma60_above_buy, 'signal_reason'] = \
            df.loc[ma60_above_buy, 'signal_reason'] + '+MA60支撑'

        # Below MA60 death cross (avoid)
        ma60_below_sell = (
            (df['close'] < df['ma60'] * (1 + tolerance)) &
            (df['signal_type'] == 'SELL')
        )

        df.loc[ma60_below_sell, 'signal_strength'] = \
            df.loc[ma60_below_sell, 'signal_strength'] - 2

        # Price pulls back to MA60
        ma60_touch = (
            (df['low'] <= df['ma60'] * (1 + tolerance)) &
            (df['close'] > df['ma60']) &
            (df['signal_type'] == 'BUY')
        )

        df.loc[ma60_touch, 'signal_strength'] = 10
        df.loc[ma60_touch, 'signal_reason'] = '回踩MA60未破+MACD金叉'

        return df

    def _special_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Special pattern recognition

        - Duck bill: DIF/DEA about to cross but don't, then open again above zero
        - Inverted duck bill: DIF/DEA about to cross but don't, then go down again below zero
        """
        if not self.params['duck_bill_enable']:
            return df

        # Duck bill detection
        duck_bill = (
            (df['macd_dif'].shift(2) > df['macd_dea'].shift(2)) &
            (df['macd_dif'].shift(1) <= df['macd_dea'].shift(1)) &
            (df['macd_dif'] > df['macd_dea']) &
            (df['macd_dif'] > 0)
        )

        df.loc[duck_bill, 'signal_type'] = 'BUY'
        df.loc[duck_bill, 'signal_strength'] = 9
        df.loc[duck_bill, 'signal_reason'] = '正鸭嘴形态(将死不死再度开口)'

        if not self.params['inverted_duck_enable']:
            return df

        # Inverted duck bill detection
        inverted_duck = (
            (df['macd_dif'].shift(2) < df['macd_dea'].shift(2)) &
            (df['macd_dif'].shift(1) >= df['macd_dea'].shift(1)) &
            (df['macd_dif'] < df['macd_dea']) &
            (df['macd_dif'] < 0)
        )

        df.loc[inverted_duck, 'signal_type'] = 'SELL'
        df.loc[inverted_duck, 'signal_strength'] = -9
        df.loc[inverted_duck, 'signal_reason'] = '倒鸭嘴形态(将金不金再度向下)'

        return df


def get_latest_signal_optimized(etf_code: str, strategy_type: str, strategy_params: dict = None) -> dict:
    """优化版：只计算当天最新信号（仅支持MACD激进策略）

    流程：
    1. 读取历史数据（用于计算指标）
    2. 只计算最新的技术指标值（MACD、KDJ等）
    3. 只生成最新日期的信号
    4. 返回最新信号

    Args:
        etf_code: ETF代码
        strategy_type: 策略类型（仅支持 macd_aggressive）
        strategy_params: 策略参数

    Returns:
        dict: 最新信号数据
    """
    from core.database import get_etf_daily_data

    # 1. 获取历史数据（必须的，用于计算MACD等指标）
    data = get_etf_daily_data(etf_code, start_date='20240101')

    if not data or len(data) < 30:  # 至少需要30天数据计算MACD
        return {
            'signal': '数据不足',
            'action': 'hold',
            'macd_dif': 0,
            'macd_dea': 0,
            'macd_hist': 0,
            'kdj_k': 0,
            'kdj_d': 0,
            'kdj_j': 0,
            'close': 0,
            'trade_date': ''
        }

    df = pd.DataFrame(data)

    # 2. 只计算最后一行的技术指标
    # 获取策略参数
    if strategy_params is None:
        strategy_params = {}

    macd_fast = strategy_params.get('macd_fast', 8)
    macd_slow = strategy_params.get('macd_slow', 17)
    macd_signal = strategy_params.get('macd_signal', 5)

    # 计算MACD
    df_with_indicators = MACDIndicators.calculate_macd(
        df,
        fast=macd_fast,
        slow=macd_slow,
        signal=macd_signal
    )

    # 计算KDJ
    df_with_indicators = MACDIndicators.calculate_kdj(df_with_indicators)

    # 3. 只获取最后一行（最新数据）
    if len(df_with_indicators) == 0:
        return {
            'signal': '计算失败',
            'action': 'hold',
            'macd_dif': 0,
            'macd_dea': 0,
            'macd_hist': 0,
            'kdj_k': 0,
            'kdj_d': 0,
            'kdj_j': 0,
            'close': 0,
            'trade_date': ''
        }

    latest = df_with_indicators.iloc[-1]

    # 4. 根据策略类型生成信号（仅支持MACD激进策略）
    macd_dif = float(latest.get('macd_dif', 0))
    macd_dea = float(latest.get('macd_dea', 0))
    kdj_k = float(latest.get('kdj_k', 0))
    kdj_d = float(latest.get('kdj_d', 0))

    # 仅支持MACD激进策略
    signal = 'buy' if macd_dif > macd_dea else ('sell' if macd_dif < macd_dea else 'hold')

    return {
        'signal': signal,
        'action': 'buy' if signal == 'buy' else ('sell' if signal == 'sell' else 'hold'),
        'trade_date': str(latest['trade_date']),
        'close': float(latest['close']),
        'macd_dif': macd_dif,
        'macd_dea': macd_dea,
        'macd_hist': float(latest.get('macd_hist', 0)),
        'kdj_k': kdj_k,
        'kdj_d': kdj_d,
        'kdj_j': float(latest.get('kdj_j', 0))
    }
