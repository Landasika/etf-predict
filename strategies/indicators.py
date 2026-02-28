"""
MACD Technical Indicators

Calculates MACD indicators and detects divergence patterns.
"""

import pandas as pd
import numpy as np


class MACDIndicators:
    """MACD indicator calculation engine"""

    @staticmethod
    def ema(df: pd.Series, span: int) -> pd.Series:
        """Exponential Moving Average"""
        return df.ewm(span=span, adjust=False).mean()

    @staticmethod
    def calculate_macd(df: pd.DataFrame,
                       fast: int = 12,
                       slow: int = 26,
                       signal: int = 9) -> pd.DataFrame:
        """
        Calculate MACD indicator

        Args:
            df: DataFrame with 'close' column
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line EMA period (default 9)

        Returns:
            DataFrame with added columns:
            - macd_dif: DIF line (fast EMA - slow EMA)
            - macd_dea: DEA line (signal line)
            - macd_hist: MACD histogram (2 * (DIF - DEA))
            - zero_axis_position: Position relative to zero (ABOVE/BELOW/AT)
        """
        df = df.copy()

        # Calculate EMAs
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()

        # Calculate MACD components
        df['macd_dif'] = ema_fast - ema_slow
        df['macd_dea'] = df['macd_dif'].ewm(span=signal, adjust=False).mean()
        df['macd_hist'] = 2 * (df['macd_dif'] - df['macd_dea'])

        # Determine zero-axis position
        df['zero_axis_position'] = df['macd_dif'].apply(
            lambda x: 'ABOVE' if x > 0 else ('BELOW' if x < 0 else 'AT')
        )

        return df

    @staticmethod
    def add_ma60(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add 60-day moving average

        Args:
            df: DataFrame with 'close' column

        Returns:
            DataFrame with added 'ma60' column
        """
        df = df.copy()
        df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()
        return df

    @staticmethod
    def detect_divergence(df: pd.DataFrame,
                         lookback: int = 20) -> pd.DataFrame:
        """
        Detect bullish and bearish divergence

        Bullish divergence: Price makes new low but MACD doesn't (reversal signal)
        Bearish divergence: Price makes new high but MACD doesn't (reversal signal)

        Args:
            df: DataFrame with 'close' and 'macd_hist' columns
            lookback: Period to look back for peaks/valleys (default 20)

        Returns:
            DataFrame with added columns:
            - bullish_divergence: Bullish divergence signal (0 or 1)
            - bearish_divergence: Bearish divergence signal (0 or 1)
        """
        df = df.copy()

        # Detect price peaks and valleys using rolling windows
        # For center=True, we need an odd window size
        window_size = lookback * 2 + 1

        # Price peaks/valleys
        price_peaks = df['close'].rolling(window_size, center=True).max()
        price_valleys = df['close'].rolling(window_size, center=True).min()

        # MACD peaks/valleys
        macd_peaks = df['macd_hist'].rolling(window_size, center=True).max()
        macd_valleys = df['macd_hist'].rolling(window_size, center=True).min()

        # Bullish divergence: price at or near new low, MACD not at new low
        df['bullish_divergence'] = (
            (df['close'] <= price_valleys * 1.01) &  # Within 1% of valley
            (df['macd_hist'] > macd_valleys * 0.99)   # Not at MACD valley
        ).astype(int)

        # Bearish divergence: price at or near new high, MACD not at new high
        df['bearish_divergence'] = (
            (df['close'] >= price_peaks * 0.99) &     # Within 1% of peak
            (df['macd_hist'] < macd_peaks * 1.01)     # Not at MACD peak
        ).astype(int)

        return df

    @staticmethod
    def detect_crossover(df: pd.DataFrame, col1: str, col2: str) -> pd.Series:
        """
        Detect crossover points (col1 crosses col2)

        Returns:
            Series with values: 1 (bullish cross), -1 (bearish cross), 0 (no cross)
        """
        crossed_above = (
            (df[col1].shift(1) <= df[col2].shift(1)) &
            (df[col1] > df[col2])
        )

        crossed_below = (
            (df[col1].shift(1) >= df[col2].shift(1)) &
            (df[col1] < df[col2])
        )

        signal = pd.Series(0, index=df.index)
        signal[crossed_above] = 1
        signal[crossed_below] = -1

        return signal

    @staticmethod
    def calculate_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """
        Calculate KDJ indicator (Stochastic Oscillator)

        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            n: RSV calculation period (default 9)
            m1: K value EMA period (default 3)
            m2: D value EMA period (default 3)

        Returns:
            DataFrame with added columns:
            - kdj_k: K line
            - kdj_d: D line
            - kdj_j: J line (3K - 2D)
        """
        df = df.copy()

        # Calculate RSV (Raw Stochastic Value)
        low_list = df['low'].rolling(window=n, min_periods=1).min()
        high_list = df['high'].rolling(window=n, min_periods=1).max()

        # Avoid division by zero
        high_low_diff = high_list - low_list
        high_low_diff = high_low_diff.replace(0, np.finfo(float).eps)

        rsv = (df['close'] - low_list) / high_low_diff * 100

        # Calculate K, D, J
        df['kdj_k'] = rsv.ewm(com=m1-1, adjust=False).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=m2-1, adjust=False).mean()
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']

        return df

    @staticmethod
    def calculate_boll(df: pd.DataFrame, n: int = 20, num_std: float = 2) -> pd.DataFrame:
        """
        Calculate Bollinger Bands

        Args:
            df: DataFrame with 'close' column
            n: MA period (default 20)
            num_std: Number of standard deviations (default 2)

        Returns:
            DataFrame with added columns:
            - boll_middle: Middle band (SMA)
            - boll_upper: Upper band
            - boll_lower: Lower band
            - boll_width: Band width percentage
        """
        df = df.copy()

        df['boll_middle'] = df['close'].rolling(window=n, min_periods=1).mean()
        std = df['close'].rolling(window=n, min_periods=1).std()

        df['boll_upper'] = df['boll_middle'] + num_std * std
        df['boll_lower'] = df['boll_middle'] - num_std * std

        # Band width (avoid division by zero)
        boll_middle_safe = df['boll_middle'].replace(0, np.finfo(float).eps)
        df['boll_width'] = (df['boll_upper'] - df['boll_lower']) / boll_middle_safe

        return df

    @staticmethod
    def calculate_atr(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
        """
        Calculate Average True Range (ATR)

        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            n: ATR period (default 14)

        Returns:
            DataFrame with added columns:
            - atr: ATR value
            - atr_pct: ATR as percentage of price
        """
        df = df.copy()

        # Calculate True Range components
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        # True Range is the maximum of the three
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # ATR is EMA of True Range
        df['atr'] = tr.ewm(span=n, adjust=False).mean()

        # ATR as percentage of price (avoid division by zero)
        close_safe = df['close'].replace(0, np.finfo(float).eps)
        df['atr_pct'] = df['atr'] / close_safe

        return df

    @staticmethod
    def calculate_volume_factors(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
        """
        Calculate volume factors

        Args:
            df: DataFrame with 'vol' column
            n: MA period for volume (default 20)

        Returns:
            DataFrame with added columns:
            - volume_ma: Volume moving average
            - volume_ratio: Current volume / MA volume
            - volume_spike: Binary indicator for volume spike (>1.5x normal)
        """
        df = df.copy()

        df['volume_ma'] = df['vol'].rolling(window=n, min_periods=1).mean()

        # Avoid division by zero
        volume_ma_safe = df['volume_ma'].replace(0, np.finfo(float).eps)
        df['volume_ratio'] = df['vol'] / volume_ma_safe

        df['volume_spike'] = (df['volume_ratio'] > 1.5).astype(int)

        return df
