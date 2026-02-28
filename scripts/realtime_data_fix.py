"""
实时数据修复脚本 - 处理24-25日的单位转换问题

问题：
- 历史数据接口 fund_daily 返回的vol单位是"手"
- 实时数据接口 rt_etf_k 返回的vol单位是"股"
- 1手 = 100股

解决方案：
- 检测异常大的成交量（可能是"股"单位）
- 自动转换为"手"（除以100）
- 保存到数据库
"""
import sqlite3
import config
import tushare as ts
from datetime import datetime, timedelta


def check_abnormal_volume(etf_code: str, vol: float) -> bool:
    """检查成交量是否异常（可能是"股"而不是"手"）

    正常ETF日成交量：10万 - 1000万手
    如果超过5000万手，可能是单位错误
    """
    # 如果成交量超过5000万，可能是"股"单位
    return vol > 50_000_000


def fix_volume_unit(etf_code: str, trade_date: str, vol: float) -> float:
    """修复成交量单位

    如果vol异常大，除以100转换为"手"
    """
    if check_abnormal_volume(etf_code, vol):
        print(f"  ⚠️  检测到异常成交量 {vol:.0f}，可能是'股'单位，转换为'手'")
        return vol / 100
    return vol


def fix_existing_data():
    """修复数据库中已有的异常数据"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    # 查找所有异常大的成交量数据
    cursor.execute('''
        SELECT ts_code, trade_date, vol, amount
        FROM etf_daily
        WHERE vol > 50_000_000
        ORDER BY vol DESC
    ''')

    abnormal_data = cursor.fetchall()
    print(f"找到 {len(abnormal_data)} 条异常成交量数据")
    print("=" * 70)

    fixed_count = 0
    for row in abnormal_data:
        ts_code, trade_date, vol, amount = row
        fixed_vol = vol / 100

        print(f"{ts_code} {trade_date}:")
        print(f"  原成交量: {vol:.0f} ({vol/10000:.2f}万手)")
        print(f"  修正后: {fixed_vol:.0f} ({fixed_vol/10000:.2f}万手)")

        # 更新数据库
        cursor.execute('''
            UPDATE etf_daily
            SET vol = ?
            WHERE ts_code = ? AND trade_date = ?
        ''', (fixed_vol, ts_code, trade_date))

        fixed_count += 1

    conn.commit()
    conn.close()

    print(f"\n✅ 已修复 {fixed_count} 条数据")


def download_realtime_data():
    """
    使用实时接口（rt_etf_k）下载今日数据

    接口说明：
    - rt_etf_k: 实时接口，vol单位是"股"，amount单位是"元"
    - fund_daily: 历史接口，vol单位是"手"，amount单位是"千元"

    本函数使用rt_etf_k，需要转换单位后保存
    """
    try:
        ts.set_token(config.TUSHARE_TOKEN)
        pro = ts.pro_api()

        # 读取watchlist
        import json
        with open(config.WATCHLIST_PATH, 'r') as f:
            watchlist = json.load(f)

        etf_codes = [etf['code'] for etf in watchlist.get('etfs', [])]

        print(f"使用实时接口(rt_etf_k)下载 {len(etf_codes)} 个ETF的最新数据...")
        print("=" * 70)

        conn = sqlite3.connect(config.DATABASE_PATH)

        for code in etf_codes[:5]:  # 先测试前5个
            try:
                # 判断交易所
                if code.endswith('.SH'):
                    # 沪市ETF
                    df = pro.rt_etf_k(ts_code=code, topic='HQ_FND_TICK')
                else:
                    # 深市ETF
                    df = pro.rt_etf_k(ts_code=code)

                if df.empty:
                    print(f"{code}: ⚠️  无实时数据")
                    continue

                # rt_etf_k返回的是实时数据
                # vol单位是"股" -> 需要除以100转为"手"
                # amount单位是"元" -> 需要除以1000转为"千元"
                row = df.iloc[0]

                # 获取今天的日期
                today = datetime.now().strftime('%Y%m%d')

                # 单位转换
                vol_lots = row['vol'] / 100 if row['vol'] else 0
                amount_thousand = row['amount'] / 1000 if row['amount'] else 0

                print(f"{code} {today}:")
                print(f"  原始: vol={row['vol']:.0f}股, amount={row['amount']:.0f}元")
                print(f"  转换: vol={vol_lots:.0f}手 ({vol_lots/10000:.2f}万手), amount={amount_thousand:.0f}千元")

                # 保存到数据库
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO etf_daily
                    (ts_code, trade_date, open, high, low, close, vol, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    code,
                    today,
                    row['open'],
                    row['high'],
                    row['low'],
                    row['close'],
                    vol_lots,       # 已转换为"手"
                    amount_thousand  # 已转换为"千元"
                ))
                conn.commit()

                print(f"  ✅ 已保存（已转换单位）")

            except Exception as e:
                print(f"{code}: ❌ 失败 - {e}")

        conn.close()

    except Exception as e:
        print(f"❌ 实时数据下载失败: {e}")


if __name__ == '__main__':
    import sys

    print("=" * 70)
    print("ETF实时数据修复工具")
    print("=" * 70)
    print()

    if len(sys.argv) > 1 and sys.argv[1] == 'download':
        # 下载实时数据
        download_realtime_data()
    else:
        # 修复已有数据
        fix_existing_data()

    print()
    print("=" * 70)
    print("完成！")
    print("=" * 70)
