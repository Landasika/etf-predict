#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人持仓报告和操作建议
通过 API 获取数据并发送到飞书（使用 Interactive Card）
"""

import requests
import sys
from datetime import datetime
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


def fetch_from_api(endpoint: str, params: dict = None) -> dict:
    """从 API 获取数据"""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ API 请求失败: {e}")
        return None


def fetch_watchlist_data() -> dict:
    """从 API 获取自选列表数据"""
    data = fetch_from_api("/api/watchlist/batch-signals", {"realtime": True})
    if not data or not data.get("success"):
        print("❌ 获取批量信号数据失败")
        return None
    return data


def generate_trading_recommendations_card(api_data: dict) -> str:
    """
    根据API数据生成操作建议的 Markdown 内容（用于 Interactive Card）
    
    Returns:
        Markdown 格式的文本
    """
    etfs = api_data.get("data", [])

    # 计算总体统计
    total_positions = 0  # 总持仓数
    total_position_value = 0  # 按持仓计算的总资金
    total_daily_profit = 0  # 今日总收益
    
    buy_recommendations = []
    sell_recommendations = []

    for etf in etfs:
        code = etf.get("code")
        name = etf.get("name")
        remark = etf.get("remark", "")
        current_price = etf.get("price", 0)
        daily_change_pct = etf.get("daily_change_pct", 0)
        current_positions = etf.get("positions_used", 0)
        total_positions_etf = etf.get("total_positions", 10)
        initial_capital = etf.get("initial_capital", 2000)
        today_operation = etf.get("today_operation", "观望")
        today_action_count = etf.get("today_action_count", 0)
        daily_profit = etf.get("daily_profit", 0)
        profit_value = etf.get("profit_value", 0)
        
        # 累计统计
        total_positions += current_positions
        total_position_value += current_positions * 200  # 按持仓计算资金：持仓数 × 200
        total_daily_profit += daily_profit
        
        if "买入" in today_operation:
            buy_recommendations.append({
                "code": code,
                "name": name,
                "remark": remark,
                "price": current_price,
                "daily_change": daily_change_pct,
                "daily_profit": daily_profit,
                "current_positions": current_positions,
                "action_positions": abs(today_action_count),
                "total_positions": total_positions_etf,
                "profit_value": profit_value
            })
        elif "卖出" in today_operation:
            sell_recommendations.append({
                "code": code,
                "name": name,
                "remark": remark,
                "price": current_price,
                "daily_change": daily_change_pct,
                "daily_profit": daily_profit,
                "current_positions": current_positions,
                "action_positions": abs(today_action_count),
                "total_positions": total_positions_etf,
                "profit_value": profit_value
            })

    # 构建 Markdown 内容（Card 支持完整 Markdown）
    markdown_lines = []
    
    # 标题
    markdown_lines.append("## 🎯 ETF 操作建议")
    markdown_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    markdown_lines.append("")
    
    # 添加整体统计
    markdown_lines.append("### 📊 持仓统计")
    markdown_lines.append("")
    markdown_lines.append("| 项目 | 数值 |")
    markdown_lines.append("|:------|:------|")
    markdown_lines.append("| 昨日总仓位 | **{}仓** |".format(total_positions))
    markdown_lines.append("| 昨日总资金 | **¥{:,}** |".format(total_position_value))  # 修复：按持仓计算
    markdown_lines.append("| 今日总收益 | **¥{:+,.2f}** |".format(total_daily_profit))
    markdown_lines.append("")
    
    # 买入建议
    if buy_recommendations:
        markdown_lines.append("### 🟢 建议买入 ({})".format(len(buy_recommendations)))
        markdown_lines.append("")
        # 列顺序：ETF名称、操作、基金名称、代码、涨跌、价格、今日收益、仓位
        markdown_lines.append("| ETF名称 | 操作 | 基金名称 | 代码 | �涨跌 | 价格 | 今日收益 | 仓位 |")
        markdown_lines.append("|:--------|:------|:--------|:------|:------|:------|:------|:------|")
        
        for item in buy_recommendations:
            etf_name = item['name']
            fund_name = item['remark'] if item['remark'] else '-'
            markdown_lines.append("| {} | **买入{}份** | {} | {} | {:+.2f}% | {:.3f} | {:+.2f} | {}/{} |".format(
                etf_name, item['action_positions'], fund_name, item['code'], 
                item['daily_change'], item['price'], item['daily_profit'],
                item['current_positions'], item['total_positions']
            ))
        
        markdown_lines.append("")
    
    # 卖出建议
    if sell_recommendations:
        markdown_lines.append("### 🔴 建议卖出 ({})".format(len(sell_recommendations)))
        markdown_lines.append("")
        # 列顺序：ETF名称、操作、基金名称、代码、涨跌、价格、今日收益、仓位
        markdown_lines.append("| ETF名称 | 操作 | 基金名称 | 代码 | 涨跌 | 价格 | 今日收益 | 仓位 |")
        markdown_lines.append("|:--------|:------|:--------|:------|:------|:------|:------|:------|")
        
        for item in sell_recommendations:
            etf_name = item['name']
            fund_name = item['remark'] if item['remark'] else '-'
            markdown_lines.append("| {} | **卖出{}份** | {} | {} | {:+.2f}% | {:.3f} | {:+.2f} | {}/{} |".format(
                etf_name, item['action_positions'], fund_name, item['code'], 
                item['daily_change'], item['price'], item['daily_profit'],
                item['current_positions'], item['total_positions']
            ))
        
        markdown_lines.append("")
    
    if not buy_recommendations and not sell_recommendations:
        markdown_lines.append("> 当前无买卖操作建议，全部保持观望")
    
    return "\n".join(markdown_lines)


def send_trading_recommendations():
    """发送操作建议到飞书（Interactive Card 格式）"""
    manager = get_manager()
    bot = manager.get_default_bot()

    if not bot:
        print("❌ 未配置默认机器人")
        return

    print("🎯 正在从 API 获取操作建议...")
    api_data = fetch_watchlist_data()

    if not api_data:
        print("❌ 获取数据失败")
        return

    print("📝 正在生成操作建议（Interactive Card 格式）...")
    markdown_content = generate_trading_recommendations_card(api_data)

    print("📤 正在发送建议到飞书...")
    
    # 使用 Interactive Card 发送
    try:
        bot.send_interactive_card(markdown_content)
        print("✅ 操作建议发送成功！")
    except AttributeError:
        print("❌ feishu_bot.py 暂不支持 Interactive Card")
        print("请使用文本消息方式")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python feishu_portfolio_report.py recommendation # 发送操作建议")
        print()
        print("注意: 请确保 API 服务已启动 (python run.py)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "recommendation":
        send_trading_recommendations()
    else:
        print("❌ 未知命令: {}".format(command))
        print("当前只支持 recommendation 命令")
        sys.exit(1)


if __name__ == "__main__":
    main()
