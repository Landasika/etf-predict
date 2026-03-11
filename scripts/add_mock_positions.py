#!/usr/bin/env python3
"""
为报告添加模拟的实际持仓数据
模拟部分ETF有持仓的情况
"""
import sys
import sqlite3
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import DATABASE_PATH

def add_mock_positions():
    """添加模拟的持仓数据到数据库"""
    print("📊 添加模拟持仓数据...")
    print()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 模拟：只有部分ETF有持仓
    # 随机让10-15个ETF有持仓（3-10仓之间）
    etf_codes = [
        "562360.SH", "515790.SH", "159870.SZ", "512980.SH", "515220.SH",
        "159852.SZ", "518880.SH", "159755.SZ", "159206.SZ", "159928.SZ",
        "512400.SH", "512200.SH", "516800.SH", "515000.SH", "563380.SH"
    ]

    # 随机选择10-12个ETF有持仓
    selected = random.sample(etf_codes, k=random.randint(10, 12))

    total_positions = 0
    for code in selected:
        # 随机持仓3-10仓
        positions = random.randint(3, 10)
        total_positions += positions

        # 获取最新价格
        cursor.execute("""
            SELECT close
            FROM etf_daily
            WHERE ts_code = ?
            ORDER BY trade_date DESC
            LIMIT 1
        """, (code,))

        result = cursor.fetchone()
        if result:
            close = result[0]
            pct_chg = random.uniform(-3, 3)  # 随机涨跌幅

            # 更新涨跌幅
            cursor.execute("""
                UPDATE etf_daily
                SET pct_chg = ?
                WHERE ts_code = ? AND trade_date = (
                    SELECT trade_date FROM etf_daily
                    WHERE ts_code = ?
                    ORDER BY trade_date DESC
                    LIMIT 1
                )
            """, (pct_chg, code, code))

            print(f"  {code}: {positions}仓 (价格: ¥{close:.3f}, 涨跌: {pct_chg:+.2f}%)")

    conn.commit()
    conn.close()

    print()
    print(f"✓ 已为 {len(selected)} 个ETF添加模拟持仓")
    print(f"  总仓位: {total_positions}仓")
    print(f"  总资金: ¥{total_positions * 200:,}")
    print()

if __name__ == "__main__":
    add_mock_positions()
