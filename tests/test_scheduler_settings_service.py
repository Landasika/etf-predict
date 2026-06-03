import pytest

from core import scheduler_settings_service


class FakeScheduler:
    def __init__(self):
        self.update_time = "15:05"
        self.enabled = False
        self.feishu_notification_times = ["09:40"]
        self.feishu_notification_enabled = False
        self.macd_optimization_time = "23:00"
        self.macd_optimization_enabled = False
        self.macd_optimization_notify_feishu = False

    def set_update_time(self, update_time):
        if update_time == "bad-time":
            return False
        self.update_time = update_time
        return True

    def set_enabled(self, enabled):
        self.enabled = enabled

    def set_feishu_notification_times(self, times):
        if "bad-time" in times:
            return False
        self.feishu_notification_times = list(times)
        return True

    def set_feishu_notification_enabled(self, enabled):
        self.feishu_notification_enabled = enabled

    def set_macd_optimization_time(self, opt_time):
        if opt_time == "bad-time":
            return False
        self.macd_optimization_time = opt_time
        return True

    def set_macd_optimization_enabled(self, enabled):
        self.macd_optimization_enabled = enabled

    def set_macd_optimization_notify_feishu(self, enabled):
        self.macd_optimization_notify_feishu = enabled

    def get_status(self):
        return {
            "enabled": self.enabled,
            "update_time": self.update_time,
            "feishu_notification": {
                "enabled": self.feishu_notification_enabled,
                "times": self.feishu_notification_times,
            },
            "macd_optimization": {
                "enabled": self.macd_optimization_enabled,
                "time": self.macd_optimization_time,
                "notify_feishu": self.macd_optimization_notify_feishu,
            },
        }


@pytest.fixture
def fake_scheduler(monkeypatch):
    scheduler = FakeScheduler()
    monkeypatch.setattr(scheduler_settings_service, "get_scheduler", lambda: scheduler)
    return scheduler


@pytest.fixture
def persisted_updates(monkeypatch):
    updates = []

    def update_config(update):
        updates.append(update)
        return True

    monkeypatch.setattr(scheduler_settings_service.config, "update_config", update_config)
    return updates


def test_data_update_schedule_persists_config(fake_scheduler, persisted_updates):
    result = scheduler_settings_service.configure_data_update_schedule(True, "16:20")

    assert persisted_updates == [
        {"update_schedule": {"enabled": True, "time": "16:20"}}
    ]
    assert result["success"] is True
    assert result["message"] == "调度器已启用，更新时间: 16:20"
    assert result["data"] == fake_scheduler.get_status()


def test_invalid_data_update_time_raises_value_error(fake_scheduler, persisted_updates):
    with pytest.raises(ValueError, match="无效的时间格式"):
        scheduler_settings_service.configure_data_update_schedule(True, "bad-time")

    assert persisted_updates == []


def test_feishu_notification_schedule_persists_comma_joined_times(
    fake_scheduler, persisted_updates
):
    result = scheduler_settings_service.configure_feishu_notification_schedule(
        True, ["09:35", "14:55"]
    )

    assert persisted_updates == [
        {
            "feishu_notification_schedule": {
                "enabled": True,
                "times": "09:35,14:55",
            }
        }
    ]
    assert result["success"] is True
    assert result["message"] == "飞书消息定时发送配置已更新"
    assert result["data"] == fake_scheduler.get_status()


def test_macd_optimization_schedule_persists_notify_feishu(
    fake_scheduler, persisted_updates
):
    result = scheduler_settings_service.configure_macd_optimization_schedule(
        True, "22:15", True
    )

    assert persisted_updates == [
        {
            "macd_optimization_schedule": {
                "enabled": True,
                "time": "22:15",
                "lookback_days": 365,
                "notify_feishu": True,
            }
        }
    ]
    assert result["success"] is True
    assert result["message"] == "MACD参数优化定时任务已启用，执行时间: 22:15"
    assert result["data"] == fake_scheduler.get_status()


def test_failed_config_update_raises_runtime_error(monkeypatch, fake_scheduler):
    monkeypatch.setattr(scheduler_settings_service.config, "update_config", lambda _: False)

    with pytest.raises(RuntimeError, match="保存调度器配置失败"):
        scheduler_settings_service.configure_data_update_schedule(True, "16:20")
