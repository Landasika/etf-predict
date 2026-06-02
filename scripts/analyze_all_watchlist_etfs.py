"""
批量回测：所有自选ETF的柱衰竭策略效果

对比MACD激进 vs 柱衰竭30%/50%/70%
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from strategies.signals import MACDSignalGenerator
from core.database import get_etf_daily_data
import pandas as pd
import numpy as np

def calculate_volatility(etf_code: str, start_date: str = '20240101'):
    """计算ETF的年化波动率"""
    data = get_etf_daily_data(etf_code, start_date=start_date)
    if not data or len(data) < 50:
        return None

    df = pd.DataFrame(data)
    df['returns'] = df['close'].pct_change()
    daily_vol = df['returns'].std()
    annual_vol = daily_vol * np.sqrt(252)
    return annual_vol

def backtest_simple(etf_code: str, entry_ratio: float, start_date: str = '20240101'):
    """简化版回测（真实交易场景）"""
    data = get_etf_daily_data(etf_code, start_date=start_date)
    if not data or len(data) < 100:
        return None

    df = pd.DataFrame(data)

    # 生成信号
    params = MACDSignalGenerator.default_params()
    params['entry_ratio'] = entry_ratio
    generator = MACDSignalGenerator(params)
    df_signals = generator.generate_signals(df)

    # 简单回测
    initial_capital = 2000
    cash = initial_capital
    position_shares = 0
    avg_cost = 0

    for idx, row in df_signals.iterrows():
        price = row['close']
        signal_strength = row['signal_strength']

        # 卖出
        if signal_strength < 0 and position_shares > 0:
            cash += position_shares * price
            position_shares = 0
            avg_cost = 0

        # 买入
        elif signal_strength > 0 and position_shares == 0:
            # 简化：买入50%资金
            investment = cash * 0.5
            if investment > 0 and price > 0:
                shares = int(investment // price)
                if shares > 0:
                    cost = shares * price
                    cash -= cost
                    position_shares = shares
                    avg_cost = price

    # 计算最终收益
    final_price = df_signals.iloc[-1]['close']
    final_value = cash + (position_shares * final_price if position_shares > 0 else 0)
    total_return = (final_value - initial_capital) / initial_capital * 100

    # 买入持有收益
    buy_hold = (final_price - df_signals.iloc[0]['close']) / df_signals.iloc[0]['close'] * 100

    return {
        'return': total_return,
        'buy_hold': buy_hold,
        'days': len(df_signals)
    }

def analyze_all_etfs():
    """分析所有自选ETF"""

    # 读取自选列表
    watchlist_file = Path('data/watchlist_etfs.json')
    if not watchlist_file.exists():
        print('未找到自选列表')
        return

    with open(watchlist_file) as f:
        data = json.load(f)

    etfs = data.get('etfs', [])

    print("="*120)
    print(f"批量回测分析：{len(etfs)}个自选ETF")
    print("="*120)
    print("回测期间：2024-01-01 至今")
    print("对比策略：MACD激进 vs 柱衰竭30%/50%/70%")
    print("="*120)

    results = []

    for i, etf in enumerate(etfs, 1):
        code = etf['code']
        name = etf.get('name', code)

        print(f"\n[{i}/{len(etfs)}] {name} ({code})")

        # 计算波动率
        volatility = calculate_volatility(code)
        if volatility is None:
            print(f"  ⚠️  数据不足，跳过")
            continue

        print(f"  年化波动率: {volatility*100:.2f}%")

        # 回测各策略
        r0 = backtest_simple(code, 0)
        r3 = backtest_simple(code, 0.3)
        r5 = backtest_simple(code, 0.5)
        r7 = backtest_simple(code, 0.7)

        if not all([r0, r3, r5, r7]):
            print(f"  ⚠️  回测失败，跳过")
            continue

        print(f"  MACD激进:  {r0['return']:>7.2f}% (买入持有:{r0['buy_hold']:>7.2f}%)")
        print(f"  柱衰竭30%: {r3['return']:>7.2f}%")
        print(f"  柱衰竭50%: {r5['return']:>7.2f}%")
        print(f"  柱衰竭70%: {r7['return']:>7.2f}%")

        # 找出最优策略
        returns = [
            ('MACD激进', r0['return']),
            ('柱衰竭30%', r3['return']),
            ('柱衰竭50%', r5['return']),
            ('柱衰竭70%', r7['return'])
        ]
        best = max(returns, key=lambda x: x[1])
        improvement = best[1] - r0['return']

        print(f"  🏆 最优: {best[0]} {best[1]:.2f}% (提升:{improvement:+.2f}%)")

        results.append({
            'code': code,
            'name': name,
            'volatility': volatility * 100,
            'buy_hold': r0['buy_hold'],
            'macd': r0['return'],
            'hist_30': r3['return'],
            'hist_50': r5['return'],
            'hist_70': r7['return'],
            'best_strategy': best[0],
            'best_return': best[1],
            'improvement': improvement
        })

    # 汇总分析
    print("\n\n" + "="*120)
    print("📊 汇总分析")
    print("="*120)

    df = pd.DataFrame(results)

    # 按改善幅度排序
    df_sorted = df.sort_values('improvement', ascending=False)

    print("\n【TOP 10 - 柱衰竭改善最大的ETF】")
    print("-"*120)
    print(f"{'排名':<4} {'ETF':<20} {'波动率':>8} {'MACD':>8} {'最优策略':<12} {'最优收益':>8} {'提升':>8}")
    print("-"*120)

    for i, row in df_sorted.head(10).iterrows():
        print(f"{df_sorted.index.get_loc(i)+1:<4} {row['name'][:18]:<20} "
              f"{row['volatility']:>7.1f}% {row['macd']:>7.2f}% "
              f"{row['best_strategy']:<12} {row['best_return']:>7.2f}% "
              f"{row['improvement']:>+7.2f}%")

    print("\n【BOTTOM 10 - 柱衰竭表现最差的ETF】")
    print("-"*120)

    for i, row in df_sorted.tail(10).iterrows():
        print(f"{df_sorted.index.get_loc(i)+1:<4} {row['name'][:18]:<20} "
              f"{row['volatility']:>7.1f}% {row['macd']:>7.2f}% "
              f"{row['best_strategy']:<12} {row['best_return']:>7.2f}% "
              f"{row['improvement']:>+7.2f}%")

    # 按波动率分组统计
    print("\n\n【按波动率分组统计】")
    print("-"*120)

    df['vol_group'] = pd.cut(df['volatility'], bins=[0, 20, 30, 100],
                             labels=['低波动(<20%)', '中波动(20-30%)', '高波动(>30%)'])

    grouped = df.groupby('vol_group').agg({
        'improvement': 'mean',
        'macd': 'mean',
        'best_return': 'mean',
        'name': 'count'
    }).round(2)

    print(f"{'波动率组':<20} {'数量':>6} {'MACD平均':>12} {'最优平均':>12} {'平均提升':>12}")
    print("-"*120)
    for group, row in grouped.iterrows():
        print(f"{group:<20} {int(row['name']):>6} "
              f"{row['macd']:>11.2f}% {row['best_return']:>11.2f}% "
              f"{row['improvement']:>+11.2f}%")

    # 策略推荐统计
    print("\n\n【最优策略分布】")
    print("-"*120)
    strategy_counts = df['best_strategy'].value_counts()
    total = len(df)

    for strategy, count in strategy_counts.items():
        pct = count / total * 100
        print(f"{strategy:<15} {count:>3}个 ({pct:>5.1f}%)")

    # 保存结果
    output_file = 'all_etfs_histogram_analysis.csv'
    df_sorted.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 详细结果已保存到: {output_file}")

    return df

if __name__ == '__main__':
    analyze_all_etfs()
