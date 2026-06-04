def test_nightly_review_report_includes_recap_operations_and_optimization(monkeypatch):
    from core import nightly_review_report

    monkeypatch.setattr(nightly_review_report, "build_feishu_operation_rows", lambda: {
        "success": True,
        "data_date": "20260604",
        "data": [
            {
                "code": "512690.SH",
                "name": "酒ETF",
                "pct_chg": -2.48,
                "daily_profit": -24.77,
                "previous_positions_used": 5,
                "positions_used": 0,
                "today_action_count": -5,
                "today_operation": "卖出5仓",
            },
            {
                "code": "563380.SH",
                "name": "航空航天ETF",
                "pct_chg": -0.39,
                "daily_profit": 0,
                "previous_positions_used": 0,
                "positions_used": 2,
                "today_action_count": 2,
                "today_operation": "买入2仓",
            },
            {
                "code": "159870.SZ",
                "name": "化工ETF",
                "pct_chg": -1.93,
                "daily_profit": -19.28,
                "previous_positions_used": 5,
                "positions_used": 5,
                "today_action_count": 0,
                "today_operation": "持有",
            },
        ],
    })

    report = nightly_review_report.generate_nightly_review_report({
        "last_result": "成功: 2/2",
        "completed_etfs": 2,
        "failed_etfs": 0,
        "total_etfs": 2,
        "changed_params": [
            {
                "code": "512690.SH",
                "name": "酒ETF",
                "old_params": {"macd_fast": 8, "macd_slow": 17, "macd_signal": 5},
                "new_params": {"macd_fast": 10, "macd_slow": 21, "macd_signal": 7},
                "return_pct": 12.3,
            }
        ],
    })

    assert "# 🌙 ETF 夜间复盘" in report
    assert "20260604" in report
    assert "今日总收益 | ¥-44.05" in report
    assert "卖出 | 1个 | 共5仓" in report
    assert "买入 | 1个 | 共2仓" in report
    assert "酒ETF | `512690.SH` | 8/17/5 -> 10/21/7 | 12.30%" in report
    assert "## 🔭 明日重点关注" in report
    assert "酒ETF | 卖出5仓 | 5->0" in report
    assert "航空航天ETF | 买入2仓 | 0->2" in report


def test_nightly_review_report_handles_no_parameter_changes(monkeypatch):
    from core import nightly_review_report

    monkeypatch.setattr(nightly_review_report, "build_feishu_operation_rows", lambda: {
        "success": True,
        "data_date": "20260604",
        "data": [],
    })

    report = nightly_review_report.generate_nightly_review_report({
        "last_result": "成功: 0/0",
        "completed_etfs": 0,
        "failed_etfs": 0,
        "total_etfs": 0,
        "changed_params": [],
    })

    assert "参数无变化" in report
    assert "今日无调仓建议" in report


def test_macd_optimization_notify_feishu_sends_nightly_review(monkeypatch):
    from core.data_update_scheduler import DataUpdateScheduler

    scheduler = DataUpdateScheduler()
    scheduler.macd_optimization_status["completed_etfs"] = 1

    sent = {}

    def fake_generate_report(status):
        sent["status"] = status
        return "nightly report"

    monkeypatch.setattr(
        "core.nightly_review_report.generate_nightly_review_report",
        fake_generate_report,
    )

    class FakeNotifier:
        async def send_message(self, message, title=None):
            sent["message"] = message
            sent["title"] = title
            return True

    monkeypatch.setattr("core.feishu_notifier.get_feishu_notifier", lambda: FakeNotifier())

    scheduler._send_nightly_review_notification()

    assert sent["message"] == "nightly report"
    assert sent["title"] == "🌙 ETF夜间复盘"
    assert sent["status"] is scheduler.macd_optimization_status


def test_macd_optimization_captures_changed_params(monkeypatch):
    from core.data_update_scheduler import DataUpdateScheduler
    from core import watchlist
    from strategies import macd_param_optimizer

    saved = {}
    monkeypatch.setattr(watchlist, "load_watchlist", lambda: {
        "etfs": [
            {
                "code": "512690.SH",
                "name": "酒ETF",
                "strategy": "macd_aggressive",
                "optimized_macd_params": {
                    "macd_fast": 8,
                    "macd_slow": 17,
                    "macd_signal": 5,
                },
            }
        ],
    })
    monkeypatch.setattr(watchlist, "save_watchlist", lambda data: saved.setdefault("watchlist", data))

    class FakeOptimizer:
        def __init__(self, etf_code, lookback_days=365):
            self.etf_code = etf_code
            self.lookback_days = lookback_days

        def optimize(self):
            return {
                "best_params": {
                    "macd_fast": 10,
                    "macd_slow": 21,
                    "macd_signal": 7,
                },
                "metrics": {
                    "total_return_pct": 12.3,
                },
            }

    monkeypatch.setattr(macd_param_optimizer, "MACDParamOptimizer", FakeOptimizer)

    scheduler = DataUpdateScheduler()
    scheduler._run_macd_optimization()

    assert scheduler.macd_optimization_status["changed_params"] == [
        {
            "code": "512690.SH",
            "name": "酒ETF",
            "old_params": {
                "macd_fast": 8,
                "macd_slow": 17,
                "macd_signal": 5,
            },
            "new_params": {
                "macd_fast": 10,
                "macd_slow": 21,
                "macd_signal": 7,
            },
            "return_pct": 12.3,
        }
    ]
    assert saved["watchlist"]["etfs"][0]["optimized_macd_params"]["macd_fast"] == 10
