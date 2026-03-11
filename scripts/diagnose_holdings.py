#!/usr/bin/env python3
"""
飞书报告持仓数据诊断脚本
用于远程服务器诊断为什么报告显示0持仓
"""
import sys
import sqlite3
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import DATABASE_PATH
from core.watchlist import load_watchlist


def diagnose_database_data():
    """诊断数据库中的持仓数据"""
    print("=" * 60)
    print("📊 诊断数据库持仓数据")
    print("=" * 60)
    print()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 1. 检查 extname 字段中的持仓信息
    print("1️⃣  检查 etf_basic 表中的 extname 字段（持仓信息）")
    print("-" * 60)

    # 获取自选ETF列表
    watchlist = load_watchlist()
    etfs = watchlist.get('etfs', []) if watchlist else []

    if not etfs:
        print("  ❌ 无法加载自选列表")
        conn.close()
        return None

    print(f"  自选ETF数量: {len(etfs)}")
    print()

    has_position_data = False
    position_count = 0

    for etf in etfs[:10]:  # 只显示前10个
        code = etf['code']

        cursor.execute("SELECT extname FROM etf_basic WHERE ts_code = ?", (code,))
        result = cursor.fetchone()

        if result and result[0]:
            extname = result[0]
            has_bracket = '[' in extname if extname else False

            status = ""
            if extname and '[' in extname and '仓]' in extname:
                import re
                match = re.search(r'\[(\d+)仓\]', extname)
                if match:
                    positions = int(match.group(1))
                    status = f"✅ {positions}仓"
                    has_position_data = True
                    position_count += 1
                else:
                    status = "⚠️  有[但未解析到仓位"
            elif has_bracket:
                status = "⚠️  有[但无仓标记"
            else:
                status = "❌ 无持仓信息"

            print(f"  {code:15s} | {status}")
        else:
            print(f"  {code:15s} | ❌ extname为空")

    print()
    print(f"  前10个ETF中有持仓数据: {position_count}个")
    print()

    # 2. 统计所有有持仓的ETF
    print("2️⃣  统计所有有持仓的ETF")
    print("-" * 60)

    total_positions = 0
    active_count = 0
    details = []

    for etf in etfs:
        code = etf['code']
        name = etf.get('name', '')

        cursor.execute("SELECT extname FROM etf_basic WHERE ts_code = ?", (code,))
        result = cursor.fetchone()

        positions = 0
        if result and result[0]:
            extname = result[0]
            if '[' in extname and '仓]' in extname:
                import re
                match = re.search(r'\[(\d+)仓\]', extname)
                if match:
                    positions = int(match.group(1))

        if positions > 0:
            active_count += 1
            total_positions += positions
            details.append({
                'code': code,
                'name': name,
                'positions': positions
            })

    print(f"  有持仓ETF数量: {active_count}")
    print(f"  总仓位: {total_positions}仓")
    print(f"  总资金: ¥{total_positions * 200:,}")
    print()

    if active_count > 0:
        print("  有持仓的ETF详情:")
        for item in details[:10]:
            print(f"    {item['code']} {item['name'][:15]:15s}: {item['positions']}仓")
        if len(details) > 10:
            print(f"    ... 还有 {len(details) - 10} 个")
    print()

    conn.close()

    return {
        'has_position_data': has_position_data,
        'active_count': active_count,
        'total_positions': total_positions,
        'total_capital': total_positions * 200
    }


