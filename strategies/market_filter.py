"""
Market Trend Filter

Filters signals based on overall market conditions.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from .indicators import MACDIndicators


class MarketFilter:
    """
    Market trend filter

    Reduces position sizes or prohibits going long when market trend is poor.
    """

    def __init__(self, index_code: str = '000300.SH'):
        """
        Initialize market filter

        Args:
            index_code: Market index code (default: CSI 300)
        """
        self.index_code = index_code

    def get_market_trend(self, df_index: pd.DataFrame) -> pd.Series:
        """
        Determine market trend

        Args:
            df_index: DataFrame with market index OHLCV data

        Returns:
            Series: 1 = bullish, 0 = neutral, -1 = bearish
        """
        df_index = df_index.copy()

        # Calculate index MA60
        df_index['ma60'] = df_index['close'].rolling(60, min_periods=1).mean()

        # Calculate index MACD
        df_index = MACDIndicators.calculate_macd(df_index)

        # Initialize trend
        trend = pd.Series(0, index=df_index.index)

        # Bullish: Price above MA60 AND DIF > 0
        bull_mask = (
            (df_index['close'] > df_index['ma60']) &
            (df_index['macd_dif'] > 0)
        )
        trend.loc[bull_mask] = 1

        # Bearish: Price below MA60 AND DIF < 0
        bear_mask = (
            (df_index['close'] < df_index['ma60']) &
            (df_index['macd_dif'] < 0)
        )
        trend.loc[bear_mask] = -1

        # Neutral: Everything else

        return trend

    def apply_filter(self,
                     df_signals: pd.DataFrame,
                     market_trend: pd.Series,
                     bullish_multiplier: float = 1.0,
                     neutral_multiplier: float = 0.5,
                     bearish_multiplier: float = 0.3) -> pd.DataFrame:
        """
        Apply market filter to signals

        Args:
            df_signals: DataFrame with 'final_strength' column
            market_trend: Series with market trend (-1, 0, 1)
            bullish_multiplier: Position multiplier in bull market (default 1.0)
            neutral_multiplier: Position multiplier in neutral market (default 0.5)
            bearish_multiplier: Position multiplier in bear market (default 0.3)

        Returns:
            DataFrame with filtered signals
        """
        df_signals = df_signals.copy()
        df_signals['market_filter'] = market_trend

        # Apply multipliers based on market trend
        if 'final_strength' in df_signals.columns:
            # Bearish market: Reduce positions significantly
            bear_mask = (df_signals['market_filter'] == -1)
            df_signals.loc[bear_mask, 'final_strength'] = (
                df_signals.loc[bear_mask, 'final_strength'] * bearish_multiplier
            )

            # Neutral market: Reduce positions moderately
            neutral_mask = (df_signals['market_filter'] == 0)
            df_signals.loc[neutral_mask, 'final_strength'] = (
                df_signals.loc[neutral_mask, 'final_strength'] * neutral_multiplier
            )

            # Bullish market: No reduction (keep original)

        return df_signals

    def get_market_regime(self, df_index: pd.DataFrame,
                          lookback: int = 60) -> Dict:
        """
        Classify market regime

        Args:
            df_index: DataFrame with market index data
            lookback: Lookback period for regime calculation

        Returns:
            Dictionary with regime information
        """
        df_index = df_index.copy()

        # Calculate indicators
        df_index['ma60'] = df_index['close'].rolling(60, min_periods=1).mean()
        df_index['returns'] = df_index['close'].pct_change()

        # Recent data
        recent = df_index.tail(lookback)

        # Calculate regime metrics
        price_above_ma60 = (recent['close'].iloc[-1] > recent['ma60'].iloc[-1])

        # Trend strength
        trend_strength = (recent['close'].iloc[-1] / recent['close'].iloc[0] - 1)

        # Volatility
        volatility = recent['returns'].std()

        # Determine regime
        if price_above_ma60 and trend_strength > 0.05:
            regime = 'strong_bull'
        elif price_above_ma60 and trend_strength > 0:
            regime = 'bull'
        elif not price_above_ma60 and trend_strength < -0.05:
            regime = 'strong_bear'
        elif not price_above_ma60 and trend_strength < 0:
            regime = 'bear'
        else:
            regime = 'sideways'

        return {
            'regime': regime,
            'price_above_ma60': price_above_ma60,
            'trend_strength': trend_strength,
            'volatility': volatility,
            'recent_return': recent['returns'].iloc[-1] if len(recent) > 0 else 0
        }

    def calculate_allowed_positions(self,
                                     market_regime: str,
                                     max_positions: int = 10) -> int:
        """
        Calculate maximum allowed positions based on market regime

        Args:
            market_regime: Market regime type
            max_positions: Maximum positions in strong bull market

        Returns:
            int: Number of allowed positions
        """
        regime_limits = {
            'strong_bull': max_positions,
            'bull': int(max_positions * 0.8),
            'sideways': int(max_positions * 0.5),
            'bear': int(max_positions * 0.2),
            'strong_bear': 0  # No new positions in strong bear
        }

        return regime_limits.get(market_regime, int(max_positions * 0.5))


class VolatilityFilter:
    """
    Volatility-based position filter

    Reduces positions during high volatility periods.
    """

    def __init__(self,
                 low_vol_threshold: float = 0.015,
                 high_vol_threshold: float = 0.03):
        """
        Initialize volatility filter

        Args:
            low_vol_threshold: Low volatility threshold (ATR %)
            high_vol_threshold: High volatility threshold (ATR %)
        """
        self.low_vol_threshold = low_vol_threshold
        self.high_vol_threshold = high_vol_threshold

    def calculate_volatility_regime(self, atr_pct: float) -> str:
        """
        Classify volatility regime

        Args:
            atr_pct: ATR as percentage of price

        Returns:
            str: 'low', 'normal', or 'high'
        """
        if atr_pct < self.low_vol_threshold:
            return 'low'
        elif atr_pct > self.high_vol_threshold:
            return 'high'
        else:
            return 'normal'

    def apply_volatility_filter(self,
                                 df: pd.DataFrame,
                                 low_vol_multiplier: float = 1.2,
                                 high_vol_multiplier: float = 0.5) -> pd.DataFrame:
        """
        Apply volatility filter to signals

        Args:
            df: DataFrame with 'atr_pct' and 'final_strength' columns
            low_vol_multiplier: Position multiplier in low vol
            high_vol_multiplier: Position multiplier in high vol

        Returns:
            DataFrame with filtered signals
        """
        df = df.copy()

        # Calculate volatility regime for each row
        vol_regime = df['atr_pct'].apply(self.calculate_volatility_regime)
        df['volatility_regime'] = vol_regime

        if 'final_strength' in df.columns:
            # Low volatility: Can increase positions
            low_vol_mask = (vol_regime == 'low')
            df.loc[low_vol_mask, 'final_strength'] = (
                df.loc[low_vol_mask, 'final_strength'] * low_vol_multiplier
            )

            # High volatility: Reduce positions
            high_vol_mask = (vol_regime == 'high')
            df.loc[high_vol_mask, 'final_strength'] = (
                df.loc[high_vol_mask, 'final_strength'] * high_vol_multiplier
            )

        return df


class CombinedMarketFilter:
    """
    Combined market filter using trend and volatility
    """

    def __init__(self,
                 index_code: str = '000300.SH',
                 low_vol_threshold: float = 0.015,
                 high_vol_threshold: float = 0.03):
        """
        Initialize combined filter

        Args:
            index_code: Market index code
            low_vol_threshold: Low volatility threshold
            high_vol_threshold: High volatility threshold
        """
        self.trend_filter = MarketFilter(index_code)
        self.vol_filter = VolatilityFilter(low_vol_threshold, high_vol_threshold)

    def apply_filters(self,
                      df_signals: pd.DataFrame,
                      df_index: pd.DataFrame) -> pd.DataFrame:
        """
        Apply both trend and volatility filters

        Args:
            df_signals: DataFrame with signals
            df_index: DataFrame with market index data

        Returns:
            DataFrame with filtered signals
        """
        # Apply trend filter
        market_trend = self.trend_filter.get_market_trend(df_index)
        df_signals = self.trend_filter.apply_filter(df_signals, market_trend)

        # Apply volatility filter
        df_signals = self.vol_filter.apply_volatility_filter(df_signals)

        return df_signals

    def get_combined_regime(self,
                           df_signals: pd.DataFrame,
                           df_index: pd.DataFrame) -> Dict:
        """
        Get combined market regime information

        Args:
            df_signals: DataFrame with signals
            df_index: DataFrame with market index data

        Returns:
            Dictionary with combined regime info
        """
        # Get trend regime
        trend_regime = self.trend_filter.get_market_regime(df_index)

        # Get current volatility regime
        current_atr_pct = df_signals['atr_pct'].iloc[-1] if len(df_signals) > 0 else 0
        vol_regime = self.vol_filter.calculate_volatility_regime(current_atr_pct)

        return {
            'trend_regime': trend_regime['regime'],
            'volatility_regime': vol_regime,
            'trend_strength': trend_regime['trend_strength'],
            'atr_pct': current_atr_pct
        }
