#!/usr/bin/env python3
"""
测试ETF报告（使用模拟的持仓和涨跌数据）
为了测试报告功能，添加模拟的持仓数据和涨跌幅数据
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


def add_mock_data_for_testing():
    """为测试添加模拟的持仓数据和涨跌幅数据"""
    print("📊 添加模拟数据...")
    print()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 获取今天的日期
    today = datetime.now().strftime('%Y%m%d')

    # 获取自选ETF列表
    watchlist = load_watchlist()
    etfs = watchlist.get('etfs', []) if watchlist else []

    # 模拟：只对部分ETF添加持仓（模拟真实情况）
    # 随机选择10-12个ETF有持仓
    selected_etfs = random.sample(etfs, k=min(12, len(etfs)))

    total_positions = 0
    updated_count = 0

    for etf in selected_etfs:
        code = etf['code']

        # 随机持仓3-10仓
        positions = random.randint(3, 10)
        total_positions += positions

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
            close = result[0]

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

            # 在extname字段存储持仓信息（临时方案）
            # 用于报告生成时读取
            cursor.execute("""
                UPDATE etf_basic
                SET extname = extname || ' [' || ? || '仓]'
                WHERE ts_code = ?
            """, (positions, code))

            updated_count += 1
            print(f"  {code}: {positions}仓, {pct_chg:+.2f}% (价格: ¥{close:.3f})")

    conn.commit()
    conn.close()

    print()
    print(f"✓ 已更新 {updated_count} 个ETF的持仓和涨跌幅数据")
    print(f"  总仓位: {total_positions}仓")
    print(f"  总资金: ¥{total_positions * 200:,}")
    print()


def clear_mock_positions():
    """清除模拟持仓数据"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 清除extname中的持仓信息
    cursor.execute("""
        UPDATE etf_basic
        SET extname = REPLACE(extname, ' [仓]', '')
        WHERE extname LIKE '%[%仓]'
    """)

    conn.commit()
    conn.close()

    print("✓ 已清除模拟持仓数据")


async def send_test_report():
    """发送测试报告"""
    print("=" * 60)
    print("📤 发送ETF操作建议报告（含模拟持仓和涨跌数据）")
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
    add_mock_data_for_testing()

    # 生成报告
    print("📊 正在生成ETF操作建议报告...")
    markdown_content = generate_etf_operation_report()

    if not markdown_content:
        print("❌ 生成报告失败或无数据")
        return False

    print("✓ 报告生成成功")
    print()

    # 只显示关键部分
    lines = markdown_content.split('\n')
    print("📄 报告内容预览：")
    print("-" * 60)
    for i, line in enumerate(lines):
        if i < 60 or i > len(lines) - 10:  # 显示开头和结尾
            print(line)
        elif line.startswith("## "):
            print(line)
        elif line.startswith("| ") and "操作类型" in lines[i-1] if i > 0 else False:
            print(line)
        elif line.startswith("| ") and ("ETF名称" in lines[i-2] if i > 1 else False):
            print(line)
        elif line.startswith("---"):
            print(line)
    print("-" * 60)
    print()

    # 发送消息
    print("📤 正在发送到飞书...")
    result = await notifier.send_message(markdown_content, title="🎯 ETF操作建议")

    # 清理模拟数据
    try:
        clear_mock_positions()
    except:
        pass

    if result:
        print("✅ 飞书消息发送成功！")
        return True
    else:
        print("❌ 飞书消息发送失败")
        return False


def main():
    print()
    print("⚠️  这将:")
    print("  1. 为部分ETF添加模拟的持仓和涨跌数据")
    print("  2. 生成并发送ETF操作建议报告")
    print("  3. 发送完成后清除模拟数据")
    print()

    result = asyncio.run(send_test_report())

    print()
    print("=" * 60)
    if result:
        print("✅ 测试完成")
        print("💡 提示: 已添加模拟持仓数据，报告显示了真实的持仓统计")
    else:
        print("❌ 测试失败")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
