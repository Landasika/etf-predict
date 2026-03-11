#!/usr/bin/env python3
"""
诊断API数据
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from core.database import get_etf_connection

    # 测试API连接
    print("=" * 60)
    print("📊 API数据诊断")
    print("=" * 60)
    print()

    # 尝试获取API数据（不认证）
    api_url = "http://127.0.0.1:8000/api/watchlist/batch-signals"

    print(f"📍 请求API: {api_url}")
    print()

    # 先测试一下简单的API
    try:
        response = requests.get(api_url, timeout=5)
        print(f"状态码: {response.status_code}")

        if response.status_code == 401:
            print("❌ 需要认证")
            print()

            # 尝试带认证
            print("🔑 尝试使用认证...")
            response = requests.get(api_url, headers={"Authorization": "Bearer admin123"}, timeout=5)
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    items = data.get('data', [])[:3]  # 只看前3个

                    print(f"✓ 获取到 {len(data.get('data', []))} 个ETF数据")
                    print()

                    for item in items:
                        code = item['code']
                        latest = item.get('latest_data', {})
                        prev_pos = latest.get('previous_positions_used', 0)
                        daily_profit = item.get('daily_profit', 0)

                        print(f"  {code}")
                        print(f"    previous_positions_used: {prev_pos}")
                        print(f"    daily_profit: ¥{daily_profit}")
                        print()
        else:
            print(f"❌ 请求失败: {response.text[:200]}")
    except Exception as e:
        print(f"❌ API请求失败: {e}")

    print()
    print("=" * 60)
    print("💡 如果 previous_positions_used 都是 0，")
    print("   说明策略回测数据需要更新")
    print("=" * 60)

except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
