#!/usr/bin/env python3
"""
直接调用API函数获取持仓数据
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.watchlist import load_watchlist
from core.database import get_etf_connection, get_latest_data_date

async def test_position_data():
    print("=" * 60)
    print("📊 测试持仓数据获取")
    print("=" * 60)
    print()

    # 加载自选列表
    watchlist = load_watchlist()
    etfs = watchlist.get('etfs', [])

    print(f"自选ETF数量: {len(etfs)}")
    print()

    # 获取最新数据日期
    data_date = get_latest_data_date()
    print(f"最新数据日期: {data_date}")
    print()

    # 查看数据库中的数据
    conn = get_etf_connection()
    if conn:
        cursor = conn.cursor()

        # 检查是否有回测结果数据
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%backtest%'
        """)
        tables = cursor.fetchall()
        print(f"数据库中的回测表: {[t[0] for t in tables]}")
        print()

        # 查看前几个ETF的最新数据
        for etf in etfs[:3]:
            code = etf['code']

            cursor.execute("""
                SELECT close, pct_chg, trade_date
                FROM etf_daily
                WHERE ts_code = ?
                ORDER BY trade_date DESC
                LIMIT 1
            """, (code,))

            result = cursor.fetchone()
            if result:
                close, pct_chg, trade_date = result
                print(f"{code} {etf['name']}")
                print(f"  收盘价: {close}")
                print(f"  涨跌幅: {pct_chg}%")
                print(f"  交易日期: {trade_date}")
                print()

        conn.close()

    print()
    print("=" * 60)
    print("💡 说明:")
    print("   如果没有策略回测数据，previous_positions_used 会是 0")
    print("   需要运行回测才能获取实际持仓数据")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_position_data())
