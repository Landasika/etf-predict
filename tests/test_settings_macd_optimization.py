from pathlib import Path

from core.data_update_scheduler import DataUpdateScheduler


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_HTML = ROOT / "templates" / "settings.html"
SETTINGS_JS = ROOT / "static" / "js" / "settings.js"


def test_settings_page_exposes_macd_optimization_schedule_controls():
    html = SETTINGS_HTML.read_text(encoding="utf-8")
    source = SETTINGS_JS.read_text(encoding="utf-8")

    assert "MACD 参数优化" in html
    assert 'id="macdOptimizationEnabled"' in html
    assert 'id="macdOptimizationTime"' in html
    assert 'id="macdOptimizationNotifyFeishu"' in html
    assert 'src="/static/js/settings.js?v=' in html

    assert "macd_optimization_schedule" in source
    assert "macdOptimizationEnabled" in source
    assert "macdOptimizationTime" in source
    assert "macdOptimizationNotifyFeishu" in source
    assert "/api/macd/optimization/schedule/configure" in source


def test_scheduler_restores_macd_optimization_feishu_notification_setting():
    scheduler = DataUpdateScheduler()

    try:
        scheduler.restore_from_config({
            "update_schedule": {"enabled": False, "time": "15:05"},
            "feishu_notification_schedule": {
                "enabled": False,
                "times": "09:40,10:40",
            },
            "realtime_updater_schedule": {"enabled": False},
            "macd_optimization_schedule": {
                "enabled": True,
                "time": "23:00",
                "notify_feishu": True,
            },
        })

        status = scheduler.get_status()["macd_optimization"]

        assert status["enabled"] is True
        assert status["time"] == "23:00"
        assert status["notify_feishu"] is True
    finally:
        scheduler.stop()
