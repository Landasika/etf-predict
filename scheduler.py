#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 预测系统定时任务调度器
在每个交易日的特定时间点执行任务并推送飞书消息
"""

import os
import sys
import time
import schedule
import requests
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from feishu_bot import get_manager
import config


# API 配置
API_HOST = config.API_HOST
if API_HOST == "0.0.0.0":
    API_HOST = "127.0.0.1"
API_BASE_URL = f"http://{API_HOST}:{config.API_PORT}"


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


def send_feishu_notification():
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

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在发送飞书通知...")

        # 生成 Markdown 内容
        markdown_content = generate_trading_recommendations_card(api_data)

        # 发送到飞书
        manager = get_manager()
        bot = manager.get_default_bot()

        if bot:
            bot.send_interactive_card(markdown_content)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 飞书通知发送成功！")
            return True
        else:
            print("❌ 未配置机器人")
            return False

    except Exception as e:
        print(f"❌ 发送通知失败: {e}")
        return False


def job_send_notification():
    """定时任务：发送飞书通知"""
    print(f"\n{'='*60}")
    print(f"定时任务触发: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*60)

    # 判断是否是交易日
    if not is_trading_day():
        print("⏰ 今天不是交易日，跳过任务执行")
        return

    # 执行发送
    send_feishu_notification()


def run_scheduler():
    """运行定时任务调度器"""
    print("="*60)
    print("📅 ETF 预测系统 - 定时任务调度器")
    print("="*60)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("定时任务:")
    print("  - 每个 09:40, 10:40, 11:40, 13:40, 14:40 发送操作建议")
    print("  - 仅在交易日执行")
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
    except:
        print("❌ 无法连接到 API 服务，请先启动: python run.py")
        return

    # 设置定时任务
    # 上午：9:40, 10:40, 11:40
    schedule.every().day.at("09:40").do(job_send_notification)
    schedule.every().day.at("10:40").do(job_send_notification)
    schedule.every().day.at("11:40").do(job_send_notification)

    # 下午：13:40, 14:40
    schedule.every().day.at("13:40").do(job_send_notification)
    schedule.every().day.at("14:40").do(job_send_notification)

    print("✅ 定时任务已设置")
    print("等待下次执行...")
    print("")

    # 启动时立即执行一次
    current_time = datetime.now().strftime("%H:%M")
    scheduled_times = ["09:40", "10:40", "11:40", "13:40", "14:40"]

    if current_time >= "09:00" and current_time < "15:00":
        if is_trading_day():
            print(f"[首次启动] 当前时间 {current_time}，正在执行一次任务...")
            send_feishu_notification()

    # 循环运行
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        print("\n\n👋 定时任务调度器已停止")
    except Exception as e:
        print(f"\n❌ 调度器错误: {e}")


def main():
    """主函数"""
    run_scheduler()


if __name__ == "__main__":
    main()
