"""
深度分析：柱衰竭策略为什么没能提前入场？

对比MACD激进和柱衰竭策略的实际入场时间
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.backtester import MACDBacktester
from strategies.signals import MACDSignalGenerator
import pandas as pd

def analyze_entry_timing(etf_code: str = '510300.SH'):
    """分析两种策略的入场时间差异"""

    # 策略1：MACD激进（无柱衰竭）
    print("="*100)
    print("策略1：MACD激进（entry_ratio=0，等待金叉）")
    print("="*100)

    strategy_params_0 = MACDSignalGenerator.default_params()
    strategy_params_0['entry_ratio'] = 0

    backtester = MACDBacktester(initial_capital=2000, num_positions=10)
    result_0 = backtester.run_backtest(etf_code, strategy_params_0, start_date='20240101')

    trades_0 = result_0['trades']
    buys_0 = [t for t in trades_0 if t['type'] == 'BUY']

    print(f"\n买入次数: {len(buys_0)}")
    print("\n买入记录:")
    for i, t in enumerate(buys_0, 1):
        print(f"{i}. {t['date']} 价格:{t['price']:.3f} 仓位:{t.get('positions_added', 0)}")

    # 策略2：柱衰竭50%
    print("\n" + "="*100)
    print("策略2：MACD激进+柱衰竭50%（entry_ratio=0.5，提前入场）")
    print("="*100)

    strategy_params_50 = MACDSignalGenerator.default_params()
    strategy_params_50['entry_ratio'] = 0.5

    result_50 = backtester.run_backtest(etf_code, strategy_params_50, start_date='20240101')

    trades_50 = result_50['trades']
    buys_50 = [t for t in trades_50 if t['type'] == 'BUY']

    print(f"\n买入次数: {len(buys_50)}")
    print("\n买入记录:")
    for i, t in enumerate(buys_50, 1):
        reason = t.get('reason', '')
        print(f"{i}. {t['date']} 价格:{t['price']:.3f} 仓位:{t.get('positions_added', 0)} 原因:{reason}")

    # 对比分析
    print("\n" + "="*100)
    print("提前入场分析")
    print("="*100)

    # 找出柱衰竭信号
    exhaustion_buys = [t for t in buys_50 if '衰竭' in t.get('reason', '')]
    crossover_buys = [t for t in buys_50 if 'SIGNAL' in t.get('reason', '') or '金叉' in t.get('reason', '')]

    print(f"\n柱衰竭提前买入: {len(exhaustion_buys)}次")
    print(f"标准金叉买入: {len(crossover_buys)}次")
    print(f"总买入次数: {len(buys_50)}次")

    if exhaustion_buys:
        print("\n柱衰竭买入详情:")
        for t in exhaustion_buys:
            print(f"  {t['date']} 价格:{t['price']:.3f}")

    # 计算提前天数
    print("\n" + "="*100)
    print("提前入场效果分析")
    print("="*100)

    # 对比同期的价格变化
    from core.database import get_etf_daily_data
    data = get_etf_daily_data(etf_code, start_date='20240101')
    df = pd.DataFrame(data)
    df['trade_date'] = df['trade_date'].astype(str)

    for buy_0 in buys_0[:5]:  # 分析前5次买入
        date_0 = str(buy_0['date'])
        price_0 = buy_0['price']

        # 查找是否有对应的柱衰竭提前买入
        # 在金叉前10天内的柱衰竭信号
        idx_0 = df[df['trade_date'] == date_0].index
        if len(idx_0) > 0:
            idx_0 = idx_0[0]
            # 前10天的数据
            window = df.iloc[max(0, idx_0-10):idx_0+1]

            print(f"\n金叉买入: {date_0} 价格:{price_0:.3f}")

            # 查看这个窗口内是否有柱衰竭买入
            found_early = False
            for buy_50 in exhaustion_buys:
                date_50 = str(buy_50['date'])
                if date_50 in window['trade_date'].values:
                    price_50 = buy_50['price']
                    days_early = idx_0 - window[window['trade_date'] == date_50].index[0]
                    price_diff = (price_0 - price_50) / price_50 * 100
                    print(f"  → 柱衰竭提前: {date_50} 价格:{price_50:.3f}")
                    print(f"     提前{days_early}天，价格优势:{price_diff:+.2f}%")
                    found_early = True

            if not found_early:
                print(f"  → 没有柱衰竭提前信号")

    # 收益对比
    print("\n" + "="*100)
    print("收益对比")
    print("="*100)

    metrics_0 = result_0['metrics']
    metrics_50 = result_50['metrics']

    print(f"MACD激进收益: {metrics_0['total_return']:.2f}%")
    print(f"柱衰竭50%收益: {metrics_50['total_return']:.2f}%")
    print(f"收益差距: {metrics_50['total_return'] - metrics_0['total_return']:.2f}%")

    print(f"\nMACD激进交易次数: {len(trades_0)}")
    print(f"柱衰竭50%交易次数: {len(trades_50)}")
    print(f"交易增加: {len(trades_50) - len(trades_0)}次 (+{(len(trades_50) - len(trades_0)) / len(trades_0) * 100:.1f}%)")

    # 持仓率对比
    performance_0 = result_0['performance']
    performance_50 = result_50['performance']

    df_0 = pd.DataFrame(performance_0)
    df_50 = pd.DataFrame(performance_50)

    hold_rate_0 = (df_0['positions_used'] > 0).sum() / len(df_0) * 100
    hold_rate_50 = (df_50['positions_used'] > 0).sum() / len(df_50) * 100

    print(f"\nMACD激进持仓率: {hold_rate_0:.1f}%")
    print(f"柱衰竭50%持仓率: {hold_rate_50:.1f}%")
    print(f"持仓率提升: {hold_rate_50 - hold_rate_0:.1f}%")


if __name__ == '__main__':
    analyze_entry_timing('510300.SH')
