def test_load_data_uses_shared_feishu_rows_without_recomputing_signals(monkeypatch):
    from core import feishu_report, watchlist

    monkeypatch.setattr(
        feishu_report,
        "load_watchlist",
        lambda: {
            "etfs": [
                {
                    "code": "562360.SH",
                    "name": "ETF A",
                    "sector": "Tech",
                    "total_positions": 10,
                }
            ]
        },
    )
    monkeypatch.setattr(
        feishu_report,
        "build_feishu_operation_rows",
        lambda: {
            "success": True,
            "data": [
                {
                    "code": "562360.SH",
                    "name": "ETF A Shared",
                    "close": 1.234,
                    "pct_chg": 2.5,
                    "previous_positions_used": 3,
                    "positions_used": 5,
                    "daily_profit": 15.0,
                    "today_action_count": 2,
                    "today_operation": "买入2仓",
                    "action_reason": "shared reason",
                    "next_action": "next shared action",
                    "signal_type": "BUY",
                    "signal_strength": 8,
                    "total_positions": 12,
                }
            ],
        },
    )

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("Feishu report should consume shared rows")

    monkeypatch.setattr(watchlist, "calculate_realtime_signal", fail_if_recomputed)

    report = feishu_report.ETFOperationReport()

    assert report.load_data() is True
    assert report.etf_data == {
        "562360.SH": {
            "name": "ETF A Shared",
            "close": 1.234,
            "pct_chg": 2.5,
            "previous_positions_used": 3,
            "positions_used": 5,
            "daily_profit": 15.0,
            "today_action_count": 2,
            "today_operation": "买入2仓",
            "action_reason": "shared reason",
            "next_action": "next shared action",
            "signal_type": "BUY",
            "signal_strength": 8,
            "total_positions": 12,
        }
    }
