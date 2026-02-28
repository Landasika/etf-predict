"""
Multi-Factor Feature Engineering

Builds factor matrix for machine learning models.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from .indicators import MACDIndicators


class FactorBuilder:
    """Build multi-factor feature matrix"""

    def __init__(self, df: pd.DataFrame = None):
        """
        Initialize FactorBuilder

        Args:
            df: Optional DataFrame to build factors from
        """
        self.df = df.copy() if df is not None else None

    def build_factor_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build complete factor matrix

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with all factor columns (prefixed with 'f_')
        """
        df = df.copy()

        # Calculate all technical indicators
        df = MACDIndicators.calculate_macd(df)
        df = MACDIndicators.calculate_kdj(df)
        df = MACDIndicators.calculate_boll(df)
        df = MACDIndicators.calculate_atr(df)
        df = MACDIndicators.calculate_volume_factors(df)
        df = MACDIndicators.add_ma60(df)

        # Build directional factors
        df = self._build_macd_factors(df)
        df = self._build_kdj_factors(df)
        df = self._build_boll_factors(df)
        df = self._build_volume_factors(df)
        df = self._build_trend_factors(df)

        return df

    def _build_macd_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        MACD factor group

        Factors:
        - f_macd_trend: Trend strength (DIF value)
        - f_macd_cross: Golden cross signal
        - f_macd_hist_slope: Histogram slope (momentum)
        - f_macd_zero_pos: Position relative to zero axis
        """
        df['f_macd_trend'] = df['macd_dif']  # Trend strength

        # Golden cross signal
        df['f_macd_cross'] = (
            (df['macd_dif'] > df['macd_dea']) &
            (df['macd_dif'].shift(1) <= df['macd_dea'].shift(1))
        ).astype(int)

        # Histogram slope (momentum change)
        df['f_macd_hist_slope'] = df['macd_hist'].diff()

        # Zero axis position (encoded as -1, 0, 1)
        df['f_macd_zero_pos'] = np.where(
            df['macd_dif'] > 0, 1,
            np.where(df['macd_dif'] < 0, -1, 0)
        )

        return df

    def _build_kdj_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        KDJ factor group

        Factors:
        - f_k_oversold: Oversold condition (K < 20)
        - f_k_overbought: Overbought condition (K > 80)
        - f_k_slope: K line slope (momentum)
        - f_kd_cross: K crosses above D
        """
        df['f_k_oversold'] = (df['kdj_k'] < 20).astype(int)
        df['f_k_overbought'] = (df['kdj_k'] > 80).astype(int)
        df['f_k_slope'] = df['kdj_k'].diff()

        # K crosses above D (bullish)
        df['f_kd_cross'] = (
            (df['kdj_k'] > df['kdj_d']) &
            (df['kdj_k'].shift(1) <= df['kdj_d'].shift(1))
        ).astype(int)

        # J value (momentum strength)
        df['f_j_value'] = df['kdj_j']

        return df

    def _build_boll_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        BOLL factor group

        Factors:
        - f_boll_lower_touch: Proximity to lower band
        - f_boll_upper_touch: Proximity to upper band
        - f_boll_breakout: Price breaks outside bands
        - f_boll_squeeze: Band width squeeze (low volatility)
        """
        # Proximity to lower band (normalized)
        boll_lower_safe = df['boll_lower'].replace(0, np.finfo(float).eps)
        df['f_boll_lower_touch'] = (df['close'] - boll_lower_safe) / boll_lower_safe

        # Proximity to upper band (normalized)
        boll_upper_safe = df['boll_upper'].replace(0, np.finfo(float).eps)
        df['f_boll_upper_touch'] = (boll_upper_safe - df['close']) / boll_upper_safe

        # Breakout detection
        df['f_boll_breakout'] = (
            (df['close'] > df['boll_upper']) |
            (df['close'] < df['boll_lower'])
        ).astype(int)

        # Band squeeze (low volatility - potential breakout setup)
        boll_width_ma = df['boll_width'].rolling(20).mean()
        df['f_boll_squeeze'] = (df['boll_width'] < boll_width_ma * 0.5).astype(int)

        # Position within bands (0 = at lower, 1 = at upper)
        boll_range = df['boll_upper'] - df['boll_lower']
        boll_range_safe = boll_range.replace(0, np.finfo(float).eps)
        df['f_boll_position'] = (df['close'] - df['boll_lower']) / boll_range_safe

        return df

    def _build_volume_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Volume factor group

        Factors:
        - f_volume_ratio: Volume ratio (current / average)
        - f_volume_spike: Volume spike indicator
        - f_volume_trend: Volume trend (MA slope)
        """
        df['f_volume_ratio'] = df['volume_ratio']
        df['f_volume_spike'] = df['volume_spike']

        # Volume trend
        df['f_volume_trend'] = df['volume_ma'].diff()

        # Volume-price trend (VP trend)
        price_change = df['close'].pct_change()
        volume_change = df['vol'].pct_change()
        df['f_vpt'] = (price_change * volume_change).fillna(0)

        return df

    def _build_trend_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Trend factor group

        Factors:
        - f_ma60_trend: Price relative to MA60
        - f_price_momentum: Price momentum (ROC)
        - f_atr_volatility: Volatility level (ATR %)
        """
        # MA60 trend
        ma60_safe = df['ma60'].replace(0, np.finfo(float).eps)
        df['f_ma60_trend'] = (df['close'] - ma60_safe) / ma60_safe

        # Price momentum (Rate of Change)
        df['f_price_momentum'] = df['close'].pct_change(5)

        # Volatility level
        df['f_atr_volatility'] = df['atr_pct']

        # Price strength relative to ATR
        df['f_price_strength'] = (df['close'] - df['close'].shift(1)) / df['atr']
        df['f_price_strength'] = df['f_price_strength'].fillna(0).replace([np.inf, -np.inf], 0)

        return df

    def get_feature_names(self) -> List[str]:
        """
        Get list of factor feature names

        Returns:
            List of factor column names (prefixed with 'f_')
        """
        return [
            # MACD factors
            'f_macd_trend', 'f_macd_cross', 'f_macd_hist_slope', 'f_macd_zero_pos',

            # KDJ factors
            'f_k_oversold', 'f_k_overbought', 'f_k_slope', 'f_kd_cross', 'f_j_value',

            # BOLL factors
            'f_boll_lower_touch', 'f_boll_upper_touch', 'f_boll_breakout',
            'f_boll_squeeze', 'f_boll_position',

            # Volume factors
            'f_volume_ratio', 'f_volume_spike', 'f_volume_trend', 'f_vpt',

            # Trend factors
            'f_ma60_trend', 'f_price_momentum', 'f_atr_volatility', 'f_price_strength'
        ]

    def get_factor_groups(self) -> Dict[str, List[str]]:
        """
        Get factor groups by category

        Returns:
            Dictionary mapping group names to factor lists
        """
        return {
            'macd': [
                'f_macd_trend', 'f_macd_cross', 'f_macd_hist_slope', 'f_macd_zero_pos'
            ],
            'kdj': [
                'f_k_oversold', 'f_k_overbought', 'f_k_slope', 'f_kd_cross', 'f_j_value'
            ],
            'boll': [
                'f_boll_lower_touch', 'f_boll_upper_touch', 'f_boll_breakout',
                'f_boll_squeeze', 'f_boll_position'
            ],
            'volume': [
                'f_volume_ratio', 'f_volume_spike', 'f_volume_trend', 'f_vpt'
            ],
            'trend': [
                'f_ma60_trend', 'f_price_momentum', 'f_atr_volatility', 'f_price_strength'
            ]
        }
