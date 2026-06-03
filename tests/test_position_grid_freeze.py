import pytest

from api import main as api_main
from core import position_signal_service


@pytest.mark.asyncio
async def test_batch_signals_refresh_uses_cache_after_close(monkeypatch):
    monkeypatch.setattr(position_signal_service, "_is_after_position_grid_lock_time", lambda now=None: True)

    from core import database, position_manager, watchlist

    monkeypatch.setattr(database, "get_latest_data_date", lambda: "20260603")
    monkeypatch.setattr(
        database,
        "get_batch_cache",
        lambda cache_type, data_date: {
            "data": [{"code": "562360.SH", "data_date": "20260603"}],
            "count": 1,
        },
    )
    monkeypatch.setattr(position_manager, "get_all_positions", lambda: [])
    monkeypatch.setattr(position_signal_service, "calculate_monthly_profit", lambda *args, **kwargs: 0)

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("signals should not be recomputed after close")

    monkeypatch.setattr(watchlist, "calculate_realtime_signal", fail_if_recomputed)

    result = await api_main.get_batch_signals(refresh=True)

    assert result["success"] is True
    assert result["cached"] is True
    assert result["data_date"] == "20260603"
    assert result["data"][0]["code"] == "562360.SH"
