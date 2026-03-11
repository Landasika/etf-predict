#!/usr/bin/env python3
"""
快速添加模拟持仓数据并发送测试报告
用于远程服务器快速测试飞书报告功能
"""
import sys
import sqlite3
import random
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import DATABASE_PATH
from core.watchlist import load_watchlist
from core.feishu_notifier import get_feishu_notifier
from core.feishu_report import generate_etf_operation_report


def add_mock_positions():
    """添加模拟持仓数据"""
    print("=" * 60)
    print("📊 添加模拟持仓数据")
    print("=" * 60)
    print()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 加载自选列表
    watchlist = load_watchlist()
    etfs = watchlist.get('etfs', []) if watchlist else []

    if not etfs:
        print("❌ 无法加载自选列表")
        return False

    # 清除现有的持仓信息
    print("清除现有持仓信息...")
    cursor.execute("""
        UPDATE etf_basic
        SET extname = REPLACE(
            REPLACE(extname, ' [' || substr(extname, instr(extname, '[') + 1, instr(extname, '仓]') - instr(extname, '[') - 1) || '仓]', ''),
            '  ', ' '
        )
        WHERE extname LIKE '%[%仓]'
    """)
    conn.commit()

    # 随机选择10-15个ETF添加持仓
    selected_count = random.randint(10, min(15, len(etfs)))
    selected = random.sample(etfs, selected_count)

    total_positions = 0
    for etf in selected:
        code = etf['code']
        name = etf.get('name', '')

        # 随机持仓3-10仓
        positions = random.randint(3, 10)
        total_positions += positions

        # 随机涨跌幅
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

            # 更新涨跌幅
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

            # 在extname字段添加持仓信息
            cursor.execute("""
                UPDATE etf_basic
                SET extname = ? || ' [' || ? || '仓]'
                WHERE ts_code = ?
            """, (name, positions, code))

            print(f"  ✅ {code} {name[:15]:15s}: {positions}仓, {pct_chg:+.2f}% (¥{close:.3f})")

    conn.commit()
    conn.close()

    print()
    print(f"✓ 已为 {selected_count} 个ETF添加模拟持仓")
    print(f"  总仓位: {total_positions}仓")
    print(f"  总资金: ¥{total_positions * 200:,}")
    print()

    return True


async def send_test_report():
    """发送测试报告"""
    print("=" * 60)
    print("📤 发送ETF操作建议报告")
    print("=" * 60)
    print()

    # 获取飞书通知器
    notifier = get_feishu_notifier()

    if not notifier.is_enabled():
        print("❌ 飞书通知未启用，请先在设置页面配置飞书")
        return False

    print("✓ 飞书通知已启用")
    print()

    # 生成报告
    print("📊 正在生成ETF操作建议报告...")
    markdown_content = generate_etf_operation_report()

    if not markdown_content:
        print("❌ 生成报告失败或无数据")
        return False

    print("✓ 报告生成成功")
    print()

    # 显示关键统计
    lines = markdown_content.split('\n')
    print("📄 报告关键信息:")
    print("-" * 60)
    for line in lines:
        if any(keyword in line for keyword in ['有持仓ETF', '昨日总仓位', '昨日总资金', '今日总收益',
                                                '操作类型', '卖出', '买入', '持有']):
            print(line)
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


def clear_mock_positions():
    """清除模拟持仓数据"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 清除extname中的持仓信息
    cursor.execute("""
        UPDATE etf_basic
        SET extname = REPLACE(extname, ' [' || substr(extname, instr(extname, '[') + 1, instr(extname, '仓]') - instr(extname, '[') - 1) || '仓]', '')
        WHERE extname LIKE '%[%仓]'
    """)

    conn.commit()
    conn.close()


async def main():
    print()
    print("⚠️  这将:")
    print("  1. 为部分ETF添加模拟的持仓和涨跌数据")
    print("  2. 生成并发送ETF操作建议报告到飞书")
    print("  3. 数据保留（不会自动清除，可重复运行）")
    print()

    try:
        # 添加模拟数据
        if not add_mock_positions():
            return

        # 发送测试报告
        success = await send_test_report()

        print()
        print("=" * 60)
        if success:
            print("✅ 测试完成")
            print("💡 提示: 模拟持仓数据已保留，可重复运行测试")
            print("   如需清除数据，请运行: python3 scripts/clear_mock_positions.py")
        else:
            print("❌ 测试失败")
        print("=" * 60)
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
