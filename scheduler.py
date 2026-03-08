#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 预测系统定时任务调度器
在每个交易日的特定时间点执行任务并推送飞书消息
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import requests
import schedule

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import config
from feishu_bot import FeishuBot, get_manager


DEFAULT_SCHEDULE_TIMES = ["09:40", "10:40", "11:40", "13:40", "14:40"]

# API 配置
API_HOST = config.API_HOST
if API_HOST == "0.0.0.0":
    API_HOST = "127.0.0.1"


def parse_bool(value: Optional[str], default: bool) -> bool:
    """解析布尔值环境变量"""
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    return default


def parse_schedule_times(raw_times: str) -> List[str]:
    """解析并校验定时任务时间列表"""
    times = [item.strip() for item in raw_times.split(",") if item.strip()]
    if not times:
        raise ValueError("定时任务时间不能为空")

    validated_times: List[str] = []
    for time_str in times:
        try:
            datetime.strptime(time_str, "%H:%M")
        except ValueError as exc:
            raise ValueError(f"无效时间格式: {time_str}，应为 HH:MM") from exc
        validated_times.append(time_str)

    return validated_times


def resolve_feishu_bot(
    app_id: Optional[str],
    app_secret: Optional[str],
    chat_id: Optional[str],
    bot_name: Optional[str],
) -> FeishuBot:
    """解析并返回用于发送消息的飞书机器人"""
    # 若手动传入了任意一项飞书参数，则要求三项齐全，并优先使用这组三元组
    custom_values = {
        "app_id": app_id,
        "app_secret": app_secret,
        "chat_id": chat_id,
    }
    if any(custom_values.values()):
        missing_fields = [key for key, value in custom_values.items() if not value]
        if missing_fields:
            missing_text = ", ".join(missing_fields)
            raise ValueError(f"飞书配置缺失字段: {missing_text}")

        return FeishuBot(
            app_id=app_id,
            app_secret=app_secret,
            chat_id=chat_id,
            name=bot_name or "custom",
        )

    manager = get_manager()

    if bot_name:
        bot = manager.get_bot(bot_name)
        if bot is None:
            raise ValueError(f"未找到机器人: {bot_name}")
        return bot

    bot = manager.get_default_bot()
    if bot is None:
        raise ValueError(
            "未配置机器人，请在 .env 中配置 BOT_1_APP_ID/BOT_1_APP_SECRET/BOT_1_CHAT_ID，"
            "或配置 FEISHU_APP_ID/FEISHU_APP_SECRET/FEISHU_CHAT_ID"
        )
    return bot


def is_trading_day(date: datetime = None) -> bool:
    """
    判断是否是交易日

    Args:
        date: 日期对象，默认为今天

    Returns:
        True if 是交易日，False otherwise
    """
    if date is None:
        date = datetime.now()

    # 周末不是交易日
    if date.weekday() >= 5:  # 5=周六, 6=周日
        return False

    # TODO: 可以添加节假日判断
    # 这里简单处理，可以通过 API 获取交易日历
    return True


def send_feishu_notification(bot: FeishuBot) -> bool:
    """发送飞书通知"""
    try:
        # 导入推送报告模块
        from feishu_portfolio_report import fetch_watchlist_data, generate_trading_recommendations_card

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在获取操作建议...")

        # 获取数据
        api_data = fetch_watchlist_data()
        if not api_data:
            print("❌ 获取数据失败")
            return False

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在发送飞书通知... (bot={bot.name})")

        # 生成 Markdown 内容
        markdown_content = generate_trading_recommendations_card(api_data)

        # 发送到飞书
        bot.send_interactive_card(markdown_content)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 飞书通知发送成功！")
        return True

    except Exception as e:
        print(f"❌ 发送通知失败: {e}")
        return False


