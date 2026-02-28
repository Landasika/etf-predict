"""
数据库初始化脚本
检查并创建必要的数据库和表结构
"""
import os
import sqlite3
from pathlib import Path
import config

def init_database():
    """初始化ETF数据库"""
    db_path = config.DATABASE_PATH

    # 检查数据库是否存在
    if Path(db_path).exists():
        print(f"✅ 数据库已存在: {db_path}")
        return True

    # 创建数据目录
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # 创建数据库和表结构
    print(f"📦 创建数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建ETF基本信息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS etf_basic (
            ts_code TEXT PRIMARY KEY,
            name TEXT,
            extname TEXT,
            market TEXT,
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

    print("✅ 数据库表结构创建完成")
    print("\n⚠️  数据库未包含数据，请运行以下命令获取数据：")
    print("   python scripts/download_etf_data.py")
    print("\n或者从现有系统复制数据库文件到：")
    print(f"   {db_path}")

    return True


def check_data_integrity():
    """检查数据完整性"""
    db_path = config.DATABASE_PATH

    if not Path(db_path).exists():
        print("❌ 数据库不存在")
        return False

    conn = sqlite3.connect(db_path)
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

    conn.close()

    print(f"\n📊 数据库状态：")
    print(f"   ETF数量: {etf_count}")
    print(f"   日线数据: {daily_count:,} 条")
    print(f"   数据范围: {date_range[0]} ~ {date_range[1]}")

    return True


if __name__ == '__main__':
    print("=" * 50)
    print("ETF预测系统 - 数据库初始化")
    print("=" * 50)

    init_database()
    check_data_integrity()

    print("\n" + "=" * 50)
