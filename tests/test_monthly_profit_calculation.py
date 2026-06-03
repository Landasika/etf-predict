import pytest

from api.main import _calculate_monthly_profit_from_rows, _calculate_slot_profit_series


def test_calculate_monthly_profit_uses_prior_position_snapshot():
    daily_rows = [
        {"trade_date": "20260601", "close": 100},
        {"trade_date": "20260602", "close": 102},
        {"trade_date": "20260603", "close": 101},
    ]
    snapshots = {
        "20260601": 3,
        "20260602": 5,
    }

    profit = _calculate_monthly_profit_from_rows(
        daily_rows=daily_rows,
        snapshot_positions=snapshots,
        fallback_positions=1,
        data_date="20260603",
    )

    assert profit == pytest.approx(3 * 200 * 0.02 + 5 * 200 * ((101 - 102) / 102))


def test_calculate_monthly_profit_falls_back_to_current_position_when_snapshots_missing():
    daily_rows = [
        {"trade_date": "20260601", "close": 100},
        {"trade_date": "20260602", "close": 101},
    ]

    profit = _calculate_monthly_profit_from_rows(
        daily_rows=daily_rows,
        snapshot_positions={},
        fallback_positions=4,
        data_date="20260602",
    )

    assert profit == pytest.approx(4 * 200 * 0.01)


def test_calculate_slot_profit_series_uses_prior_position_snapshot():
    daily_rows = [
        {"trade_date": "20260601", "close": 100},
        {"trade_date": "20260602", "close": 102},
        {"trade_date": "20260603", "close": 101},
    ]
    snapshots = {
        "20260601": 3,
        "20260602": 5,
    }

    series = _calculate_slot_profit_series(
        daily_rows=daily_rows,
        snapshot_positions=snapshots,
        fallback_positions=1,
        start_date="20260601",
    )

    assert series[0]["daily_profit"] == 0
    assert series[1]["daily_profit"] == pytest.approx(3 * 200 * 0.02)
    assert series[2]["daily_profit"] == pytest.approx(5 * 200 * ((101 - 102) / 102))
    assert series[2]["positions"] == 5
