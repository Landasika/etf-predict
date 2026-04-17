"""
下载ETF数据脚本 - 使用官方 Tushare 库
支持代理服务器配置
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import config


def init_database():
    """初始化数据库表结构"""
    db_path = config.DATABASE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建ETF基本信息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS etf_basic (
            ts_code TEXT PRIMARY KEY,
            name TEXT,
            extname TEXT,
            market TEXT,
            exchange TEXT,
            list_date TEXT,
            fund_type TEXT
        )
    ''')

    # 创建ETF日线数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS etf_daily (
            ts_code TEXT,
            trade_date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            vol REAL,
            amount REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    ''')

    # 创建索引
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_etf_daily_date
        ON etf_daily(trade_date)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_etf_daily_code
        ON etf_daily(ts_code)
    ''')

    conn.commit()
    conn.close()


def get_tushare_pro():
    """获取配置好的 Tushare Pro API 客户端"""
    if not config.TUSHARE_TOKEN:
        raise ValueError("请先在 config.json 中设置 tushare.token")

    try:
        import tushare as ts
    except ImportError:
        raise ImportError("请先安装 tushare: pip install tushare")

    # 初始化 API 客户端
    pro = ts.pro_api(config.TUSHARE_TOKEN)

    # 设置代理 URL（如果配置了）
    if config.TUSHARE_PROXY_URL:
        pro._DataApi__http_url = config.TUSHARE_PROXY_URL
        print(f"✓ 使用代理服务器: {config.TUSHARE_PROXY_URL}")

    return pro


def download_etf_list():
    """下载ETF列表"""
    print("正在下载ETF列表...")

    try:
        pro = get_tushare_pro()

        # 获取所有ETF基本信息
        df = pro.index_basic(market='SSE,SZSE')  # 上交所和深交所

        if df.empty:
            print("❌ 未获取到ETF数据")
            return False

        # 保存到数据库
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 清空旧数据
        cursor.execute("DELETE FROM etf_basic")

        # 插入新数据
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO etf_basic
                (ts_code, name, extname, market, exchange, list_date, fund_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                row.get('ts_code'),
                row.get('name'),
                row.get('extname', ''),
                row.get('market', ''),
                row.get('exchange', ''),
                row.get('list_date', ''),
                row.get('market_type', '')
            ))

        conn.commit()
        conn.close()

        print(f"✓ 成功下载 {len(df)} 只ETF信息")
        return True

    except Exception as e:
        print(f"❌ 下载ETF列表失败: {e}")
        return False


def download_etf_daily(ts_code, start_date='20200101'):
    """下载单个ETF的日线数据

    Args:
        ts_code: ETF代码，如 '510330.SH'
        start_date: 开始日期，格式 'YYYYMMDD'
    """
    try:
        pro = get_tushare_pro()

        # 获取日线数据
        df = pro.daily(ts_code=ts_code, start_date=start_date)

        if df.empty:
            print(f"  ⚠️  {ts_code} 无数据")
            return False

        # 保存到数据库
        db_path = config.DATABASE_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 删除该ETF的旧数据
        cursor.execute("DELETE FROM etf_daily WHERE ts_code=?", (ts_code,))

        # 插入新数据
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO etf_daily
                (ts_code, trade_date, open, high, low, close, vol, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ts_code,
                row['trade_date'],
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                row['vol'],
                row['amount']
            ))

        conn.commit()
        conn.close()

        print(f"  ✓ {ts_code}: {len(df)} 条记录")
        return True

    except Exception as e:
        print(f"  ❌ {ts_code} 下载失败: {e}")
        return False


def download_all_etf_data():
    """下载所有ETF的日线数据"""
    print("\n开始下载ETF日线数据...")

    # 从数据库获取ETF列表
    db_path = config.DATABASE_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT ts_code FROM etf_basic")
    etf_list = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not etf_list:
        print("❌ 数据库中没有ETF信息，请先运行下载ETF列表")
        return False

    print(f"共 {len(etf_list)} 只ETF需要下载")

    # 计算开始日期（3年前）
    start_date = (datetime.now() - timedelta(days=365*3)).strftime('%Y%m%d')

    success_count = 0
    for i, ts_code in enumerate(etf_list, 1):
        print(f"[{i}/{len(etf_list)}] 正在下载 {ts_code}...")
        if download_etf_daily(ts_code, start_date):
            success_count += 1

    print(f"\n✓ 下载完成: {success_count}/{len(etf_list)} 成功")
    return success_count > 0


def main():
    """主函数"""
    print("=" * 50)
    print("ETF数据下载工具 - Tushare官方版")
    print("=" * 50)

    # 检查配置
    if not config.TUSHARE_TOKEN:
        print("❌ 错误：请先在 config.json 中设置 tushare.token")
        return

    print(f"Token: {config.TUSHARE_TOKEN[:20]}...")
    if config.TUSHARE_PROXY_URL:
        print(f"代理: {config.TUSHARE_PROXY_URL}")
    print()

    # 初始化数据库
    init_database()

    # 下载ETF列表
    if not download_etf_list():
        return

    # 下载日线数据
    download_all_etf_data()

    print("\n✅ 所有数据下载完成！")


if __name__ == '__main__':
    main()
