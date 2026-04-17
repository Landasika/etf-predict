"""
Tushare 使用示例
演示如何在项目中使用配置好的 Tushare 代理
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import tushare as ts
import pandas as pd


def example_1_basic_usage():
    """示例1: 基础使用"""
    print("\n" + "="*50)
    print("示例1: 基础使用 - 获取指数基本信息")
    print("="*50)

    # 初始化 API
    pro = ts.pro_api(config.TUSHARE_TOKEN)

    # ⭐ 关键步骤：设置代理 URL
    if config.TUSHARE_PROXY_URL:
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL
        print(f"✓ 使用代理: {config.TUSHARE_PROXY_URL}")

    # 获取指数基本信息
    df = pro.index_basic(market='SSE', limit=10)
    print(f"\n获取到 {len(df)} 条指数信息：")
    print(df[['ts_code', 'name', 'market', 'list_date']].to_string(index=False))


def example_2_get_etf_data():
    """示例2: 获取 ETF 数据"""
    print("\n" + "="*50)
    print("示例2: 获取 ETF 日线数据")
    print("="*50)

    # 初始化 API
    pro = ts.pro_api(config.TUSHARE_TOKEN)
    if config.TUSHARE_PROXY_URL:
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL

    # 获取沪深300 ETF 数据（使用实际存在的日期范围）
    ts_code = '510330.SH'
    df = pro.daily(ts_code=ts_code, start_date='20240101', end_date='20241231')

    if df.empty:
        print(f"⚠️  {ts_code} 没有获取到数据，可能日期范围不正确")
        return

    print(f"\n{ts_code} 沪深300 ETF 最近数据：")
    print(df.head(10).to_string(index=False))


def example_3_multiple_etfs():
    """示例3: 批量获取多个 ETF 数据"""
    print("\n" + "="*50)
    print("示例3: 批量获取多个 ETF 数据")
    print("="*50)

    # 初始化 API
    pro = ts.pro_api(config.TUSHARE_TOKEN)
    if config.TUSHARE_PROXY_URL:
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL

    # 常见 ETF 代码
    etf_list = [
        '510330.SH',  # 沪深300
        '510500.SH',  # 中证500
        '159915.SZ',  # 创业板
    ]

    print(f"\n获取 {len(etf_list)} 只 ETF 的最新数据...")

    for ts_code in etf_list:
        try:
            # 获取最新5天数据
            df = pro.daily(ts_code=ts_code, limit=5)
            if not df.empty:
                latest = df.iloc[0]
                print(f"\n{ts_code}: {latest['trade_date']} 收盘价 {latest['close']:.3f}")
        except Exception as e:
            print(f"\n{ts_code}: 获取失败 - {e}")


def example_4_save_to_database():
    """示例4: 保存数据到数据库"""
    print("\n" + "="*50)
    print("示例4: 保存数据到数据库")
    print("="*50)

    import sqlite3

    # 初始化 API
    pro = ts.pro_api(config.TUSHARE_TOKEN)
    if config.TUSHARE_PROXY_URL:
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL

    # 获取数据
    ts_code = '510330.SH'
    df = pro.daily(ts_code=ts_code, start_date='20250101')

    # 保存到数据库
    conn = sqlite3.connect(config.DATABASE_PATH)
    df.to_sql('etf_daily_test', conn, if_exists='replace', index=False)
    conn.close()

    print(f"\n✓ 已保存 {len(df)} 条数据到数据库")


def main():
    """运行所有示例"""
    print("\n" + "="*50)
    print("Tushare 代理使用示例")
    print("="*50)
    print(f"\n配置信息：")
    print(f"  Token: {config.TUSHARE_TOKEN[:20]}...")
    print(f"  代理: {config.TUSHARE_PROXY_URL}")

    try:
        # 运行示例
        example_1_basic_usage()
        example_2_get_etf_data()
        example_3_multiple_etfs()
        # example_4_save_to_database()  # 需要数据库已初始化

        print("\n" + "="*50)
        print("✅ 所有示例运行完成")
        print("="*50)

    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        print("\n请检查：")
        print("  1. config.json 中的配置是否正确")
        print("  2. 代理服务器是否可用")
        print("  3. Token 是否有效")


if __name__ == '__main__':
    main()