def job_send_notification(bot: FeishuBot, only_trading_day: bool = True):
    """定时任务：发送飞书通知"""
    print(f"\n{'='*60}")
    print(f"定时任务触发: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*60)

    # 判断是否是交易日
    if only_trading_day and not is_trading_day():
        print("⏰ 今天不是交易日，跳过任务执行")
        return

    # 执行发送
    send_feishu_notification(bot)


def run_scheduler(
    bot: FeishuBot,
    scheduled_times: List[str],
    run_on_startup: bool = True,
    poll_seconds: int = 60,
    only_trading_day: bool = True,
):
    """运行定时任务调度器"""
    print("="*60)
    print("📅 ETF 预测系统 - 定时任务调度器")
    print("="*60)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"机器人: {bot.name}")
    print(f"定时任务: {', '.join(scheduled_times)}")
    print(f"仅交易日执行: {'是' if only_trading_day else '否'}")
    print(f"启动后立即尝试执行一次: {'是' if run_on_startup else '否'}")
    print("")
    print("按 Ctrl+C 停止调度器")
    print("="*60)
    print("")

    # 检查服务是否可用
    try:
        response = requests.get(f"http://{API_HOST}:{config.API_PORT}/api/watchlist", timeout=5)
        if response.status_code != 200:
            print("❌ API 服务未运行，请先启动: python run.py")
            return
    except Exception:
        print("❌ 无法连接到 API 服务，请先启动: python run.py")
        return

    # 设置定时任务
    for time_str in scheduled_times:
        schedule.every().day.at(time_str).do(
            job_send_notification,
            bot=bot,
            only_trading_day=only_trading_day,
        )

    print("✅ 定时任务已设置")
    print("等待下次执行...")
    print("")

    # 启动时立即执行一次
    if run_on_startup:
        current_time = datetime.now().strftime("%H:%M")
        if "09:00" <= current_time < "15:00":
            if not only_trading_day or is_trading_day():
                print(f"[首次启动] 当前时间 {current_time}，正在执行一次任务...")
                send_feishu_notification(bot)
            else:
                print("[首次启动] 非交易日，跳过首次执行")

    # 循环运行
    try:
        while True:
            schedule.run_pending()
            time.sleep(max(1, poll_seconds))
    except KeyboardInterrupt:
        print("\n\n👋 定时任务调度器已停止")
    except Exception as e:
        print(f"\n❌ 调度器错误: {e}")


def build_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数"""
    parser = argparse.ArgumentParser(description="ETF 飞书定时发送任务")

    parser.add_argument(
        "--times",
        default=os.getenv("SCHEDULER_TIMES", ",".join(DEFAULT_SCHEDULE_TIMES)),
        help="定时任务时间，逗号分隔，格式 HH:MM，例如 09:40,10:40",
    )
    parser.add_argument(
        "--bot-name",
        default=os.getenv("SCHEDULER_BOT_NAME") or os.getenv("DEFAULT_BOT"),
        help="使用已配置机器人名称（对应 BOT_n_NAME）",
    )
    parser.add_argument(
        "--app-id",
        default=os.getenv("SCHEDULER_APP_ID") or os.getenv("FEISHU_APP_ID"),
        help="飞书 App ID（与 --app-secret/--chat-id 组合使用）",
    )
    parser.add_argument(
        "--app-secret",
        default=os.getenv("SCHEDULER_APP_SECRET") or os.getenv("FEISHU_APP_SECRET"),
        help="飞书 App Secret（与 --app-id/--chat-id 组合使用）",
    )
    parser.add_argument(
        "--chat-id",
        default=os.getenv("SCHEDULER_CHAT_ID") or os.getenv("FEISHU_CHAT_ID"),
        help="飞书会话 Chat ID（与 --app-id/--app-secret 组合使用）",
    )

    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=int(os.getenv("SCHEDULER_POLL_SECONDS", "60")),
        help="轮询间隔秒数（默认60）",
    )

    startup_default = parse_bool(os.getenv("SCHEDULER_RUN_ON_STARTUP"), True)
    parser.add_argument(
        "--run-on-startup",
        action="store_true",
        dest="run_on_startup",
        help="启动后在交易时段内立即执行一次",
    )
    parser.add_argument(
        "--no-run-on-startup",
        action="store_false",
        dest="run_on_startup",
        help="启动后不立即执行",
    )
    parser.set_defaults(run_on_startup=startup_default)

    parser.add_argument(
        "--ignore-trading-day",
        action="store_true",
        help="忽略交易日检查（周末也执行）",
    )

    return parser


def main() -> int:
    """主函数"""
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        scheduled_times = parse_schedule_times(args.times)
        bot = resolve_feishu_bot(
            app_id=args.app_id,
            app_secret=args.app_secret,
            chat_id=args.chat_id,
            bot_name=args.bot_name,
        )
    except ValueError as exc:
        print(f"❌ 参数错误: {exc}")
        return 1

    run_scheduler(
        bot=bot,
        scheduled_times=scheduled_times,
        run_on_startup=args.run_on_startup,
        poll_seconds=args.poll_seconds,
        only_trading_day=not args.ignore_trading_day,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
