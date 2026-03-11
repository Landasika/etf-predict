#!/usr/bin/env python3
"""
测试飞书消息发送（使用Markdown表格格式）
立即发送ETF交易建议到飞书
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.feishu_notifier import get_feishu_notifier
from core.database import get_etf_connection
from core.watchlist import load_watchlist
from datetime import datetime

async def send_test_message():
    """发送测试消息（使用Markdown表格格式）"""
    print("=" * 60)
    print("📤 发送飞书测试消息（Markdown表格格式）")
    print("=" * 60)
    print()

    # 获取飞书通知器
    notifier = get_feishu_notifier()

    if not notifier.is_enabled():
        print("❌ 飞书通知未启用，请先在设置页面配置飞书")
        return False

    print("✓ 飞书通知已启用")
    print()

    # 获取自选列表
    watchlist_data = load_watchlist()
    if not watchlist_data or not watchlist_data.get('etfs'):
        print("❌ 自选列表为空")
        return False

    etfs = watchlist_data.get('etfs', [])
    print(f"✓ 自选列表: {len(etfs)} 个ETF")
    print()

    # 获取数据并构建Markdown表格
    try:
        conn = get_etf_connection()
        if not conn:
            print("❌ 无法连接数据库")
            return False

        etf_codes = [etf['code'] for etf in etfs[:15]]  # 最多显示15个

        # 构建Markdown表格
        markdown_lines = [
            "⏰ **时间**: " + datetime.now().strftime('%Y-%m-%d %H:%M') + "\n\n",
            "| ETF名称 | 代码 | 价格 | 涨跌幅 |",
            "| --- | --- | --- | --- |"
        ]

        # 数据行
        for etf_code in etf_codes:
            try:
                # 获取最新数据
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.close, d.pct_chg, b.extname
                    FROM etf_daily d
                    LEFT JOIN etf_basic b ON d.ts_code = b.ts_code
                    WHERE d.ts_code = ?
                    ORDER BY d.trade_date DESC
                    LIMIT 1
                """, (etf_code,))
                result = cursor.fetchone()

                if result:
                    close, pct_chg, name = result
                    if close is not None:
                        # 处理 None 值
                        if pct_chg is None:
                            change_str = "N/A"
                        else:
                            change_str = f"+{pct_chg:.2f}%"

                        # 根据涨跌添加emoji
                        if pct_chg is None:
                            emoji = "⚪"
                        elif pct_chg > 0:
                            emoji = "🟢"
                        elif pct_chg < 0:
                            emoji = "🔴"
                        else:
                            emoji = "⚪"

                        markdown_lines.append(
                            f"| {emoji} {name or etf_code} | `{etf_code}` | `{close:.3f}` | `{change_str}` |"
                        )
            except Exception as e:
                print(f"❌ 获取 {etf_code} 数据失败: {e}")

        conn.close()

        markdown_lines.append("\n---\n💡 这是一条测试消息 - 详细信息请访问系统查看")
        markdown_content = "\n".join(markdown_lines)

        print("📨 消息内容（Markdown表格）：")
        print("-" * 60)
        for i, line in enumerate(markdown_lines[:10]):  # 只显示前10行
            print(line)
        if len(markdown_lines) > 10:
            print(f"... (共{len(markdown_lines)}行)")
        print("-" * 60)
        print()

        # 发送消息
        print("📤 正在发送到飞书...")
        result = await notifier.send_message(markdown_content, title="📊 ETF交易建议（测试）")

        if result:
            print("✅ 飞书消息发送成功！")
            return True
        else:
            print("❌ 飞书消息发送失败")
            return False

    except Exception as e:
        print(f"❌ 发送失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print()
    print("⚠️  这将立即发送一条测试消息到飞书（Markdown表格格式）")
    print()

    result = asyncio.run(send_test_message())

    print()
    print("=" * 60)
    if result:
        print("✅ 测试完成")
    else:
        print("❌ 测试失败")
    print("=" * 60)
    print()

if __name__ == "__main__":
    main()
