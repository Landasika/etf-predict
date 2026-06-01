"""
MACD Histogram Momentum Signal Generator

Based on MACD histogram (量能柱) changes instead of DIF/DEA crossovers.
Six-phase state machine + acceleration adjustment + MA20 weak filter.
Outputs target_position (0-10) for the backtester to execute.

Tunable params:
- deadzone: ignore histogram changes when |hist| < threshold
- confirm_days: require N consecutive days of same state before switching
- smooth: EMA smoothing window for histogram
- max_change: cap daily position change at N levels
"""
import pandas as pd
import numpy as np
from .indicators import MACDIndicators


class MACDHistogramMomentumSignalGenerator:
    """MACD histogram momentum strategy signal generator"""

    def __init__(self, params: dict = None):
        base = self.default_params()
        if params:
            base.update(params)
        self.params = base

    @staticmethod
    def default_params() -> dict:
        return {
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'ma_period': 20,
            'ma_slope_lookback': 5,
            'deadzone': 0.0,
            'confirm_days': 1,
            'smooth': 1,
            'max_change': 10,
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        fast = self.params['macd_fast']
        slow = self.params['macd_slow']
        signal = self.params['macd_signal']
        ma_period = self.params['ma_period']
        slope_lb = self.params['ma_slope_lookback']
        deadzone = self.params.get('deadzone', 0)
        confirm_days = self.params.get('confirm_days', 1)
        smooth = self.params.get('smooth', 1)
        max_change = self.params.get('max_change', 10)

        df = MACDIndicators.calculate_macd(df, fast=fast, slow=slow, signal=signal)

        # MA20
        df['ma20'] = df['close'].rolling(window=ma_period, min_periods=1).mean()
        df['ma20_slope'] = self._ma20_slope(df, slope_lb)

        # Optional histogram smoothing
        if smooth > 1:
            df['macd_hist'] = df['macd_hist'].ewm(span=smooth, adjust=False).mean()

        # Histogram direction and acceleration
        df['hist_direction'] = self._hist_direction(df)
        df['hist_acceleration'] = self._hist_acceleration(df)

        # Six-phase state with deadzone + confirmation
        df['hist_state'] = self._classify_state(df, deadzone, confirm_days)

        # Position calculation
        df['target_position'] = 0
        df['signal_reason'] = ''

        h = df['macd_hist']
        ah = h.abs()
        start_idx = max(ma_period, slow + signal)

        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            base = self._base_position(row['hist_state'])
            accel = self._accel_adjust(row['hist_state'], row['hist_acceleration'])

            # Apply MA20 downside cap before slope adjustment
            pre_cap = base + accel
            pre_cap = self._ma20_cap(row['close'], row['ma20'], pre_cap)

            ma20_slope_adj = self._ma20_slope_adjust(row['close'], row['ma20'], row['ma20_slope'])
            target = max(0, min(10, int(round(pre_cap + ma20_slope_adj))))

            # Apply max_change limit
            if max_change < 10:
                prev = df.at[df.index[i-1], 'target_position']
                target = max(prev - max_change, min(prev + max_change, target))

            df.at[df.index[i], 'target_position'] = target
            df.at[df.index[i], 'signal_reason'] = self._build_reason(
                row['hist_state'], row['hist_direction'], row['hist_acceleration'],
                base, accel, ma20_slope_adj
            )

        return df

    def _hist_direction(self, df: pd.DataFrame) -> pd.Series:
        hist = df['macd_hist']
        result = pd.Series('FLAT', index=df.index)
        expanding = hist.abs() > hist.abs().shift(1)
        shrinking = hist.abs() < hist.abs().shift(1)
        result[expanding] = 'EXPANDING'
        result[shrinking] = 'SHRINKING'
        return result

    def _hist_acceleration(self, df: pd.DataFrame) -> pd.Series:
        hist = df['macd_hist']
        abs_hist = hist.abs()
        daily_change = abs_hist.diff()
        result = pd.Series('STEADY', index=df.index)
        accel_mask = (
            (daily_change > 0) &
            (daily_change.shift(1) > 0) &
            (daily_change > daily_change.shift(1))
        )
        decel_mask = (
            (daily_change < 0) &
            (daily_change.shift(1) < 0) &
            (daily_change < daily_change.shift(1))
        )
        result[accel_mask] = 'ACCELERATING'
        result[decel_mask] = 'DECELERATING'
        return result

    def _classify_state(self, df: pd.DataFrame, deadzone: float = 0,
                        confirm_days: int = 1) -> pd.Series:
        hist = df['macd_hist']
        direction = df['hist_direction']

        # Raw state (no deadzone/confirmation)
        raw = pd.Series('STRONG_BEAR', index=df.index)
        just_up = (hist > 0) & (hist.shift(1) <= 0)
        just_down = (hist < 0) & (hist.shift(1) >= 0)
        raw[(hist > 0) & (direction == 'EXPANDING') & ~just_up] = 'STRONG_BULL'
        raw[(hist > 0) & (direction == 'SHRINKING') & ~just_down] = 'BULL_WEAKENING'
        raw[(hist < 0) & (direction == 'SHRINKING') & ~just_up] = 'BEAR_TO_BULL'
        raw[just_up] = 'JUST_CROSSED_UP'
        raw[just_down] = 'JUST_CROSSED_DOWN'

        if deadzone == 0 and confirm_days <= 1:
            return raw

        # Apply deadzone + confirmation sequentially
        result = pd.Series('STRONG_BEAR', index=df.index)
        cur = 'STRONG_BEAR'
        pending = None
        count = 0

        for i in range(len(df)):
            rs = raw.iloc[i]

            # Deadzone: if |hist| is tiny, keep current state
            if deadzone > 0 and abs(hist.iloc[i]) < deadzone:
                rs = cur

            # Confirmation: require N consecutive days
            if confirm_days <= 1:
                cur = rs
            else:
                if rs == pending:
                    count += 1
                    if count >= confirm_days:
                        cur = rs
                        pending = None
                        count = 0
                else:
                    pending = rs
                    count = 1

            result.iloc[i] = cur

        return result

    def _base_position(self, state: str) -> int:
        return {
            'STRONG_BULL': 9,
            'BULL_WEAKENING': 4,
            'BEAR_TO_BULL': 2,
            'STRONG_BEAR': 0,
            'JUST_CROSSED_UP': 6,
            'JUST_CROSSED_DOWN': 1,
        }.get(state, 0)

    def _accel_adjust(self, state: str, accel: str) -> int:
        if accel == 'ACCELERATING':
            return 2
        elif accel == 'DECELERATING':
            return -2
        return 0

    def _ma20_slope_adjust(self, close: float, ma20: float, slope: str) -> int:
        adjust = 0
        if close > ma20:
            adjust += 1
        if slope == 'UP':
            adjust += 1
        elif slope == 'DOWN':
            adjust -= 1
        return adjust

    def _ma20_cap(self, close: float, ma20: float, position: int) -> int:
        if close < ma20:
            return min(position, 5)
        return position

    def _ma20_slope(self, df: pd.DataFrame, lookback: int) -> pd.Series:
        ma = df['ma20']
        result = pd.Series('FLAT', index=df.index)
        result[ma > ma.shift(lookback)] = 'UP'
        result[ma < ma.shift(lookback)] = 'DOWN'
        return result

    def _build_reason(self, state: str, direction: str, accel: str,
                      base: int, accel_adj: int, ma20_adj: int) -> str:
        state_names = {
            'STRONG_BULL': '强多',
            'BULL_WEAKENING': '多转弱',
            'BEAR_TO_BULL': '空转多',
            'STRONG_BEAR': '强空',
            'JUST_CROSSED_UP': '刚上零轴',
            'JUST_CROSSED_DOWN': '刚下零轴',
        }
        parts = [state_names.get(state, state)]
        if accel_adj != 0:
            parts.append('急加速' if accel_adj > 0 else '急减速')
        if ma20_adj > 0:
            parts.append('MA20支撑')
        elif ma20_adj < 0:
            parts.append('MA20压制')
        return '+'.join(parts)
