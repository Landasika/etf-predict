#!/usr/bin/env python3
"""
清除数据库中的模拟持仓数据
从extname字段移除 [X仓] 标记
"""
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import DATABASE_PATH


def clear_mock_positions():
    """清除模拟持仓数据"""
    print("=" * 60)
    print("🧹 清除模拟持仓数据")
    print("=" * 60)
    print()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 先查看有多少ETF有持仓信息
    cursor.execute("""
        SELECT ts_code, extname
        FROM etf_basic
        WHERE extname LIKE '%[%仓]'
    """)

    etfs_with_positions = cursor.fetchall()

    if not etfs_with_positions:
        print("✓ 数据库中没有持仓数据（extname中没有[X仓]标记）")
        conn.close()
        return

    print(f"找到 {len(etfs_with_positions)} 个ETF有持仓信息:")
    for code, extname in etfs_with_positions[:10]:
        print(f"  {code}: {extname[:50]}")
    if len(etfs_with_positions) > 10:
        print(f"  ... 还有 {len(etfs_with_positions) - 10} 个")
    print()

    # 清除持仓信息
    print("正在清除...")
    cursor.execute("""
        UPDATE etf_basic
        SET extname = REPLACE(
            REPLACE(extname, ' [' || substr(extname, instr(extname, '[') + 1, instr(extname, '仓]') - instr(extname, '[') - 1) || '仓]', ''),
            '  ', ' '
        )
        WHERE extname LIKE '%[%仓]'
    """)

    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()

    print()
    print(f"✓ 已清除 {affected_rows} 个ETF的持仓数据")
    print()


if __name__ == "__main__":
    clear_mock_positions()
