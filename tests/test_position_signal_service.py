import pytest


def test_build_position_signal_rows_builds_row_with_daily_profit(monkeypatch):
    from core import database, position_manager, position_signal_service, watchlist

    monkeypatch.setattr(database, "get_latest_data_date", lambda: "20260603")
    monkeypatch.setattr(database, "get_batch_cache", lambda *args, **kwargs: None)
    saved_cache = {}
    monkeypatch.setattr(
        database,
        "set_batch_cache",
        lambda cache_type, data_date, data: saved_cache.update(
            {"cache_type": cache_type, "data_date": data_date, "data": data}
        ),
    )
    monkeypatch.setattr(watchlist, "load_watchlist", lambda: {"etfs": [{
        "code": "562360.SH",
        "strategy": "macd_aggressive",
        "strategy_name": "MACD",
        "total_positions": 10,
        "position_value": 200,
        "remark": "core holding",
    }]})
    monkeypatch.setattr(database, "get_etf_info", lambda code: {"extname": "ETF A"})
    monkeypatch.setattr(database, "get_etf_daily_data", lambda code: [
        {"trade_date": "20260602", "close": 100},
        {"trade_date": "20260603", "close": 105},
    ])
    monkeypatch.setattr(position_manager, "get_position", lambda code: {"current_positions": 3})
    monkeypatch.setattr(position_manager, "get_all_positions", lambda: [{
        "etf_code": "562360.SH",
        "current_positions": 3,
        "total_shares": 600,
        "avg_cost": 1.2,
    }])
    monkeypatch.setattr(position_signal_service, "calculate_monthly_profit", lambda *args: 12.5)
    monkeypatch.setattr(watchlist, "calculate_realtime_signal", lambda *args: {
        "success": True,
        "data": {
            "latest_date": "20260603",
            "latest_data": {
                "signal_type": "BUY",
                "signal_strength": 8,
                "macd_dif": 0.1,
                "macd_dea": 0.05,
                "macd_hist": 0.03,
                "previous_positions_used": 2,
                "kdj_k": 55,
                "kdj_d": 50,
                "kdj_j": 65,
                "fusion_level": 2,
                "kdj_position_cap": 7,
                "close": 105,
            },
            "backtest_summary": {"buy_hold_return_pct": 4.2},
            "positions_used": 5,
            "profit": 20,
            "profit_pct": 10,
            "next_action": "BUY",
        },
    })

    result = position_signal_service.build_position_signal_rows()

    assert result["success"] is True
    assert result["cached"] is False
    assert result["data_date"] == "20260603"
    assert result["count"] == 1
    row = result["data"][0]
    assert row["code"] == "562360.SH"
    assert row["name"] == "ETF A"
    assert row["signal"] == "BUY"
    assert row["signal_name"] == "买入"
    assert row["previous_positions_used"] == 2
    assert row["today_action_count"] == 3
    assert row["today_operation"] == "买入3仓"
    assert row["daily_change_pct"] == pytest.approx(5.0)
    assert row["daily_profit"] == pytest.approx(3 * 200 * 5.0 / 100)
    assert row["monthly_profit"] == 12.5
    assert row["slot_value"] == 200
    assert row["db_position"] == 3
    assert row["db_shares"] == 600
    assert row["db_avg_cost"] == 1.2
    assert row["data_date"] == "20260603"
    assert row["remark"] == "core holding"
    assert saved_cache["cache_type"] == "signals"
    assert saved_cache["data_date"] == "20260603_20250101"


