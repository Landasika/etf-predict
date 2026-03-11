"""
数据更新调度器

使用Python schedule库实现定时任务
支持通过API动态配置和执行
"""

import schedule
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
import sys
import os
import config

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入统一的日志配置
from core.logging_config import setup_logger

# 配置日志
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# 使用轮转日志：单个文件最大10MB，保留5个备份
logger = setup_logger(
    name='data_update_scheduler',
    log_file=LOG_DIR / 'data_update_scheduler.log',
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=5
)


class DataUpdateScheduler:
    """数据更新调度器"""

    def __init__(self):
        self.is_running = False
        self.scheduler_thread = None
        self.update_time = config.DEFAULT_UPDATE_TIME
        self.enabled = False  # 默认关闭
        self.current_job = None
        self.update_status = {
            'is_updating': False,
            'progress': 0,
            'total': 0,
            'current': '',
            'success_count': 0,
            'fail_count': 0,
            'message': '',
            'last_update': None,
            'last_result': None
        }

        # 实时更新器
        self.realtime_updater = None
        self.realtime_enabled = False

        # 飞书消息定时发送配置
        self.feishu_notification_enabled = False
        self.feishu_notification_times = config.DEFAULT_FEISHU_NOTIFICATION_TIMES.copy()
        self.feishu_notification_status = {
            'is_sending': False,
            'last_send': None,
            'last_result': None,
            'success_count': 0,
            'fail_count': 0
        }

    def _has_enabled_schedules(self) -> bool:
        """是否至少启用了一个定时任务"""
        return self.enabled or self.feishu_notification_enabled

    def _sync_scheduler_state(self):
        """根据当前开关状态启动、停止或重载调度器"""
        if self._has_enabled_schedules():
            if self.is_running:
                self._reschedule()
            else:
                self.start()
        elif self.is_running:
            self.stop()

    def restore_from_config(self, config_data=None):
        """从配置文件恢复调度器设置"""
        config_data = config_data or config.get_config()

        update_schedule = config_data.get('update_schedule', {})
        feishu_schedule = config_data.get('feishu_notification_schedule', {})

        update_time = update_schedule.get('time', config.DEFAULT_UPDATE_TIME)
        if not self.set_update_time(update_time):
            self.set_update_time(config.DEFAULT_UPDATE_TIME)

        feishu_times = feishu_schedule.get('times', config.DEFAULT_FEISHU_NOTIFICATION_TIMES)
        if not isinstance(feishu_times, list) or not feishu_times:
            feishu_times = config.DEFAULT_FEISHU_NOTIFICATION_TIMES.copy()
        if not self.set_feishu_notification_times(feishu_times):
            self.set_feishu_notification_times(config.DEFAULT_FEISHU_NOTIFICATION_TIMES.copy())

        self.set_enabled(bool(update_schedule.get('enabled', False)))
        self.set_feishu_notification_enabled(bool(feishu_schedule.get('enabled', False)))

        logger.info(
            "✅ 调度器配置已恢复: 数据更新=%s, 飞书定时=%s",
            self.enabled,
            self.feishu_notification_enabled
        )

    def set_realtime_enabled(self, enabled: bool):
        """启用/禁用实时更新

        Args:
            enabled: True启用，False禁用
        """
        self.realtime_enabled = enabled

        if enabled:
            from core.realtime_data_updater import RealtimeDataUpdater
            if self.realtime_updater is None:
                self.realtime_updater = RealtimeDataUpdater()
            self.realtime_updater.start()
            logger.info("✅ 实时更新已启用")
        else:
            if self.realtime_updater:
                self.realtime_updater.stop()
            logger.info("⏹️  实时更新已禁用")

    def get_realtime_status(self) -> dict:
        """获取实时更新状态"""
        if self.realtime_updater:
            status = self.realtime_updater.get_status()
            status['enabled'] = self.realtime_enabled
            return status
        else:
            return {
                'enabled': self.realtime_enabled,
                'is_running': False,
                'start_time': '09:25',
                'end_time': '15:05',
                'update_interval': 60,
                'update_status': {
                    'is_updating': False,
                    'last_update': None,
                    'etf_count': 0,
                    'success_count': 0,
                    'fail_count': 0
                }
            }

    def set_realtime_settings(self, start_time: str, end_time: str, update_interval: int) -> bool:
        """设置实时更新参数

        Args:
            start_time: 开始时间 "HH:MM"
            end_time: 结束时间 "HH:MM"
            update_interval: 更新间隔（秒）

        Returns:
            bool: 是否设置成功
        """
        if self.realtime_updater:
            # 设置时间范围
            success = self.realtime_updater.set_time_range(start_time, end_time)
            if success:
                self.realtime_updater.update_interval = update_interval
            return success
        else:
            logger.warning("实时更新器未初始化")
            return False

    def set_feishu_notification_times(self, times: list) -> bool:
        """设置飞书消息发送时间

        Args:
            times: 时间列表，格式 ["HH:MM", "HH:MM", ...]

        Returns:
            bool: 是否设置成功
        """
        try:
            # 验证时间格式
            validated_times = []
            for time_str in times:
                datetime.strptime(time_str, '%H:%M')
                validated_times.append(time_str)

            self.feishu_notification_times = validated_times
            logger.info(f"飞书消息发送时间已设置为: {', '.join(validated_times)}")

            # 如果调度器正在运行，重新调度
            if self.is_running:
                self._reschedule()

            return True
        except ValueError as e:
            logger.error(f"无效的时间格式: {e}")
            return False

    def set_feishu_notification_enabled(self, enabled: bool):
        """启用/禁用飞书消息定时发送

        Args:
            enabled: True启用，False禁用
        """
        self.feishu_notification_enabled = enabled
        logger.info(f"飞书消息定时发送已{'启用' if enabled else '禁用'}")
        self._sync_scheduler_state()

    def _send_feishu_notification(self):
        """发送飞书消息任务"""
        logger.info("=" * 60)
        logger.info("📱 开始执行飞书消息发送任务")
        logger.info("=" * 60)

        self.feishu_notification_status['is_sending'] = True

        try:
            from core.feishu_notifier import get_feishu_notifier
            from core.feishu_report import generate_etf_operation_report

            notifier = get_feishu_notifier()

            # 生成ETF操作建议报告
            markdown_content = generate_etf_operation_report()

            if not markdown_content:
                logger.warning("⚠️  生成报告失败或无数据")
                self.feishu_notification_status['last_result'] = '生成报告失败'
                return

            # 发送消息
            import asyncio
            result = asyncio.run(notifier.send_message(markdown_content, title="🎯 ETF操作建议"))

            self.feishu_notification_status['last_send'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.feishu_notification_status['last_result'] = '成功' if result else '失败'

            if result:
                self.feishu_notification_status['success_count'] += 1
                logger.info("✅ 飞书消息发送成功")
            else:
                self.feishu_notification_status['fail_count'] += 1
                logger.warning("⚠️  飞书消息发送失败")

        except Exception as e:
            logger.error(f"❌ 飞书消息发送失败: {e}")
            self.feishu_notification_status['last_result'] = f'失败: {str(e)}'
            self.feishu_notification_status['fail_count'] += 1
        finally:
            self.feishu_notification_status['is_sending'] = False

    def set_update_time(self, time_str):
        """设置更新时间

        Args:
            time_str: 时间格式 "HH:MM"，如 "15:05"
        """
        try:
            # 验证时间格式
            datetime.strptime(time_str, '%H:%M')
            self.update_time = time_str
            logger.info(f"更新时间已设置为: {time_str}")

            # 如果调度器正在运行，重新调度
            if self.is_running:
                self._reschedule()

            return True
        except ValueError:
            logger.error(f"无效的时间格式: {time_str}")
            return False

    def set_enabled(self, enabled):
        """启用/禁用调度器

        Args:
            enabled: True启用，False禁用
        """
        self.enabled = enabled
        logger.info(f"调度器已{'启用' if enabled else '禁用'}")
        self._sync_scheduler_state()

    def _run_update(self):
        """执行更新任务"""
        logger.info("=" * 60)
        logger.info("🚀 开始执行定时更新任务")
        logger.info("=" * 60)

        self.update_status['is_updating'] = True
        self.update_status['progress'] = 0
        self.update_status['message'] = '正在更新数据...'

        try:
            from scripts.auto_update_data import run_auto_update

            # 执行更新
            success = run_auto_update(force=False)

            self.update_status['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.update_status['last_result'] = '成功' if success else '部分失败'
            self.update_status['message'] = '更新完成'

            logger.info(f"✅ 定时更新任务完成: {self.update_status['last_result']}")

        except Exception as e:
            logger.error(f"❌ 定时更新任务失败: {e}")
            self.update_status['last_result'] = '失败'
            self.update_status['message'] = f'更新失败: {str(e)}'
        finally:
            self.update_status['is_updating'] = False

    def _reschedule(self):
        """重新调度任务"""
        # 清除所有任务
        schedule.clear()

        # 如果启用，添加新任务
        if self.enabled:
            # 每个工作日执行数据更新
            schedule.every().monday.at(self.update_time).do(self._run_update)
            schedule.every().tuesday.at(self.update_time).do(self._run_update)
            schedule.every().wednesday.at(self.update_time).do(self._run_update)
            schedule.every().thursday.at(self.update_time).do(self._run_update)
            schedule.every().friday.at(self.update_time).do(self._run_update)

            logger.info(f"✅ 已调度更新任务: 每个工作日 {self.update_time}")

        # 如果启用飞书消息发送，添加飞书消息任务
        if self.feishu_notification_enabled:
            for time_str in self.feishu_notification_times:
                schedule.every().monday.at(time_str).do(self._send_feishu_notification)
                schedule.every().tuesday.at(time_str).do(self._send_feishu_notification)
                schedule.every().wednesday.at(time_str).do(self._send_feishu_notification)
                schedule.every().thursday.at(time_str).do(self._send_feishu_notification)
                schedule.every().friday.at(time_str).do(self._send_feishu_notification)

            logger.info(f"✅ 已调度飞书消息任务: 每个工作日 {', '.join(self.feishu_notification_times)}")

    def _run_scheduler(self):
        """调度器运行循环"""
        logger.info("📅 调度器线程已启动")
        self._reschedule()

        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次

        logger.info("📅 调度器线程已停止")

    def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("调度器已在运行")
            return False

        if not self._has_enabled_schedules():
            logger.warning("调度器没有可运行的定时任务")
            return False

        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("✅ 调度器已启动")
        return True

    def stop(self):
        """停止调度器"""
        if not self.is_running:
            logger.warning("调度器未运行")
            return False

        self.is_running = False
        schedule.clear()

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        logger.info("✅ 调度器已停止")
        return True

    def trigger_now(self):
        """立即触发一次更新（在新线程中执行）"""
        if self.update_status['is_updating']:
            logger.warning("⚠️  更新任务正在进行中")
            return False

        logger.info("🚀 手动触发更新任务")

        def run_in_thread():
            self._run_update()

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        return True

    def get_status(self):
        """获取调度器状态"""
        next_run = None
        if self.is_running and schedule.jobs:
            next_job = schedule.next_run()
            if next_job:
                next_run = next_job.strftime('%Y-%m-%d %H:%M:%S')

        return {
            'enabled': self.enabled,
            'is_running': self.is_running,
            'update_time': self.update_time,
            'next_run': next_run,
            'update_status': self.update_status.copy(),
            'feishu_notification': {
                'enabled': self.feishu_notification_enabled,
                'times': self.feishu_notification_times.copy(),
                'status': self.feishu_notification_status.copy()
            }
        }


# 全局调度器实例
scheduler = DataUpdateScheduler()


def get_scheduler():
    """获取调度器实例"""
    return scheduler


if __name__ == '__main__':
    # 测试代码
    s = get_scheduler()

    print("设置更新时间为 15:05...")
    s.set_update_time("15:05")

    print("启用调度器...")
    s.set_enabled(True)

    print("调度器状态:")
    status = s.get_status()
    print(f"  启用: {status['enabled']}")
    print(f"  运行中: {status['is_running']}")
    print(f"  更新时间: {status['update_time']}")
    print(f"  下次运行: {status['next_run']}")

    # 保持运行
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n停止调度器...")
        s.stop()
