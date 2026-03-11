#!/usr/bin/env python3
"""
测试API是否返回持仓数据
用于诊断远程服务器的API响应
"""
import sys
import requests
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_api_holdings():
    """测试API是否返回持仓数据"""
    print("=" * 60)
    print("🔌 测试API持仓数据")
    print("=" * 60)
    print()

    # 尝试不同的端口
    api_urls = [
        "http://127.0.0.1:8000/api/watchlist/batch-signals",
        "http://127.0.0.1:8001/api/watchlist/batch-signals"
    ]

    for url in api_urls:
        print(f"尝试连接: {url}")

        try:
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                print(f"✅ 连接成功 (HTTP {response.status_code})")

                data = response.json()

                if data.get('success'):
                    items = data.get('data', [])
                    print(f"✅ 返回 {len(items)} 个ETF的数据")
                    print()

                    # 分析持仓数据
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
                        cur_positions = latest_data.get('positions_used', 0)
                        daily_profit = item.get('daily_profit', 0)

                        if prev_positions > 0:
                            has_positions = True
                            active_count += 1
                            total_positions += prev_positions
                            status = f"✅ {prev_positions}仓"
                        else:
                            status = "❌ 0仓"

                        print(f"  {code} {name[:15]:15s}: "
                              f"previous_positions_used={prev_positions}, "
                              f"daily_profit=¥{daily_profit:.2f} {status}")

                    print()
                    print("-" * 60)
                    print(f"统计（前10个）:")
                    print(f"  有持仓ETF: {active_count}个")
                    print(f"  总仓位: {total_positions}仓")
                    print(f"  总资金: ¥{total_positions * 200:,}")
                    print()

                    if not has_positions:
                        print("⚠️  问题诊断：")
                        print("  API连接成功，但所有ETF的 previous_positions_used 都是 0")
                        print()
                        print("  可能原因：")
                        print("  1. 远程服务器没有运行过回测")
                        print("  2. 回测结果数据不存在")
                        print("  3. 数据库中没有回测记录")
                        print()
                        print("  解决方案：")
                        print("  需要运行回测来生成持仓数据")
                        return False
                    else:
                        print("✅ API返回了正确的持仓数据")
                        return True

                else:
                    print(f"❌ API返回失败: {data}")
                    return False

            else:
                print(f"❌ HTTP错误: {response.status_code}")
                print()
                # 继续尝试下一个URL

        except requests.exceptions.ConnectionError:
            print(f"❌ 连接失败（API服务器可能未运行）")
            print()
            # 继续尝试下一个URL

        except Exception as e:
            print(f"❌ 错误: {e}")
            print()
            # 继续尝试下一个URL

    print()
    print("=" * 60)
    print("⚠️  所有API连接都失败")
    print("=" * 60)
    print()
    print("可能原因：")
    print("  1. API服务器没有运行")
    print("  2. 端口配置不正确")
    print("  3. 防火墙阻止了连接")
    print()
    print("解决方案：")
    print("  启动API服务器：")
    print("    cd /root/etf-predict")
    print("    python run.py")
    print()

    return False


def main():
    success = test_api_holdings()

    if success:
        print()
        print("=" * 60)
        print("✅ API数据正常")
        print("=" * 60)
        print()
        print("如果报告仍显示0持仓，请检查报告生成器的逻辑")
    else:
        print()
        print("=" * 60)
        print("❌ API数据异常或连接失败")
        print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
