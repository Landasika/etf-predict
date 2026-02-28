#!/usr/bin/env python3
"""
测试 minishare SDK 获取ETF实时行情

使用方法:
    python test_minishare.py

功能:
    1. 测试 minishare SDK 连接
    2. 获取上海市场ETF实时行情
    3. 获取深圳市场ETF实时行情
    4. 显示部分数据预览
"""

import sys
from datetime import datetime

def test_minishare():
    """测试 minishare SDK 功能"""

    print("=" * 60)
    print("🧪 minishare SDK 测试脚本")
    print("=" * 60)

    # 1. 检查 SDK 是否安装
    print("\n📦 检查 minishare SDK...")
    try:
        import minishare as ms
        print("✅ minishare SDK 已安装")
    except ImportError:
        print("❌ minishare SDK 未安装")
        print("   请运行: pip install minishare --upgrade")
        return False

    # 2. 配置授权码
    token = "6xH3v19jLi9AZ4N2m7Qsn98hur2Mle9ock6RT9Dnt7Ys3GAPMf00H0gl3d5355fd"
    print(f"\n🔑 使用授权码: {token[:10]}...")

    # 3. 初始化 API
    print("\n🔌 初始化 API 连接...")
    try:
        pro = ms.pro_api(token)
        print("✅ API 初始化成功")
    except Exception as e:
        print(f"❌ API 初始化失败: {e}")
        return False

    # 4. 测试获取深圳市场ETF实时行情
    print("\n" + "=" * 60)
    print("📊 获取深圳市场ETF实时行情 (*.SZ)...")
    print("=" * 60)

    try:
        df_sz = pro.rt_etf_k_ms(ts_code='*.SZ')

        if df_sz is None or df_sz.empty:
            print("⚠️  深圳市场无数据返回（可能非交易时间）")
        else:
            print(f"✅ 成功获取 {len(df_sz)} 条数据")
            print(f"\n数据列: {list(df_sz.columns)}")

            # 显示前10条数据
            print(f"\n📋 前10条数据预览:")
            print("-" * 100)
            display_cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol']
            available_cols = [col for col in display_cols if col in df_sz.columns]

            for idx, row in df_sz.head(10).iterrows():
                print(f"  {row.get('ts_code', 'N/A'):>12} | "
                      f"{row.get('trade_date', 'N/A')} | "
                      f"开:{row.get('open', 0):>7.2f} | "
                      f"高:{row.get('high', 0):>7.2f} | "
                      f"低:{row.get('low', 0):>7.2f} | "
                      f"收:{row.get('close', 0):>7.2f} | "
                      f"量:{row.get('vol', 0):>10.0f}")

            # 显示统计信息
            print(f"\n📈 数据统计:")
            print(f"  总记录数: {len(df_sz)}")
            if 'close' in df_sz.columns and len(df_sz) > 0:
                print(f"  价格范围: {df_sz['close'].min():.2f} - {df_sz['close'].max():.2f}")
                print(f"  平均价格: {df_sz['close'].mean():.2f}")

    except Exception as e:
        print(f"❌ 获取深圳市场数据失败: {e}")
        import traceback
        traceback.print_exc()

    # 5. 测试获取上海市场ETF实时行情
    print("\n" + "=" * 60)
    print("📊 获取上海市场ETF实时行情 (*.SH)...")
    print("=" * 60)

    try:
        df_sh = pro.rt_etf_k_ms(ts_code='*.SH')

        if df_sh is None or df_sh.empty:
            print("⚠️  上海市场无数据返回（可能非交易时间）")
        else:
            print(f"✅ 成功获取 {len(df_sh)} 条数据")
            print(f"\n数据列: {list(df_sh.columns)}")

            # 显示前10条数据
            print(f"\n📋 前10条数据预览:")
            print("-" * 100)
            display_cols = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol']
            available_cols = [col for col in display_cols if col in df_sh.columns]

            for idx, row in df_sh.head(10).iterrows():
                print(f"  {row.get('ts_code', 'N/A'):>12} | "
                      f"{row.get('trade_date', 'N/A')} | "
                      f"开:{row.get('open', 0):>7.2f} | "
                      f"高:{row.get('high', 0):>7.2f} | "
                      f"低:{row.get('low', 0):>7.2f} | "
                      f"收:{row.get('close', 0):>7.2f} | "
                      f"量:{row.get('vol', 0):>10.0f}")

            # 显示统计信息
            print(f"\n📈 数据统计:")
            print(f"  总记录数: {len(df_sh)}")
            if 'close' in df_sh.columns and len(df_sh) > 0:
                print(f"  价格范围: {df_sh['close'].min():.2f} - {df_sh['close'].max():.2f}")
                print(f"  平均价格: {df_sh['close'].mean():.2f}")

    except Exception as e:
        print(f"❌ 获取上海市场数据失败: {e}")
        import traceback
        traceback.print_exc()

    # 6. 测试特定ETF
    print("\n" + "=" * 60)
    print("🎯 测试获取特定ETF数据...")
    print("=" * 60)

    test_etfs = ['159672.SZ', '510330.SH', '159928.SZ', '510050.SH']

    for etf_code in test_etfs:
        market = etf_code.split('.')[1]
        try:
            df = pro.rt_etf_k_ms(ts_code=f'*.{market}')

            if df is not None and not df.empty:
                etf_data = df[df['ts_code'] == etf_code]
                if not etf_data.empty:
                    row = etf_data.iloc[-1]
                    print(f"  ✅ {etf_code}: "
                          f"日期={row.get('trade_date', 'N/A')}, "
                          f"开盘={row.get('open', 0):.2f}, "
                          f"收盘={row.get('close', 0):.2f}")
                else:
                    print(f"  ⚠️  {etf_code}: 无数据")
            else:
                print(f"  ❌ {etf_code}: 获取失败")
        except Exception as e:
            print(f"  ❌ {etf_code}: {e}")

    # 7. 总结
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
    print(f"\n当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    now = datetime.now()
    weekday = now.weekday()
    current_time = now.time()

    # 交易时间判断
    start_time = datetime.strptime("09:25", "%H:%M").time()
    end_time = datetime.strptime("15:05", "%H:%M").time()

    is_weekday = weekday < 5
    is_trading_time = start_time <= current_time <= end_time

    print(f"是否工作日: {'是' if is_weekday else '否 (周末)'}")
    print(f"是否交易时间: {'是' if is_trading_time else '否'}")

    if not is_weekday:
        print("\n💡 提示: 周末可能没有实时数据")
    elif not is_trading_time:
        print("\n💡 提示: 非交易时间段，可能返回的是历史数据")
    else:
        print("\n✅ 当前为交易时间，应该能获取到实时数据")

    return True


if __name__ == '__main__':
    try:
        success = test_minishare()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试已中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
