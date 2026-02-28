"""
数据检查脚本
检查ETF数据库的完整性和质量
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import config


def check_database():
    """检查数据库状态"""
    db_path = config.DATABASE_PATH

    if not os.path.exists(db_path):
        print("❌ 数据库不存在")
        print(f"   路径: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("📦 数据库状态")
    print(f"   文件: {db_path}")
    file_size = os.path.getsize(db_path) / (1024 * 1024)
    print(f"   大小: {file_size:.2f} MB")

    # 检查表结构
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"   表: {', '.join(tables)}")

    conn.close()
    return True


def check_etf_basic():
    """检查ETF基本信息"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    print("\n📋 ETF基本信息")

    try:
        cursor.execute('SELECT COUNT(*) FROM etf_basic')
        count = cursor.fetchone()[0]
        print(f"   总数: {count}")

        # 按市场分类
        cursor.execute('SELECT market, COUNT(*) FROM etf_basic GROUP BY market')
        by_market = cursor.fetchall()
        if by_market:
            print(f"   按市场分类:")
            for market, cnt in by_market:
                print(f"   - {market}: {cnt}")

    except Exception as e:
        print(f"   ❌ 错误: {str(e)}")

    conn.close()


def check_etf_daily():
    """检查日线数据"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    print("\n📈 日线数据")

    try:
        cursor.execute('SELECT COUNT(*) FROM etf_daily')
        total = cursor.fetchone()[0]
        print(f"   总记录数: {total:,}")

        # 数据范围
        cursor.execute('SELECT MIN(trade_date), MAX(trade_date) FROM etf_daily')
        min_date, max_date = cursor.fetchone()
        print(f"   数据范围: {min_date} ~ {max_date}")

        # 有数据的ETF数量
        cursor.execute('SELECT COUNT(DISTINCT ts_code) FROM etf_daily')
        etf_with_data = cursor.fetchone()[0]
        print(f"   有数据的ETF: {etf_with_data}")

        # 每个ETF的数据量
        cursor.execute('''
            SELECT ts_code, COUNT(*) as count
            FROM etf_daily
            GROUP BY ts_code
            ORDER BY count DESC
        ''')
        etf_counts = cursor.fetchall()

        if etf_counts:
            print(f"\n   数据量最多的ETF:")
            for code, count in etf_counts[:5]:
                print(f"   - {code}: {count} 条")

            print(f"\n   数据量最少的ETF:")
            for code, count in etf_counts[-5:]:
                print(f"   - {code}: {count} 条")

        # 检查缺失数据
        cursor.execute('''
            SELECT b.ts_code, b.name
            FROM etf_basic b
            LEFT JOIN etf_daily d ON b.ts_code = d.ts_code
            WHERE d.ts_code IS NULL
            LIMIT 10
        ''')
        missing = cursor.fetchall()

        if missing:
            print(f"\n   ⚠️  没有日线数据的ETF:")
            for code, name in missing:
                print(f"   - {code} ({name})")

    except Exception as e:
        print(f"   ❌ 错误: {str(e)}")

    conn.close()


def check_data_quality():
    """检查数据质量"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    print("\n✅ 数据质量检查")

    issues = []

    # 1. 检查缺失值
    cursor.execute('''
        SELECT COUNT(*)
        FROM etf_daily
        WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
    ''')
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        issues.append(f"发现 {null_count} 条记录包含缺失值")

    # 2. 检查异常值（价格为0或负数）
    cursor.execute('''
        SELECT COUNT(*)
        FROM etf_daily
        WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
    ''')
    invalid_price = cursor.fetchone()[0]
    if invalid_price > 0:
        issues.append(f"发现 {invalid_price} 条记录包含无效价格")

    # 3. 检查价格逻辑（low > high等）
    cursor.execute('''
        SELECT COUNT(*)
        FROM etf_daily
        WHERE low > high OR open > high OR close > high
        OR high < low OR open < low OR close < low
    ''')
    logic_error = cursor.fetchone()[0]
    if logic_error > 0:
        issues.append(f"发现 {logic_error} 条记录价格逻辑错误")

    # 4. 检查数据连续性
    cursor.execute('''
        SELECT ts_code, COUNT(*) as gap_count
        FROM (
            SELECT ts_code, trade_date,
                LAG(trade_date) OVER (PARTITION BY ts_code ORDER BY trade_date) as prev_date
            FROM etf_daily
        )
        WHERE prev_date IS NOT NULL
          AND trade_date != date(prev_date, '+1 day')
          AND trade_date != date(prev_date, '+3 days')  # 跳过周末
          AND trade_date != date(prev_date, '+4 days')  # 跳过小长假
        GROUP BY ts_code
        ORDER BY gap_count DESC
        LIMIT 5
    ''')
    gap_etfs = cursor.fetchall()

    if gap_etfs:
        print(f"   ⚠️  数据不连续的ETF:")
        for code, gap_count in gap_etfs:
            print(f"   - {code}: {gap_count} 处间隔")

    # 5. 检查最新数据
    cursor.execute('''
        SELECT MAX(trade_date) FROM etf_daily
    ''')
    latest_date = cursor.fetchone()[0]
    today = datetime.now().strftime('%Y%m%d')

    if latest_date:
        latest_dt = datetime.strptime(latest_date, '%Y%m%d')
        today_dt = datetime.strptime(today, '%Y%m%d')
        days_behind = (today_dt - latest_dt).days

        if days_behind > 7:
            issues.append(f"数据落后 {days_behind} 天（最新: {latest_date}）")
        else:
            print(f"   ✅ 数据更新及时（最新: {latest_date}）")

    # 打印问题汇总
    if issues:
        print(f"\n   ⚠️  发现的问题:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print(f"   ✅ 未发现明显问题")

    conn.close()


def check_specific_etf(etf_code):
    """检查特定ETF的数据"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    print(f"\n🔍 检查ETF: {etf_code}")

    # 基本信息
    cursor.execute('SELECT * FROM etf_basic WHERE ts_code = ?', (etf_code,))
    basic_info = cursor.fetchone()

    if not basic_info:
        print(f"   ❌ 未找到该ETF")
        conn.close()
        return

    print(f"   名称: {basic_info[2] if basic_info[2] else basic_info[1]}")
    print(f"   市场: {basic_info[3]}")
    print(f"   上市日期: {basic_info[5]}")

    # 日线数据
    cursor.execute('''
        SELECT COUNT(*), MIN(trade_date), MAX(trade_date)
        FROM etf_daily
        WHERE ts_code = ?
    ''', (etf_code,))
    count, min_date, max_date = cursor.fetchone()

    print(f"   数据量: {count} 条")
    print(f"   数据范围: {min_date} ~ {max_date}")

    # 最近数据
    cursor.execute('''
        SELECT trade_date, open, high, low, close, vol
        FROM etf_daily
        WHERE ts_code = ?
        ORDER BY trade_date DESC
        LIMIT 5
    ''', (etf_code,))
    recent_data = cursor.fetchall()

    if recent_data:
        print(f"\n   最近5个交易日:")
        for row in recent_data:
            print(f"   {row[0]}: 开{row[1]:.3f} 高{row[2]:.3f} "
                  f"低{row[3]:.3f} 收{row[4]:.3f} 量{row[5]:.0f}")

    conn.close()


if __name__ == '__main__':
    print("=" * 50)
    print("ETF数据质量检查工具")
    print("=" * 50)

    # 检查数据库
    if not check_database():
        sys.exit(1)

    # 检查基本信息
    check_etf_basic()

    # 检查日线数据
    check_etf_daily()

    # 检查数据质量
    check_data_quality()

    # 如果指定了ETF代码，检查特定ETF
    if len(sys.argv) > 1:
        etf_code = sys.argv[1]
        check_specific_etf(etf_code)

    print("\n" + "=" * 50)
    print("✅ 检查完成！")
    print("=" * 50)
