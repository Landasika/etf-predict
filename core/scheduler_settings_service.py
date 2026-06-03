"""Scheduler settings read/write service."""

import config
from core.data_update_scheduler import get_scheduler


INVALID_TIME_MESSAGE = "无效的时间格式，请使用 HH:MM 格式"


def get_scheduler_settings_status() -> dict:
    scheduler = get_scheduler()
    return {
        "success": True,
        "data": scheduler.get_status(),
    }


def configure_data_update_schedule(enabled: bool, update_time: str) -> dict:
    scheduler = get_scheduler()

    if not scheduler.set_update_time(update_time):
        raise ValueError(INVALID_TIME_MESSAGE)

    scheduler.set_enabled(enabled)

    if not config.update_config({
        "update_schedule": {
            "enabled": enabled,
            "time": update_time,
        }
    }):
        raise RuntimeError("保存调度器配置失败")

    return {
        "success": True,
        "message": f"调度器已{'启用' if enabled else '禁用'}，更新时间: {update_time}",
        "data": scheduler.get_status(),
    }


def configure_feishu_notification_schedule(enabled: bool, times: list[str]) -> dict:
    scheduler = get_scheduler()

    if not scheduler.set_feishu_notification_times(times):
        raise ValueError(INVALID_TIME_MESSAGE)

    scheduler.set_feishu_notification_enabled(enabled)

    if not config.update_config({
        "feishu_notification_schedule": {
            "enabled": enabled,
            "times": ",".join(scheduler.feishu_notification_times),
        }
    }):
        raise RuntimeError("保存飞书定时发送配置失败")

    return {
        "success": True,
        "message": "飞书消息定时发送配置已更新",
        "data": scheduler.get_status(),
    }


def configure_macd_optimization_schedule(
    enabled: bool,
    opt_time: str,
    notify_feishu: bool,
) -> dict:
    scheduler = get_scheduler()

    if not scheduler.set_macd_optimization_time(opt_time):
        raise ValueError(INVALID_TIME_MESSAGE)

    scheduler.set_macd_optimization_enabled(enabled)
    scheduler.set_macd_optimization_notify_feishu(bool(notify_feishu))

    if not config.update_config({
        "macd_optimization_schedule": {
            "enabled": enabled,
            "time": opt_time,
            "lookback_days": 365,
            "notify_feishu": bool(notify_feishu),
        }
    }):
        raise RuntimeError("保存MACD优化调度配置失败")

    return {
        "success": True,
        "message": (
            f"MACD参数优化定时任务已{'启用' if enabled else '禁用'}，"
            f"执行时间: {opt_time}"
        ),
        "data": scheduler.get_status(),
    }
