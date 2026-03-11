#!/usr/bin/env python3
"""
测试ETF操作建议报告发送
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.feishu_notifier import get_feishu_notifier
from core.feishu_report import generate_etf_operation_report

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

    print("📄 报告内容预览：")
    print("-" * 60)
    lines = markdown_content.split('\n')
    for i, line in enumerate(lines[:30]):  # 显示前30行
        print(line)
    if len(lines) > 30:
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
    print("⚠️  这将立即发送ETF操作建议报告到飞书")
    print()

    result = asyncio.run(send_test_report())

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
