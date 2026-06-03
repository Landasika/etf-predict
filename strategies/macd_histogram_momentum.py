"""
MACD Histogram Momentum Signal Generator

Based on MACD histogram (量能柱) changes instead of DIF/DEA crossovers.
Six-phase state machine + acceleration adjustment + MA20 weak filter.
Outputs target_position (0-10) for the backtester to execute.

Tunable params:
- exhaustion_ratio: current bar / current sign-cycle peak ratio that marks exhaustion
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
            'exhaustion_ratio': 0.35,
            'confirm_days': 1,
            'smooth': 1,
            'max_change': 10,
            'min_position_change': 1,
            'volatility_filter': True,
            'volatility_window': 20,
            'low_vol_threshold': 0.20,
            'high_vol_threshold': 0.45,
            'low_vol_early_bonus': 1,
            'high_vol_early_penalty': 1,
            'semantic_position_rules': True,
            'weakening_reduce_step': 1,
            'weakening_recovery_days': 3,
            'strong_bull_increment': True,
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        fast = self.params['macd_fast']
        slow = self.params['macd_slow']
        signal = self.params['macd_signal']
        ma_period = self.params['ma_period']
        slope_lb = self.params['ma_slope_lookback']
        confirm_days = self.params.get('confirm_days', 1)
        smooth = self.params.get('smooth', 1)
        max_change = self.params.get('max_change', 10)
        min_position_change = self.params.get('min_position_change', 2)

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
        df = self._hist_cycle_peak_ratio(df)
        df['annual_volatility'] = self._annual_volatility(df)

        # Six-phase state with cycle-peak exhaustion + confirmation
        df['hist_state'] = self._classify_state(df, confirm_days=confirm_days)

        # Position calculation
        df['target_position'] = 0
        df['signal_reason'] = ''

        h = df['macd_hist']
        ah = h.abs()
        start_idx = max(ma_period, slow + signal)
        weakening_count = 0  # Track consecutive expanding days during weakening

        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            prev = df.at[df.index[i-1], 'target_position'] if i > start_idx else 0
            target, weakening_count = self._target_from_row(
                row, previous=prev, weakening_count=weakening_count
            )
            target = self._apply_position_debounce(target, prev, min_position_change)

            # Apply max_change limit
            if max_change < 10:
                target = max(prev - max_change, min(prev + max_change, target))

            df.at[df.index[i], 'target_position'] = target
            # Recalculate adjustments for display reason
            _base = self._base_position(row['hist_state'])
            _accel = self._accel_adjust(row['hist_state'], row['hist_acceleration'])
            _ma20 = self._ma20_slope_adjust(row['close'], row['ma20'], row['ma20_slope'])
            _vol = self._volatility_adjust(row['hist_state'], row.get('annual_volatility', 0))
            df.at[df.index[i], 'signal_reason'] = self._build_reason(
                row['hist_state'], row['hist_direction'], row['hist_acceleration'],
                _base, _accel, _ma20, _vol
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

    def _hist_cycle_peak_ratio(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        peaks = []
        ratios = []
        current_sign = 0
        current_peak = 0.0

        for value in df['macd_hist'].fillna(0):
            sign = 1 if value > 0 else (-1 if value < 0 else current_sign)
            if sign != current_sign:
                current_sign = sign
                current_peak = abs(value)
            else:
                current_peak = max(current_peak, abs(value))

            peaks.append(current_peak)
            ratios.append(abs(value) / current_peak if current_peak > 0 else 0)

        df['hist_cycle_peak'] = peaks
        df['hist_peak_ratio'] = ratios
        return df

    def _classify_state(self, df: pd.DataFrame, deadzone: float = 0,
                        confirm_days: int = 1) -> pd.Series:
        hist = df['macd_hist']
        exhaustion_ratio = self.params.get('exhaustion_ratio', 0.5)
        peak_ratio = df.get('hist_peak_ratio')
        if peak_ratio is None:
            df = self._hist_cycle_peak_ratio(df)
            peak_ratio = df['hist_peak_ratio']

        # Raw state uses relative exhaustion inside the current MACD histogram sign cycle.
        raw = pd.Series('STRONG_BEAR', index=df.index)
        just_up = (hist > 0) & (hist.shift(1) <= 0)
        just_down = (hist < 0) & (hist.shift(1) >= 0)
        negative_exhausted = (hist < 0) & (peak_ratio <= exhaustion_ratio)
        positive_exhausted = (hist > 0) & (peak_ratio <= exhaustion_ratio)

        raw[hist > 0] = 'STRONG_BULL'
        raw[negative_exhausted] = 'BEAR_TO_BULL'
        raw[positive_exhausted] = 'BULL_WEAKENING'
        raw[just_up] = 'JUST_CROSSED_UP'
        raw[just_down] = 'JUST_CROSSED_DOWN'

        if confirm_days <= 1:
            return raw

        # Apply confirmation sequentially.
        result = pd.Series('STRONG_BEAR', index=df.index)
        cur = 'STRONG_BEAR'
        pending = None
        count = 0

        for i in range(len(df)):
            rs = raw.iloc[i]

            # Confirmation: require N consecutive days
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
        if state == 'BEAR_TO_BULL':
            if accel == 'DECELERATING':
                return 2
            if accel == 'ACCELERATING':
                return -1
            return 0
        if state == 'STRONG_BEAR':
            if accel == 'ACCELERATING':
                return -2
            if accel == 'DECELERATING':
                return 1
            return 0
        if state == 'JUST_CROSSED_DOWN':
            if accel == 'ACCELERATING':
                return -2
            if accel == 'DECELERATING':
                return 1
            return 0
        if accel == 'ACCELERATING':
            return 2
        if accel == 'DECELERATING':
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

    def _annual_volatility(self, df: pd.DataFrame) -> pd.Series:
        window = self.params.get('volatility_window', 20)
        returns = df['close'].pct_change()
        return returns.rolling(window=window, min_periods=2).std().fillna(0) * np.sqrt(252)

    def _volatility_adjust(self, state: str, annual_volatility: float) -> int:
        if not self.params.get('volatility_filter', True):
            return 0
        if state not in {'BEAR_TO_BULL', 'JUST_CROSSED_UP'}:
            return 0

        low_threshold = self.params.get('low_vol_threshold', 0.20)
        high_threshold = self.params.get('high_vol_threshold', 0.35)
        if annual_volatility <= low_threshold:
            return self.params.get('low_vol_early_bonus', 1)
        if annual_volatility >= high_threshold:
            return -self.params.get('high_vol_early_penalty', 2)
        return 0

    def _raw_target_from_row(self, row: pd.Series) -> int:
        base = self._base_position(row['hist_state'])
        accel = self._accel_adjust(row['hist_state'], row['hist_acceleration'])
        ma20_slope_adj = self._ma20_slope_adjust(row['close'], row['ma20'], row['ma20_slope'])
        vol_adj = self._volatility_adjust(row['hist_state'], row.get('annual_volatility', 0))
        target = base + accel + ma20_slope_adj + vol_adj
        target = self._ma20_cap(row['close'], row['ma20'], target)
        return max(0, min(10, int(round(target))))

    def _target_result(self, target: int, weakening_count: int, return_tuple: bool):
        if return_tuple:
            return target, weakening_count
        return target

    def _target_from_row(self, row: pd.Series, previous: int = None,
                         weakening_count: int = None):
        """Calculate target position with semantic rules.

        Returns target by default. When weakening_count is provided, returns
        (target, updated_weakening_count) for sequential signal generation.

        MA20 filter is context-dependent:
        - Entry states: still require price > MA20 (bad entries in downtrends are costly)
        - STRONG_BULL: relaxed, hold regardless of MA20
        - BULL_WEAKENING: below MA20 accelerates reduction
        """
        return_tuple = weakening_count is not None
        weakening_count = int(weakening_count or 0)

        if not self.params.get('semantic_position_rules', True):
            return self._target_result(self._raw_target_from_row(row), 0, return_tuple)

        state = row['hist_state']
        previous = int(previous or 0)
        close = row.get('close', 0)
        ma20 = row.get('ma20', 0)
        below_ma20 = close < ma20

        # STRONG_BEAR / JUST_CROSSED_DOWN: always clear
        if state in {'STRONG_BEAR', 'JUST_CROSSED_DOWN'}:
            return self._target_result(0, 0, return_tuple)

        # Entry states: require MA20 support for full entry
        if state in {'BEAR_TO_BULL', 'JUST_CROSSED_UP'}:
            if below_ma20:
                return self._target_result(0, 0, return_tuple)
            return self._target_result(self._raw_target_from_row(row), 0, return_tuple)

        # STRONG_BULL: hold or increment (only above MA20 for increment)
        if state == 'STRONG_BULL':
            if self.params.get('strong_bull_increment', True):
                accel = row.get('hist_acceleration', 'STEADY')
                if accel == 'ACCELERATING' and not below_ma20 and previous < 10:
                    return self._target_result(min(10, previous + 1), 0, return_tuple)
            # Hold position even below MA20 (trend is established)
            return self._target_result(previous, 0, return_tuple)

        # BULL_WEAKENING: graduated reduction with recovery, MA20-aware
        if state == 'BULL_WEAKENING':
            reduce_step = self.params.get('weakening_reduce_step', 1)
            direction = row.get('hist_direction', 'SHRINKING')
            recovery_days = self.params.get('weakening_recovery_days', 3)

            # If histogram is expanding again, count recovery days
            if direction == 'EXPANDING':
                new_count = weakening_count + 1
                if new_count >= recovery_days:
                    # Recovered: treat as STRONG_BULL
                    if self.params.get('strong_bull_increment', True):
                        accel = row.get('hist_acceleration', 'STEADY')
                        if accel == 'ACCELERATING' and not below_ma20 and previous < 10:
                            return self._target_result(min(10, previous + 1), 0, return_tuple)
                    return self._target_result(previous, 0, return_tuple)
                # Still counting: don't reduce yet
                return self._target_result(previous, new_count, return_tuple)
            else:
                # Shrinking/flat: below MA20 accelerates exit
                step = reduce_step * 2 if below_ma20 else reduce_step
                return self._target_result(max(0, previous - step), 0, return_tuple)

        return self._target_result(previous, 0, return_tuple)

    def _apply_position_debounce(self, target: int, previous: int, min_change: int = None) -> int:
        if min_change is None:
            min_change = self.params.get('min_position_change', 2)
        if min_change <= 1:
            return target
        if target != previous and abs(target - previous) < min_change:
            return previous
        return target

    def _ma20_slope(self, df: pd.DataFrame, lookback: int) -> pd.Series:
        ma = df['ma20']
        result = pd.Series('FLAT', index=df.index)
        result[ma > ma.shift(lookback)] = 'UP'
        result[ma < ma.shift(lookback)] = 'DOWN'
        return result

    def _build_reason(self, state: str, direction: str, accel: str,
                      base: int, accel_adj: int, ma20_adj: int, vol_adj: int = 0) -> str:
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
        if vol_adj > 0:
            parts.append('低波动加仓')
        elif vol_adj < 0:
            parts.append('高波动降仓')
        return '+'.join(parts)
