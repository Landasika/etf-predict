import pytest


def _patch_single_etf_watchlist(monkeypatch, feishu_report):
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


class _FakeCursor:
    def __init__(self, result):
        self.result = result

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchone(self):
        return self.result


class _FakeConnection:
    def __init__(self, result):
        self.result = result
        self.closed = False

    def cursor(self):
        return _FakeCursor(self.result)

    def close(self):
        self.closed = True


def test_load_data_uses_shared_feishu_rows_without_recomputing_signals(monkeypatch):
    from core import feishu_report, watchlist

    _patch_single_etf_watchlist(monkeypatch, feishu_report)
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


def test_load_data_does_not_fallback_to_database_when_shared_rows_raise(monkeypatch):
    from core import feishu_report

    _patch_single_etf_watchlist(monkeypatch, feishu_report)

    def raise_shared_row_error():
        raise RuntimeError("shared rows failed")

    def fail_if_database_fallback():
        raise AssertionError("Unexpected shared row errors must not use DB fallback")

    monkeypatch.setattr(feishu_report, "build_feishu_operation_rows", raise_shared_row_error)
    monkeypatch.setattr(feishu_report, "get_etf_connection", fail_if_database_fallback)

    report = feishu_report.ETFOperationReport()

    assert report.load_data() is False
    assert report.etf_data == {}


@pytest.mark.parametrize(
    "shared_result",
    [
        {
            "data": [
                {
                    "code": "562360.SH",
                    "name": "ETF A Shared",
                }
            ]
        },
        {
            "success": None,
            "data": [
                {
                    "code": "562360.SH",
                    "name": "ETF A Shared",
                }
            ],
        },
        {
            "success": 1,
            "data": [
                {
                    "code": "562360.SH",
                    "name": "ETF A Shared",
                }
            ],
        },
        {
            "success": 0,
            "data": [
                {
                    "code": "562360.SH",
                    "name": "ETF A Shared",
                }
            ],
        },
    ],
)
def test_load_data_does_not_fallback_to_database_when_shared_payload_metadata_is_malformed(
    monkeypatch, shared_result
):
    from core import feishu_report

    _patch_single_etf_watchlist(monkeypatch, feishu_report)

    def fail_if_database_fallback():
        raise AssertionError("Malformed shared row metadata must not use DB fallback")

    monkeypatch.setattr(
        feishu_report,
        "build_feishu_operation_rows",
        lambda: shared_result,
    )
    monkeypatch.setattr(feishu_report, "get_etf_connection", fail_if_database_fallback)

    report = feishu_report.ETFOperationReport()

    assert report.load_data() is False
    assert report.etf_data == {}


def test_load_data_does_not_fallback_to_database_when_shared_row_mapping_fails(monkeypatch):
    from core import feishu_report

    _patch_single_etf_watchlist(monkeypatch, feishu_report)

    def fail_if_database_fallback():
        raise AssertionError("Malformed shared rows must not use DB fallback")

    monkeypatch.setattr(
        feishu_report,
        "build_feishu_operation_rows",
        lambda: {"success": True, "data": [None]},
    )
    monkeypatch.setattr(feishu_report, "get_etf_connection", fail_if_database_fallback)

    report = feishu_report.ETFOperationReport()

    assert report.load_data() is False
    assert report.etf_data == {}


def test_load_data_falls_back_to_database_when_shared_success_is_false(monkeypatch):
    from core import feishu_report

    _patch_single_etf_watchlist(monkeypatch, feishu_report)
    monkeypatch.setattr(
        feishu_report,
        "build_feishu_operation_rows",
        lambda: {"success": False, "data": []},
    )
    monkeypatch.setattr(
        feishu_report,
        "get_etf_connection",
        lambda: _FakeConnection((1.234, 2.5, "20260603", "ETF A DB [4仓]")),
    )

    report = feishu_report.ETFOperationReport()

    assert report.load_data() is True
    assert report.etf_data == {
        "562360.SH": {
            "name": "ETF A DB",
            "close": 1.234,
            "pct_chg": 2.5,
            "trade_date": "20260603",
            "previous_positions_used": 4,
            "positions_used": 4,
            "daily_profit": 0,
        }
    }


@pytest.mark.parametrize("shared_data", [[], None])
def test_load_data_does_not_fallback_when_shared_success_is_true_without_data(
    monkeypatch, shared_data
):
    from core import feishu_report

    _patch_single_etf_watchlist(monkeypatch, feishu_report)
    monkeypatch.setattr(
        feishu_report,
        "build_feishu_operation_rows",
        lambda: {"success": True, "data": shared_data},
    )

    def fail_if_database_fallback():
        raise AssertionError("Successful shared row payloads must not use DB fallback")

    monkeypatch.setattr(feishu_report, "get_etf_connection", fail_if_database_fallback)

    report = feishu_report.ETFOperationReport()

    assert report.load_data() is False
    assert report.etf_data == {}
