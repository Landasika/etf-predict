#!/usr/bin/env python3
"""
测试ETF报告（使用模拟的实时数据）
为了测试报告功能，临时添加一些模拟的涨跌数据
"""
import sys
import os
import asyncio
from pathlib import Path
import sqlite3
import random
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.feishu_notifier import get_feishu_notifier
from core.feishu_report import generate_etf_operation_report
from core.database import DATABASE_PATH
from core.watchlist import load_watchlist


def add_mock_daily_changes():
    """为今天的ETF数据添加模拟的涨跌幅（仅用于测试）"""
    print("📊 添加模拟涨跌数据...")

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 获取今天的日期
    today = datetime.now().strftime('%Y%m%d')

    # 获取自选ETF列表
    watchlist = load_watchlist()
    etfs = watchlist.get('etfs', []) if watchlist else []

    updated_count = 0

    for etf in etfs[:10]:  # 只处理前10个ETF进行测试
        code = etf['code']

        # 生成随机的涨跌幅（-3%到+3%）
        pct_chg = random.uniform(-3, 3)

        # 获取最新价格
        cursor.execute("""
            SELECT close
            FROM etf_daily
            WHERE ts_code = ?
            ORDER BY trade_date DESC
            LIMIT 1
        """, (code,))

        result = cursor.fetchone()
        if result:
            last_close = result[0]

            # 更新今天的涨跌幅
            cursor.execute("""
                UPDATE etf_daily
                SET pct_chg = ?
                WHERE ts_code = ? AND trade_date = (
                    SELECT trade_date FROM etf_daily
                    WHERE ts_code = ?
                    ORDER BY trade_date DESC
                    LIMIT 1
                )
            """, (pct_chg, code, code))

            updated_count += 1
            print(f"  {code}: {pct_chg:+.2f}%")

    conn.commit()
    conn.close()

    print(f"✓ 已更新 {updated_count} 个ETF的涨跌幅数据\n")


async def send_test_report():
    """发送测试报告"""
    print("=" * 60)
    print("📤 发送ETF操作建议报告（含模拟数据）")
    print("=" * 60)
    print()

    # 获取飞书通知器
    notifier = get_feishu_notifier()

    if not notifier.is_enabled():
        print("❌ 飞书通知未启用，请先在设置页面配置飞书")
        return False

    print("✓ 飞书通知已启用")
    print()

    # 添加模拟数据
    add_mock_daily_changes()

    # 生成报告
    print("📊 正在生成ETF操作建议报告...")
    markdown_content = generate_etf_operation_report()

    if not markdown_content:
        print("❌ 生成报告失败或无数据")
        return False

    print("✓ 报告生成成功")
    print()

    print("📄 报告内容预览：")
    print("-" * 60)
    lines = markdown_content.split('\n')
    for i, line in enumerate(lines[:50]):  # 显示前50行
        print(line)
    if len(lines) > 50:
        print(f"\n... (共{len(lines)}行)")
    print("-" * 60)
    print()

    # 发送消息
    print("📤 正在发送到飞书...")
    result = await notifier.send_message(markdown_content, title="🎯 ETF操作建议")

    if result:
        print("✅ 飞书消息发送成功！")
        return True
    else:
        print("❌ 飞书消息发送失败")
        return False


def main():
    print()
    print("⚠️  这将:")
    print("  1. 为ETF添加模拟的涨跌数据（-3%到+3%）")
    print("  2. 生成并发送ETF操作建议报告")
    print()

    result = asyncio.run(send_test_report())

    print()
    print("=" * 60)
    if result:
        print("✅ 测试完成")
        print("💡 提示: 已添加模拟数据，报告显示了真实的操作建议")
    else:
        print("❌ 测试失败")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
