#!/usr/bin/env python3
"""
测试报告生成器是否正确使用API数据
"""
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_api_data():
    """测试API返回的数据"""
    print("=" * 60)
    print("1️⃣  测试API数据")
    print("=" * 60)
    print()

    api_urls = [
        "http://127.0.0.1:8000/api/watchlist/batch-signals",
        "http://127.0.0.1:8001/api/watchlist/batch-signals"
    ]

    api_data = None
    working_url = None

    for url in api_urls:
        try:
            print(f"尝试: {url}")
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    items = data.get('data', [])
                    print(f"✅ 成功! 返回 {len(items)} 个ETF")
                    working_url = url
                    api_data = data
                    break
        except:
            print(f"❌ 失败")
            continue

    if not api_data:
        print()
        print("❌ 所有API连接失败")
        print("   请确保API服务器正在运行: python run.py")
        return None

    print()

    # 分析持仓数据
    items = api_data.get('data', [])
    has_positions = False
    total_positions = 0
    active_count = 0

    print("前10个ETF的持仓数据:")
    print("-" * 60)

    for item in items[:10]:
        code = item.get('code')
        name = item.get('name', '')
        latest_data = item.get('latest_data', {})
        prev_positions = latest_data.get('previous_positions_used', 0)
        daily_profit = item.get('daily_profit', 0)

        if prev_positions > 0:
            has_positions = True
            active_count += 1
            total_positions += prev_positions
            status = f"✅ {prev_positions}仓"
        else:
            status = "❌ 0仓"

        print(f"  {code} {name[:15]:15s}: previous_positions_used={prev_positions}, daily_profit=¥{daily_profit:.2f} {status}")

    print()
    print("-" * 60)
    print(f"统计（前10个）:")
    print(f"  有持仓ETF: {active_count}个")
    print(f"  总仓位: {total_positions}仓")
    print()

    if not has_positions:
        print("⚠️  API返回的所有ETF持仓都是0")
        print("   需要运行回测来生成持仓数据")
        return None

    return api_data


def test_report_generation():
    """测试报告生成"""
    print("=" * 60)
    print("2️⃣  测试报告生成")
    print("=" * 60)
    print()

    try:
        from core.feishu_report import generate_etf_operation_report

        print("正在生成报告...")
        markdown_content = generate_etf_operation_report()

        if not markdown_content:
            print("❌ 报告生成失败（返回None）")
            return False

        print("✅ 报告生成成功")
        print()

        # 提取关键信息
        lines = markdown_content.split('\n')

        print("持仓统计部分:")
        print("-" * 60)
        for i, line in enumerate(lines):
            if any(keyword in line for keyword in ['有持仓ETF', '昨日总仓位', '昨日总资金', '今日总收益']):
                print(line)
        print("-" * 60)
        print()

        # 检查是否显示0
        has_zero = any('| 0仓 |' in line or '| ¥0 |' in line or '| 0个 |' in line for line in lines)

        if has_zero:
            print("⚠️  报告中仍显示0持仓")
            print()
            return False
        else:
            print("✅ 报告显示了正确的持仓数据")
            print()
            return True

    except Exception as e:
        print(f"❌ 报告生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print()
    print("🔍 测试报告生成器使用API数据")
    print()

    # 1. 测试API
    api_data = test_api_data()
    if not api_data:
        print()
        print("=" * 60)
        print("❌ API数据异常，无法继续")
        print("=" * 60)
        return 1

    # 2. 测试报告生成
    report_ok = test_report_generation()

    # 总结
    print("=" * 60)
    print("📋 测试总结")
    print("=" * 60)
    print()

    if api_data and report_ok:
        print("✅ API数据正常")
        print("✅ 报告生成正常")
        print("✅ 报告使用了API数据")
        print()
        print("可以发送到飞书了！")
        return 0
    elif api_data and not report_ok:
        print("✅ API数据正常")
        print("❌ 报告生成异常")
        print()
        print("问题：报告生成器没有正确使用API数据")
        return 1
    else:
        print("❌ API数据异常")
        return 1


if __name__ == "__main__":
    sys.exit(main())
