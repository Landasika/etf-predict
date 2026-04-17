"""
测试 ETF 相关的 Tushare API
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import tushare as ts

def get_pro():
    """获取配置好的 API 客户端"""
    pro = ts.pro_api(config.TUSHARE_TOKEN)
    if config.TUSHARE_PROXY_URL:
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL
    return pro


def test_index_basic():
    """测试指数基础信息"""
    print("\n1. 测试指数基础信息 (index_basic)")
    print("-" * 50)
    try:
        pro = get_pro()
        df = pro.index_basic(market='SSE', limit=5)
        print(f"✅ 成功！获取到 {len(df)} 条指数数据")
        print(df[['ts_code', 'name', 'market']].to_string(index=False))
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


def test_etf_basic():
    """测试 ETF 基础信息"""
    print("\n2. 测试 ETF 基础信息")
    print("-" * 50)
    try:
        pro = get_pro()

        # 尝试不同的参数组合
        print("  尝试1: market='SSE,SZSE'")
        df = pro.index_basic(market='SSE,SZSE', limit=10)

        if df.empty:
            print("  ⚠️ 返回为空，尝试其他方法")

        # 过滤 ETF
        etf_df = df[df['ts_code'].str.match(r'^\d{6}\.(SH|SZ)$')]
        print(f"✅ 成功！获取到 {len(etf_df)} 条 ETF 数据")
        if not etf_df.empty:
            print(etf_df[['ts_code', 'name', 'market']].head().to_string(index=False))
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


def test_daily_data():
    """测试日线数据"""
    print("\n3. 测试日线数据 (daily)")
    print("-" * 50)

    test_codes = ['510330.SH', '000001.SZ', '510300.SH']

    for ts_code in test_codes:
        try:
            pro = get_pro()
            print(f"  尝试获取 {ts_code}...")

            # 尝试不同的日期范围
            df = pro.daily(ts_code=ts_code, start_date='20240101', end_date='20241231')

            if not df.empty:
                print(f"  ✅ {ts_code}: 获取到 {len(df)} 条数据")
                print(f"     最新日期: {df.iloc[0]['trade_date']}, 收盘价: {df.iloc[0]['close']}")
                return True
            else:
                print(f"  ⚠️ {ts_code}: 无数据")

        except Exception as e:
            print(f"  ❌ {ts_code}: {e}")

    return False


def test_fund_basic():
    """测试基金基础信息"""
    print("\n4. 测试基金基础信息 (fund_basic)")
    print("-" * 50)
    try:
        pro = get_pro()

        # 尝试获取基金信息
        df = pro.fund_basic(market='E', status='L', limit=10)

        if not df.empty:
            print(f"✅ 成功！获取到 {len(df)} 条基金数据")
            print(df[['ts_code', 'name', 'management']].to_string(index=False))
            return True
        else:
            print("⚠️ 返回为空")
            return False
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


def test_specific_etf():
    """测试特定 ETF 代码"""
    print("\n5. 测试常见 ETF 代码")
    print("-" * 50)

    # 常见的 ETF 代码
    etf_codes = {
        '510300.SH': '沪深300ETF',
        '510500.SH': '中证500ETF',
        '510330.SH': '沪深300ETF',
        '159915.SZ': '创业板ETF',
        '159919.SZ': '沪深300ETF',
    }

    pro = get_pro()

    for code, name in etf_codes.items():
        try:
            # 先查询基本信息
            df_info = pro.index_basic(ts_code=code)

            if not df_info.empty:
                print(f"  ✅ {code} ({name}): 存在")

                # 尝试获取日线数据
                df_daily = pro.daily(ts_code=code, limit=5)
                if not df_daily.empty:
                    print(f"     最新数据: {df_daily.iloc[0]['trade_date']}, 收盘: {df_daily.iloc[0]['close']}")
                else:
                    print(f"     ⚠️ 无日线数据")
            else:
                print(f"  ❌ {code} ({name}): 不存在")

        except Exception as e:
            print(f"  ❌ {code} ({name}): {e}")


if __name__ == '__main__':
    print("=" * 50)
    print("ETF API 接口测试")
    print("=" * 50)
    print(f"\n配置信息:")
    print(f"  Token: {config.TUSHARE_TOKEN[:20]}...")
    print(f"  代理: {config.TUSHARE_PROXY_URL}")

    # 运行测试
    test_index_basic()
    test_etf_basic()
    test_daily_data()
    test_fund_basic()
    test_specific_etf()

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