def test_build_position_signal_rows_uses_cache_after_lock_even_when_refresh(monkeypatch):
    from core import database, position_manager, position_signal_service, watchlist

    monkeypatch.setattr(position_signal_service, "_is_after_position_grid_lock_time", lambda now=None: True)
    monkeypatch.setattr(database, "get_latest_data_date", lambda: "20260603")
    monkeypatch.setattr(database, "get_batch_cache", lambda cache_type, data_date: {
        "data": [{"code": "562360.SH", "data_date": "20260603"}],
        "count": 1,
    })
    monkeypatch.setattr(position_manager, "get_all_positions", lambda: [{
        "etf_code": "562360.SH",
        "current_positions": 4,
        "total_shares": 800,
        "avg_cost": 1.1,
    }])
    monkeypatch.setattr(position_signal_service, "calculate_monthly_profit", lambda *args: 9.0)

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("signals should not be recomputed after lock")

    monkeypatch.setattr(watchlist, "calculate_realtime_signal", fail_if_recomputed)

    result = position_signal_service.build_position_signal_rows(refresh=True)

    assert result["success"] is True
    assert result["cached"] is True
    assert result["data_date"] == "20260603"
    assert result["data"][0]["code"] == "562360.SH"
    assert result["data"][0]["db_position"] == 4
    assert result["data"][0]["slot_value"] == 200
    assert result["data"][0]["monthly_profit"] == 9.0


def test_build_position_signal_rows_rederives_actual_position_fields_from_cached_rows(monkeypatch):
    from core import database, position_manager, position_signal_service, watchlist

    cached_row = {
        "code": "562360.SH",
        "data_date": "20260603",
        "positions_used": 5,
        "daily_change_pct": 5.0,
        "daily_profit": 30.0,
        "today_action_count": 2,
        "today_operation": "买入2仓",
        "action_reason": "old reason",
        "latest_data": {
            "signal_type": "BUY",
            "signal_strength": 8,
            "macd_dif": 0.1,
            "macd_dea": 0.05,
            "previous_positions_used": 2,
            "kdj_k": 50,
        },
    }

    monkeypatch.setattr(position_signal_service, "_is_after_position_grid_lock_time", lambda now=None: True)
    monkeypatch.setattr(database, "get_latest_data_date", lambda: "20260603")
    monkeypatch.setattr(database, "get_batch_cache", lambda cache_type, data_date: {
        "data": [cached_row],
        "count": 1,
    })
    monkeypatch.setattr(position_manager, "get_all_positions", lambda: [{
        "etf_code": "562360.SH",
        "current_positions": 4,
        "total_shares": 800,
        "avg_cost": 1.1,
    }])
    monkeypatch.setattr(position_signal_service, "calculate_monthly_profit", lambda *args: 9.0)

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("cached signals should not recompute strategy output after lock")

    monkeypatch.setattr(watchlist, "calculate_realtime_signal", fail_if_recomputed)

    result = position_signal_service.build_position_signal_rows(refresh=True)

    row = result["data"][0]
    assert row["db_position"] == 4
    assert row["previous_positions_used"] == 2
    assert row["today_action_count"] == 3
    assert row["today_operation"] == "买入3仓"
    assert row["daily_profit"] == pytest.approx(4 * 200 * 5.0 / 100)
    assert row["monthly_profit"] == 9.0
    assert row["action_reason"] != "old reason"
    assert cached_row["today_operation"] == "买入2仓"


def test_build_position_signal_rows_copies_cached_rows_before_enriching(monkeypatch):
    from core import database, position_manager, position_signal_service

    cached_row = {"code": "562360.SH", "data_date": "20260603"}
    cached_payload = {
        "data": [cached_row],
        "count": 1,
    }

    monkeypatch.setattr(position_signal_service, "_is_after_position_grid_lock_time", lambda now=None: True)
    monkeypatch.setattr(database, "get_latest_data_date", lambda: "20260603")
    monkeypatch.setattr(database, "get_batch_cache", lambda cache_type, data_date: cached_payload)
    monkeypatch.setattr(position_manager, "get_all_positions", lambda: [{
        "etf_code": "562360.SH",
        "current_positions": 4,
        "total_shares": 800,
        "avg_cost": 1.1,
    }])
    monkeypatch.setattr(position_signal_service, "calculate_monthly_profit", lambda *args: 9.0)

    result = position_signal_service.build_position_signal_rows(refresh=True)

    assert result["data"][0] is not cached_row
    assert result["data"][0]["db_position"] == 4
    assert result["data"][0]["monthly_profit"] == 9.0
    assert cached_row == {"code": "562360.SH", "data_date": "20260603"}