def test_api_endpoint():
    """测试API端点是否返回持仓数据"""
    print("=" * 60)
    print("🔌 测试API端点")
    print("=" * 60)
    print()

    try:
        import requests

        # 尝试连接到本地API
        api_urls = [
            "http://127.0.0.1:8000/api/watchlist/batch-signals",
            "http://127.0.0.1:8001/api/watchlist/batch-signals"
        ]

        for url in api_urls:
            print(f"尝试连接: {url}")
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ API连接成功")

                    data = response.json()
                    if data.get('success'):
                        items = data.get('data', [])
                        print(f"  返回数据: {len(items)}个ETF")
                        print()

                        # 检查持仓数据
                        has_positions = False
                        total_positions = 0
                        active_count = 0

                        print("  前5个ETF的持仓数据:")
                        for item in items[:5]:
                            code = item.get('code')
                            latest_data = item.get('latest_data', {})
                            prev_positions = latest_data.get('previous_positions_used', 0)
                            cur_positions = latest_data.get('positions_used', 0)
                            daily_profit = item.get('daily_profit', 0)

                            status = "❌ 0仓"
                            if prev_positions > 0:
                                status = f"✅ {prev_positions}仓"
                                has_positions = True
                                active_count += 1
                                total_positions += prev_positions

                            print(f"    {code}: previous_positions_used={prev_positions}, "
                                  f"positions_used={cur_positions}, "
                                  f"daily_profit=¥{daily_profit:.2f} {status}")

                        print()
                        print(f"  统计:")
                        print(f"    有持仓ETF: {active_count}个（前5个中）")
                        print(f"    总仓位: {total_positions}仓（前5个中）")

                        if has_positions:
                            print(f"\n✅ API返回了持仓数据")
                            return {
                                'success': True,
                                'has_positions': True,
                                'active_count': active_count,
                                'total_positions': total_positions
                            }
                        else:
                            print(f"\n⚠️  API没有返回持仓数据（previous_positions_used=0）")
                            return {
                                'success': True,
                                'has_positions': False,
                                'active_count': 0,
                                'total_positions': 0
                            }
                    else:
                        print(f"❌ API返回失败: {data}")
                        return {'success': False}
                else:
                    print(f"❌ HTTP错误: {response.status_code}")
            except requests.exceptions.ConnectionError:
                print(f"❌ 连接失败（API服务器可能未运行）")
            except Exception as e:
                print(f"❌ 错误: {e}")

            print()

    except ImportError:
        print("❌ requests模块未安装")

    return {'success': False}


def test_report_generation():
    """测试报告生成"""
    print("=" * 60)
    print("📄 测试报告生成")
    print("=" * 60)
    print()

    try:
        from core.feishu_report import generate_etf_operation_report

        print("正在生成报告...")
        markdown_content = generate_etf_operation_report()

        if not markdown_content:
            print("❌ 报告生成失败（返回None）")
            return {'success': False}

        print("✅ 报告生成成功")
        print()

        # 提取关键信息
        lines = markdown_content.split('\n')

        print("持仓统计部分:")
        for i, line in enumerate(lines):
            if '有持仓ETF' in line or '昨日总仓位' in line or '昨日总资金' in line or '今日总收益' in line:
                print(f"  {line}")

        print()

        # 保存完整报告到文件
        report_path = Path(__file__).parent.parent / "diagnostic_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        print(f"📄 完整报告已保存到: {report_path}")
        print()

        return {'success': True}

    except Exception as e:
        print(f"❌ 报告生成失败: {e}")
        import traceback
        traceback.print_exc()
        print()
        return {'success': False}


def main():
    print()
    print("🔍 ETF持仓数据诊断")
    print()

    # 1. 诊断数据库
    db_result = diagnose_database_data()

    # 2. 测试API
    api_result = test_api_endpoint()

    # 3. 测试报告生成
    report_result = test_report_generation()

    # 总结
    print("=" * 60)
    print("📋 诊断总结")
    print("=" * 60)
    print()

    if db_result:
        if db_result['has_position_data']:
            print("✅ 数据库: 有持仓数据")
            print(f"   {db_result['active_count']}个ETF, {db_result['total_positions']}仓, ¥{db_result['total_capital']:,}")
        else:
            print("❌ 数据库: 无持仓数据")
            print("   💡 需要运行回测或使用脚本添加模拟数据")
    else:
        print("❌ 数据库: 诊断失败")

    if api_result['success']:
        if api_result['has_positions']:
            print("✅ API: 返回持仓数据")
        else:
            print("⚠️  API: 连接成功但无持仓数据")
    else:
        print("❌ API: 连接失败")
        print("   💡 确保API服务器正在运行（python run.py）")

    if report_result['success']:
        print("✅ 报告生成: 成功")
    else:
        print("❌ 报告生成: 失败")

    print()

    # 给出建议
    print("=" * 60)
    print("💡 解决建议")
    print("=" * 60)
    print()

    if db_result and not db_result['has_position_data']:
        print("方案1: 添加模拟持仓数据（用于测试）")
        print("  python3 scripts/test_report_with_data.py")
        print()
        print("方案2: 运行完整的回测以获取真实持仓")
        print("  访问 http://127.0.0.1:8001/backtest")
        print()

    if not api_result['success']:
        print("方案: 启动API服务器")
        print("  cd /root/etf-predict")
        print("  python run.py")
        print()

    if db_result and db_result['has_position_data'] and not api_result['has_positions']:
        print("⚠️  发现问题:")
        print("  数据库有持仓数据，但API没有返回")
        print("  可能原因: API未从数据库extname字段解析持仓")
        print("  解决: 重启API服务器")
        print()

    print()


if __name__ == "__main__":
    main()
