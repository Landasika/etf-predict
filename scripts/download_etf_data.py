"""
下载ETF数据脚本
使用 tinyshare SDK 下载 ETF 历史数据
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tinyshare as ts
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


def download_etf_list():
    """下载ETF列表"""
    print("检查 tinyshare 授权码...")
    if not config.TINYSHARE_TOKEN:
        print("❌ 错误：请先在 config.json 中设置 tinyshare.token")
        print("   首次使用：pip install tinyshare --upgrade")
        return False

    print(f"使用授权码: {config.TINYSHARE_TOKEN[:10]}...")
    ts.set_token(config.TINYSHARE_TOKEN)
    pro = ts.pro_api()

    # 使用代理API
    pro._DataApi__token = config.TINYSHARE_TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'
    print("使用代理API: http://lianghua.nanyangqiankun.top")

    print("正在下载ETF列表...")
    try:
        # 获取ETF列表
        df = pro.fund_basic(market='E')

        if df.empty:
            print("❌ 未获取到ETF数据")
            return False

        print(f"✅ 获取到 {len(df)} 个ETF")

        # 保存到数据库
        conn = sqlite3.connect(config.DATABASE_PATH)
        df.to_sql('etf_basic', conn, if_exists='replace', index=False)
        conn.close()

        print(f"✅ ETF列表已保存到数据库")
        return True

    except Exception as e:
        print(f"❌ 下载失败: {str(e)}")
        return False


def download_etf_daily(etf_code=None, start_date=None, end_date=None):
    """下载ETF日线数据"""
    if not config.TINYSHARE_TOKEN:
        print("❌ 请先在 config.json 中设置 tinyshare.token")
        return False

    ts.set_token(config.TINYSHARE_TOKEN)
    pro = ts.pro_api()

    # 使用代理API
    pro._DataApi__token = config.TINYSHARE_TOKEN
    pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'

    # 确定日期范围
    if not end_date:
        end_date = datetime.now().strftime('%Y%m%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365*3)).strftime('%Y%m%d')

    # 获取要下载的ETF列表
    conn = sqlite3.connect(config.DATABASE_PATH)

    if etf_code:
        etf_codes = [etf_code]
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT ts_code FROM etf_basic")
        etf_codes = [row[0] for row in cursor.fetchall()]

    conn.close()

    print(f"准备下载 {len(etf_codes)} 个ETF的日线数据...")
    print(f"时间范围: {start_date} ~ {end_date}")

    success_count = 0
    fail_count = 0

    for i, code in enumerate(etf_codes, 1):
        try:
            print(f"[{i}/{len(etf_codes)}] 下载 {code}...", end=' ')

            # 下载数据（使用fund_daily接口，单位已经是"手"和"千元"）
            df = pro.fund_daily(ts_code=code, start_date=start_date, end_date=end_date)

            if df.empty:
                print("⚠️  无数据")
                fail_count += 1
                continue

            # fund_daily接口数据已经是标准单位，无需转换
            # 保存到数据库
            conn = sqlite3.connect(config.DATABASE_PATH)
            df.to_sql('etf_daily', conn, if_exists='append', index=False)
            conn.close()

            print(f"✅ {len(df)} 条记录")
            success_count += 1

        except Exception as e:
            print(f"❌ 失败: {str(e)}")
            fail_count += 1

    print(f"\n下载完成！")
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")

    return True


def check_data():
    """检查数据完整性"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    # 检查ETF基本信息
    cursor.execute('SELECT COUNT(*) FROM etf_basic')
    etf_count = cursor.fetchone()[0]

    # 检查日线数据
    cursor.execute('SELECT COUNT(*) FROM etf_daily')
    daily_count = cursor.fetchone()[0]

    # 检查数据范围
    cursor.execute('SELECT MIN(trade_date), MAX(trade_date) FROM etf_daily')
    date_range = cursor.fetchone()

    # 检查每个ETF的数据量
    cursor.execute('''
        SELECT ts_code, COUNT(*) as count
        FROM etf_daily
        GROUP BY ts_code
        ORDER BY count DESC
        LIMIT 10
    ''')
    top_etfs = cursor.fetchall()

    conn.close()

    print("\n📊 数据库状态：")
    print(f"   ETF数量: {etf_count}")
    print(f"   日线数据: {daily_count:,} 条")
    print(f"   数据范围: {date_range[0]} ~ {date_range[1]}")

    if top_etfs:
        print(f"\n   数据最多的ETF:")
        for code, count in top_etfs:
            print(f"   - {code}: {count} 条")


if __name__ == '__main__':
    print("=" * 50)
    print("ETF数据下载工具")
    print("=" * 50)

    # 检查配置
    if not config.TUSHARE_TOKEN:
        print("\n⚠️  警告：未配置Tushare Token")
        print("请先完成以下步骤：")
        print("1. 注册账号：https://tushare.pro/register")
        print("2. 获取Token")
        print("3. 编辑 config.py，设置 TUSHARE_TOKEN")
        print("\n或者从现有系统复制数据库文件到：")
        print(f"   {config.DATABASE_PATH}")
        sys.exit(1)

    # 初始化数据库
    print("\n[1/3] 初始化数据库...")
    init_database()

    # 下载ETF列表
    print("\n[2/3] 下载ETF列表...")
    if not download_etf_list():
        sys.exit(1)

    # 下载日线数据
    print("\n[3/3] 下载日线数据...")
    download_etf_daily()

    # 检查数据
    check_data()

    print("\n" + "=" * 50)
    print("✅ 数据下载完成！")
    print("=" * 50)
