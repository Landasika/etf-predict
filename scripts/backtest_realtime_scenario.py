"""
真实交易场景回测：盘中信号当天交易

场景说明：
1. 监控场内ETF的MACD信号
2. 盘中检测到柱衰竭信号 → 当天买入场外基金
3. 使用当天的信号，不需要偏移
4. 对比柱衰竭提前入场的实际效果
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.signals import MACDSignalGenerator
from core.database import get_etf_daily_data
import pandas as pd
import numpy as np

def backtest_realtime_trading(etf_code: str, entry_ratio: float, start_date: str = '20240101'):
    """
    真实交易场景回测（盘中信号当天交易）

    Args:
        etf_code: ETF代码
        entry_ratio: 柱衰竭比率
        start_date: 开始日期

    Returns:
        回测结果
    """
    # 获取数据
    data = get_etf_daily_data(etf_code, start_date=start_date)
    if not data or len(data) < 100:
        return None

    df = pd.DataFrame(data)

    # 生成信号
    params = MACDSignalGenerator.default_params()
    params['entry_ratio'] = entry_ratio

    generator = MACDSignalGenerator(params)
    df_signals = generator.generate_signals(df)

    # ===== 关键：不偏移信号，使用当天信号当天交易 =====
    # 这模拟了你的真实交易：盘中检测到信号，当天就买入场外基金

    # 回测逻辑
    initial_capital = 2000
    cash = initial_capital
    position_shares = 0
    avg_cost = 0
    positions_used = 0
    trades = []

    for idx, row in df_signals.iterrows():
        date = row['trade_date']
        price = row['close']
        signal_strength = row['signal_strength']
        signal_reason = row['signal_reason']

        # 卖出逻辑
        if signal_strength < 0 and position_shares > 0:
            # 全部卖出
            sell_value = position_shares * price
            cash += sell_value

            trades.append({
                'date': date,
                'type': 'SELL',
                'price': price,
                'shares': position_shares,
                'value': sell_value,
                'reason': signal_reason,
                'pnl': (price - avg_cost) * position_shares if avg_cost > 0 else 0
            })

            position_shares = 0
            avg_cost = 0
            positions_used = 0

        # 买入逻辑
        elif signal_strength > 0 and positions_used < 10:
            # 根据信号强度决定买入仓位
            if signal_strength <= 3:
                desired_positions = min(signal_strength, 2)
            elif signal_strength <= 6:
                desired_positions = signal_strength - 1
            elif signal_strength <= 9:
                desired_positions = signal_strength
            else:
                desired_positions = 10

            desired_positions = int(desired_positions)
            positions_to_add = max(0, desired_positions - positions_used)

            if positions_to_add > 0:
                position_size = initial_capital / 10
                investment = positions_to_add * position_size

                if cash >= investment and price > 0:
                    shares = int(investment // price)
                    if shares > 0:
                        cost = shares * price
                        cash -= cost

                        # 更新持仓成本
                        total_cost = avg_cost * position_shares + cost
                        position_shares += shares
                        avg_cost = total_cost / position_shares
                        positions_used += positions_to_add

                        trades.append({
                            'date': date,
                            'type': 'BUY',
                            'price': price,
                            'shares': shares,
                            'value': cost,
                            'reason': signal_reason,
                            'positions_added': positions_to_add,
                            'signal_strength': signal_strength
                        })

    # 计算最终收益
    final_date = df_signals.iloc[-1]['trade_date']
    final_price = df_signals.iloc[-1]['close']
    final_value = cash + (position_shares * final_price if position_shares > 0 else 0)
    total_return = (final_value - initial_capital) / initial_capital * 100

    # 买入持有收益
    buy_hold_return = (final_price - df_signals.iloc[0]['close']) / df_signals.iloc[0]['close'] * 100

    return {
        'trades': trades,
        'total_return': total_return,
        'buy_hold_return': buy_hold_return,
        'final_value': final_value,
        'trade_count': len(trades)
    }


def compare_strategies_realtime(etf_code: str = '510300.SH'):
    """对比不同策略在真实交易场景下的表现"""

    print("="*100)
    print(f"真实交易场景回测：{etf_code}")
    print("="*100)
    print("交易规则：盘中检测到信号 → 当天买入场外基金")
    print("="*100)

    entry_ratios = [0, 0.3, 0.5, 0.7]
    results = []

    for ratio in entry_ratios:
        strategy_name = f"MACD激进" if ratio == 0 else f"柱衰竭{int(ratio*100)}%"
        print(f"\n策略: {strategy_name} (entry_ratio={ratio})")

        result = backtest_realtime_trading(etf_code, ratio, start_date='20240101')

        if result:
            print(f"  总收益率: {result['total_return']:.2f}%")
            print(f"  买入持有: {result['buy_hold_return']:.2f}%")
            print(f"  交易次数: {result['trade_count']}")
            print(f"  超额收益: {result['total_return'] - result['buy_hold_return']:.2f}%")

            results.append({
                'strategy': strategy_name,
                'ratio': ratio,
                'return': result['total_return'],
                'buy_hold': result['buy_hold_return'],
                'trades': result['trade_count']
            })

            # 显示交易详情
            trades = result['trades']
            buys = [t for t in trades if t['type'] == 'BUY']

            if ratio > 0:
                # 统计柱衰竭信号
                exhaustion_buys = [t for t in buys if '衰竭' in t.get('reason', '')]
                print(f"  其中柱衰竭买入: {len(exhaustion_buys)}次")

                if exhaustion_buys:
                    print(f"  柱衰竭买入详情:")
                    for t in exhaustion_buys[:5]:
                        print(f"    {t['date']} 价格:{t['price']:.3f} 仓位:{t.get('positions_added',0)} {t.get('reason','')}")

    # 汇总对比
    print("\n" + "="*100)
    print("策略收益对比汇总")
    print("="*100)
    print(f"{'策略':<20} {'收益率':>12} {'买入持有':>12} {'超额收益':>12} {'交易次数':>12}")
    print("-"*100)

    for r in results:
        excess = r['return'] - r['buy_hold']
        print(f"{r['strategy']:<20} {r['return']:>11.2f}% {r['buy_hold']:>11.2f}% {excess:>11.2f}% {r['trades']:>12}")

    print("="*100)

    # 找出最优策略
    best = max(results, key=lambda x: x['return'])
    print(f"\n🏆 最优策略: {best['strategy']} - 收益率 {best['return']:.2f}%")

    return results


if __name__ == '__main__':
    # 测试多个ETF
    test_etfs = [
        ('510300.SH', '沪深300ETF'),
        ('510500.SH', '中证500ETF'),
        ('159915.SZ', '创业板ETF'),
    ]

    all_results = {}

    for etf_code, etf_name in test_etfs:
        print(f"\n\n{'='*100}")
        print(f"测试 {etf_name} ({etf_code})")
        print(f"{'='*100}")

        results = compare_strategies_realtime(etf_code)
        all_results[etf_code] = results

    # 总结
    print("\n\n" + "="*100)
    print("📊 全局总结")
    print("="*100)

    for etf_code, results in all_results.items():
        macd = [r for r in results if r['ratio'] == 0][0]
        best = max([r for r in results if r['ratio'] > 0], key=lambda x: x['return'])

        print(f"\n{etf_code}:")
        print(f"  MACD激进: {macd['return']:.2f}%")
        print(f"  最优柱衰竭: {best['strategy']} {best['return']:.2f}%")
        print(f"  提升: {best['return'] - macd['return']:.2f}%")
