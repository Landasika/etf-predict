import pandas as pd

from strategies.macd_histogram_momentum import MACDHistogramMomentumSignalGenerator


def _flat_row(**overrides):
    row = {
        "hist_state": "BEAR_TO_BULL",
        "hist_acceleration": "STEADY",
        "close": 10.0,
        "ma20": 10.0,
        "ma20_slope": "FLAT",
        "annual_volatility": 0.25,
    }
    row.update(overrides)
    return pd.Series(row)


def test_bear_to_bull_fast_histogram_shrink_adds_position():
    generator = MACDHistogramMomentumSignalGenerator()

    assert generator._accel_adjust("BEAR_TO_BULL", "DECELERATING") > 0
    assert generator._target_from_row(_flat_row(hist_acceleration="DECELERATING")) > generator._target_from_row(_flat_row())


def test_strong_bear_acceleration_reduces_position():
    generator = MACDHistogramMomentumSignalGenerator()

    assert generator._accel_adjust("STRONG_BEAR", "ACCELERATING") < 0


def test_volatility_layer_boosts_low_vol_reversal_and_reduces_high_vol_reversal():
    generator = MACDHistogramMomentumSignalGenerator({
        "volatility_filter": True,
        "low_vol_threshold": 0.20,
        "high_vol_threshold": 0.35,
    })

    low_vol_target = generator._target_from_row(_flat_row(annual_volatility=0.10))
    mid_vol_target = generator._target_from_row(_flat_row(annual_volatility=0.25))
    high_vol_target = generator._target_from_row(_flat_row(annual_volatility=0.45))

    assert low_vol_target > mid_vol_target
    assert high_vol_target < mid_vol_target


def test_small_position_change_is_debounced():
    generator = MACDHistogramMomentumSignalGenerator({"min_position_change": 2})

    assert generator._apply_position_debounce(target=5, previous=4) == 4
    assert generator._apply_position_debounce(target=6, previous=4) == 6


def test_strong_bear_never_opens_ma20_support_probe_position():
    generator = MACDHistogramMomentumSignalGenerator()

    target = generator._target_from_row(_flat_row(
        hist_state="STRONG_BEAR",
        hist_acceleration="ACCELERATING",
        close=10.5,
        ma20=10.0,
        ma20_slope="UP",
        annual_volatility=0.10,
    ), previous=0)

    assert target == 0


def test_strong_bull_holds_existing_position_without_chasing():
    generator = MACDHistogramMomentumSignalGenerator()

    assert generator._target_from_row(_flat_row(hist_state="STRONG_BULL"), previous=5) == 5
    assert generator._target_from_row(_flat_row(hist_state="STRONG_BULL"), previous=0) == 0


def test_bull_weakening_reduces_without_direct_clear():
    generator = MACDHistogramMomentumSignalGenerator({"weakening_reduce_step": 2})

    assert generator._target_from_row(_flat_row(hist_state="BULL_WEAKENING"), previous=8) == 6
    assert generator._target_from_row(_flat_row(hist_state="BULL_WEAKENING"), previous=1) == 0


def test_cross_down_or_ma20_break_exits_position():
    generator = MACDHistogramMomentumSignalGenerator()

    assert generator._target_from_row(_flat_row(hist_state="JUST_CROSSED_DOWN"), previous=5) == 0
    assert generator._target_from_row(_flat_row(hist_state="BEAR_TO_BULL", close=9.9, ma20=10.0), previous=5) == 0


def test_negative_histogram_half_peak_marks_bear_to_bull():
    generator = MACDHistogramMomentumSignalGenerator({"exhaustion_ratio": 0.5})
    df = pd.DataFrame({"macd_hist": [-0.002, -0.006, -0.010, -0.007, -0.004]})
    df["hist_direction"] = generator._hist_direction(df)
    df = generator._hist_cycle_peak_ratio(df)

    states = generator._classify_state(df, confirm_days=1).tolist()

    assert states[-1] == "BEAR_TO_BULL"
    assert df["hist_peak_ratio"].iloc[-1] == 0.4


def test_positive_histogram_half_peak_marks_bull_weakening():
    generator = MACDHistogramMomentumSignalGenerator({"exhaustion_ratio": 0.5})
    df = pd.DataFrame({"macd_hist": [0.002, 0.006, 0.010, 0.007, 0.004]})
    df["hist_direction"] = generator._hist_direction(df)
    df = generator._hist_cycle_peak_ratio(df)

    states = generator._classify_state(df, confirm_days=1).tolist()

    assert states[-1] == "BULL_WEAKENING"
    assert df["hist_peak_ratio"].iloc[-1] == 0.4
