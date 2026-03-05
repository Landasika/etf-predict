#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人消息发送工具（支持多机器人）
用于向指定会话发送文本消息和富文本消息
"""

import os
import json
import sys
from typing import Optional, Dict, List
from pathlib import Path
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class FeishuBot:
    """飞书机器人客户端"""

    def __init__(self, app_id: str, app_secret: str, chat_id: str, name: str = "default"):
        """
        初始化飞书机器人

        Args:
            app_id: 飞书应用的 App ID
            app_secret: 飞书应用的 App Secret
            chat_id: 会话 ID
            name: 机器人名称（用于多机器人管理）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.chat_id = chat_id
        self.name = name
        self.tenant_access_token: Optional[str] = None
        self.base_url = "https://open.feishu.cn/open-apis"

    def get_tenant_access_token(self) -> str:
        """
        获取 tenant_access_token

        Returns:
            tenant_access_token
        """
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, json=payload, headers=headers)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"获取 token 失败: {result.get('msg')}")

        self.tenant_access_token = result.get("tenant_access_token")
        return self.tenant_access_token

    def send_text_message(self, text: str, chat_id: Optional[str] = None) -> dict:
        """
        发送文本消息到指定会话

        Args:
            text: 消息文本内容
            chat_id: 会话 ID（可选，默认使用初始化时的 chat_id）

        Returns:
            API 响应结果
        """
        if not self.tenant_access_token:
            self.get_tenant_access_token()

        target_chat_id = chat_id or self.chat_id

        url = f"{self.base_url}/im/v1/messages?receive_id_type=chat_id"
        payload = {
            "receive_id": target_chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text})
        }
        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"发送消息失败: {result.get('msg')}")

        return result

    def send_post_message(self, title: str, content: List[List[Dict]], chat_id: Optional[str] = None) -> dict:
        """
        发送富文本消息（Post 类型）到指定会话

        Args:
            title: 消息标题
            content: 富文本内容，格式为 [[{tag, text, style}], ...]
                   每个子数组是一个段落，段落中可以有多个元素
            chat_id: 会话 ID（可选，默认使用初始化时的 chat_id）

        Returns:
            API 响应结果

        示例:
            content = [
                [
                    {"tag": "text", "text": "标题", "style": ["bold"]},
                    {"tag": "text", "text": "\n"}
                ],
                [
                    {"tag": "text", "text": "普通文本"}
                ]
            ]
        """
        if not self.tenant_access_token:
            self.get_tenant_access_token()

        target_chat_id = chat_id or self.chat_id

        url = f"{self.base_url}/im/v1/messages?receive_id_type=chat_id"
        
        # 构建富文本消息体
        post_content = {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content
                }
            }
        }

        payload = {
            "receive_id": target_chat_id,
            "msg_type": "post",
            "content": json.dumps(post_content)
        }
        
        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"发送富文本消息失败: {result.get('msg')}")

        return result


    def send_interactive_card(self, markdown_content: str, chat_id: Optional[str] = None, title: str = "📊 消息通知") -> dict:
        """
        发送 Interactive Card 消息（支持完整 Markdown）
        
        Args:
            markdown_content: Markdown 格式的内容
            chat_id: 会话 ID（可选）
            title: 卡片标题
            
        Returns:
            API 响应结果
        """
        if not self.tenant_access_token:
            self.get_tenant_access_token()

        target_chat_id = chat_id or self.chat_id

        url = f"{self.base_url}/im/v1/messages?receive_id_type=chat_id"

        # 构建 Interactive Card (Schema 2.0)
        card = {
            "schema": "2.0",
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
            },
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": markdown_content
                    }
                ]
            }
        }

        payload = {
            "receive_id": target_chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card)
        }

        headers = {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        result = response.json()

        if result.get("code") != 0:
            raise Exception(f"发送 Interactive Card 失败: {result.get('msg')}")

        return result

    def __repr__(self):
        return f"FeishuBot(name='{self.name}', app_id='{self.app_id}')"


class FeishuBotManager:
    """飞书机器人管理器（支持多机器人）"""

    def __init__(self):
        """初始化机器人管理器"""
        self.bots: Dict[str, FeishuBot] = {}
        self._load_bots_from_env()

    def _load_bots_from_env(self):
        """从环境变量加载机器人配置"""
        # 从环境变量加载所有配置的机器人
        index = 1
        while True:
            bot_name = os.getenv(f"BOT_{index}_NAME")
            app_id = os.getenv(f"BOT_{index}_APP_ID")
            app_secret = os.getenv(f"BOT_{index}_APP_SECRET")
            chat_id = os.getenv(f"BOT_{index}_CHAT_ID")

            if not all([bot_name, app_id, app_secret, chat_id]):
                break

            self.add_bot(bot_name, app_id, app_secret, chat_id)
            index += 1

    def add_bot(self, name: str, app_id: str, app_secret: str, chat_id: str):
        """
        添加机器人

        Args:
            name: 机器人名称
            app_id: 飞书应用的 App ID
            app_secret: 飞书应用的 App Secret
            chat_id: 会话 ID
        """
        bot = FeishuBot(app_id, app_secret, chat_id, name)
        self.bots[name] = bot

    def get_bot(self, name: str) -> Optional[FeishuBot]:
        """
        获取指定名称的机器人

        Args:
            name: 机器人名称

        Returns:
            FeishuBot 实例，如果不存在返回 None
        """
        return self.bots.get(name)

    def get_default_bot(self) -> Optional[FeishuBot]:
        """
        获取默认机器人

        Returns:
            默认的 FeishuBot 实例
        """
        default_bot_name = os.getenv("DEFAULT_BOT", "default")
        return self.get_bot(default_bot_name)

    def send_to_all(self, text: str):
        """
        向所有机器人发送消息

        Args:
            text: 消息文本内容
        """
        results = []
        for bot in self.bots.values():
            try:
                result = bot.send_text_message(text)
                results.append({"bot": bot.name, "status": "success", "result": result})
            except Exception as e:
                results.append({"bot": bot.name, "status": "failed", "error": str(e)})
        return results

    def send_to_bots(self, bot_names: List[str], text: str):
        """
        向指定机器人发送消息

        Args:
            bot_names: 机器人名称列表
            text: 消息文本内容
        """
        results = []
        for name in bot_names:
            bot = self.get_bot(name)
            if bot:
                try:
                    result = bot.send_text_message(text)
                    results.append({"bot": name, "status": "success", "result": result})
                except Exception as e:
                    results.append({"bot": name, "status": "failed", "error": str(e)})
            else:
                results.append({"bot": name, "status": "failed", "error": "Bot not found"})
        return results

    def list_bots(self):
        """列出所有已配置的机器人"""
        return list(self.bots.keys())

    def __repr__(self):
        return f"FeishuBotManager(bots={list(self.bots.keys())})"


# 全局单例
_manager = None


def get_manager() -> FeishuBotManager:
    """获取机器人管理器单例"""
    global _manager
    if _manager is None:
        _manager = FeishuBotManager()
    return _manager


def main():
    """主函数：命令行调用示例"""

    # 获取管理器
    manager = get_manager()

    # 检查是否配置了机器人
    if not manager.list_bots():
        print("❌ 错误：未配置任何机器人")
        print("请在 .env 文件中配置机器人信息")
        print("参考 .env.example 文件")
        sys.exit(1)

    # 解析命令行参数
    if len(sys.argv) < 2:
        print("用法:")
        print("  # 发送消息到默认机器人")
        print("  python feishu_bot.py \"消息内容\"")
        print()
        print("  # 发送消息到指定机器人")
        print("  python feishu_bot.py --bot <机器人名称> \"消息内容\"")
        print()
        print("  # 发送消息到多个机器人")
        print("  python feishu_bot.py --bots <机器人1,机器人2> \"消息内容\"")
        print()
        print("  # 发送消息到所有机器人")
        print("  python feishu_bot.py --all \"消息内容\"")
        print()
        print("  # 列出所有已配置的机器人")
        print("  python feishu_bot.py --list")
        sys.exit(1)

    # 列出所有机器人
    if "--list" in sys.argv:
        print("已配置的机器人:")
        for name in manager.list_bots():
            bot = manager.get_bot(name)
            print(f"  - {name}: {bot}")
        sys.exit(0)

    # 解析参数
    bot_name = None
    bot_names = None
    send_to_all_flag = False

    if "--bot" in sys.argv:
        idx = sys.argv.index("--bot")
        if idx + 1 < len(sys.argv):
            bot_name = sys.argv[idx + 1]
            sys.argv.pop(idx)
            sys.argv.pop(idx)

    if "--bots" in sys.argv:
        idx = sys.argv.index("--bots")
        if idx + 1 < len(sys.argv):
            bot_names = sys.argv[idx + 1].split(",")
            sys.argv.pop(idx)
            sys.argv.pop(idx)

    if "--all" in sys.argv:
        send_to_all_flag = True
        sys.argv.remove("--all")

    # 获取消息内容
    message = " ".join(sys.argv[1:])

    if not message:
        print("❌ 错误：消息内容不能为空")
        sys.exit(1)

    try:
        # 发送到所有机器人
        if send_to_all_flag:
            print(f"📤 发送消息到所有机器人...")
            results = manager.send_to_all(message)
            for result in results:
                if result["status"] == "success":
                    print(f"  ✅ {result['bot']}: 发送成功")
                else:
                    print(f"  ❌ {result['bot']}: {result.get('error', '发送失败')}")

        # 发送到指定机器人列表
        elif bot_names:
            print(f"📤 发送消息到机器人: {', '.join(bot_names)}")
            results = manager.send_to_bots(bot_names, message)
            for result in results:
                if result["status"] == "success":
                    print(f"  ✅ {result['bot']}: 发送成功")
                else:
                    print(f"  ❌ {result['bot']}: {result.get('error', '发送失败')}")

        # 发送到指定机器人
        elif bot_name:
            bot = manager.get_bot(bot_name)
            if not bot:
                print(f"❌ 错误：未找到机器人 '{bot_name}'")
                sys.exit(1)
            print(f"📤 发送消息到机器人: {bot_name}")
            result = bot.send_text_message(message)
            print(f"  ✅ 发送成功！消息 ID: {result.get('data', {}).get('message_id')}")

        # 发送到默认机器人
        else:
            bot = manager.get_default_bot()
            if not bot:
                print("❌ 错误：未配置默认机器人")
                sys.exit(1)
            print(f"📤 发送消息到默认机器人: {bot.name}")
            result = bot.send_text_message(message)
            print(f"  ✅ 发送成功！消息 ID: {result.get('data', {}).get('message_id')}")

    except Exception as e:
        print(f"❌ 发送失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
