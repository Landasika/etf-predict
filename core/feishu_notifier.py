"""
飞书推送核心模块
集成到ETF预测系统，支持策略信号推送、数据更新通知等
"""
import json
import os
import logging
from typing import Optional, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

# 飞书配置文件路径
FEISHU_CONFIG_PATH = Path(__file__).parent.parent / "data" / "feishu_config.json"


class FeishuNotifier:
    """飞书通知管理器"""

    def __init__(self):
        self.config = {}
        self.load_config()

    def load_config(self):
        """加载飞书配置"""
        try:
            if FEISHU_CONFIG_PATH.exists():
                with open(FEISHU_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"飞书配置加载成功: {len(self.config.get('bots', []))} 个机器人")
            else:
                # 创建默认配置
                self.config = {
                    "enabled": False,
                    "default_bot": "bot_1",
                    "bots": [
                        {
                            "id": "bot_1",
                            "name": "默认机器人",
                            "app_id": "",
                            "app_secret": "",
                            "chat_id": "",
                            "enabled": True
                        }
                    ],
                    "notifications": {
                        "signal_alerts": True,  # 信号提醒
                        "data_updates": False,  # 数据更新通知
                        "backtest_complete": False,  # 回测完成通知
                        "error_alerts": True  # 错误告警
                    }
                }
                self.save_config()
                logger.info("创建默认飞书配置")
        except Exception as e:
            logger.error(f"加载飞书配置失败: {e}")
            self.config = {"enabled": False, "bots": []}

    def save_config(self):
        """保存飞书配置"""
        try:
            FEISHU_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(FEISHU_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info("飞书配置已保存")
        except Exception as e:
            logger.error(f"保存飞书配置失败: {e}")

    def get_config(self) -> dict:
        """获取配置（用于API返回）"""
        # 隐藏敏感信息
        safe_config = self.config.copy()
        if "bots" in safe_config:
            for bot in safe_config["bots"]:
                if bot.get("app_secret"):
                    bot["app_secret"] = "******" if bot["app_secret"] else ""
        return safe_config

    def update_config(self, new_config: dict):
        """更新配置"""
        try:
            # 保留原有的app_secret（如果前端传的是******）
            if "bots" in new_config and "bots" in self.config:
                for new_bot in new_config["bots"]:
                    for old_bot in self.config["bots"]:
                        if (new_bot.get("id") == old_bot.get("id") and
                            new_bot.get("app_secret") == "******"):
                            new_bot["app_secret"] = old_bot.get("app_secret", "")

            self.config = new_config
            self.save_config()
            return True
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False

    def is_enabled(self) -> bool:
        """检查飞书通知是否启用"""
        return self.config.get("enabled", False)

    def get_bot(self, bot_id: Optional[str] = None) -> Optional[dict]:
        """获取指定机器人配置"""
        if not self.is_enabled():
            return None

        bot_id = bot_id or self.config.get("default_bot", "bot_1")
        for bot in self.config.get("bots", []):
            if bot.get("id") == bot_id and bot.get("enabled"):
                return bot
        return None

    async def send_message(self, message: str, bot_id: Optional[str] = None) -> bool:
        """发送消息到飞书"""
        if not self.is_enabled():
            logger.debug("飞书通知未启用")
            return False

        bot = self.get_bot(bot_id)
        if not bot:
            logger.warning(f"未找到可用的飞书机器人: {bot_id}")
            return False

        if not all([bot.get("app_id"), bot.get("app_secret"), bot.get("chat_id")]):
            logger.warning(f"飞书机器人配置不完整: {bot.get('name')}")
            return False

        try:
            from feishu_bot import FeishuBot
            feishu_bot = FeishuBot(
                app_id=bot["app_id"],
                app_secret=bot["app_secret"],
                chat_id=bot["chat_id"],
                name=bot.get("name", "default")
            )
            feishu_bot.send_text_message(message)
            logger.info(f"飞书消息发送成功: {bot.get('name')}")
            return True
        except Exception as e:
            logger.error(f"发送飞书消息失败: {e}")
            return False

    async def send_signal_alert(self, etf_code: str, etf_name: str, signal: str, strategy: str):
        """发送策略信号提醒"""
        if not self.config.get("notifications", {}).get("signal_alerts"):
            return

        signal_emoji = {
            "BUY": "🟢",
            "SELL": "🔴",
            "HOLD": "🟡"
        }.get(signal, "⚪")

        message = f"""{signal_emoji} 策略信号提醒

ETF: {etf_name} ({etf_code})
策略: {strategy}
信号: {signal}

时间: {self._get_current_time()}"""

        await self.send_message(message)

    async def send_data_update(self, success: bool, count: int = 0, error: str = ""):
        """发送数据更新通知"""
        if not self.config.get("notifications", {}).get("data_updates"):
            return

        if success:
            message = f"""✅ 数据更新完成

更新数量: {count} 个ETF
时间: {self._get_current_time()}"""
        else:
            message = f"""❌ 数据更新失败

错误: {error}
时间: {self._get_current_time()}"""

        await self.send_message(message)

    async def send_error_alert(self, error_type: str, error_message: str):
        """发送错误告警"""
        if not self.config.get("notifications", {}).get("error_alerts"):
            return

        message = f"""⚠️ 系统错误告警

错误类型: {error_type}
错误信息: {error_message}
时间: {self._get_current_time()}

请检查系统日志"""

        await self.send_message(message)

    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 全局单例
_feishu_notifier = None


def get_feishu_notifier() -> FeishuNotifier:
    """获取飞书通知器单例"""
    global _feishu_notifier
    if _feishu_notifier is None:
        _feishu_notifier = FeishuNotifier()
    return _feishu_notifier
