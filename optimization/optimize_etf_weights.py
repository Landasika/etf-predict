#!/usr/bin/env python3
"""
指定ETF代码，自动优化权重找最佳参数
"""

import sys
sys.path.append('/home/landasika/etf')

from core.database import get_etf_daily_data
import pandas as pd
from strategies.factors import FactorBuilder
from strategies.optimizer import optimize_for_short_term
from strategies.signals import MultiFactorSignalGenerator
from strategies.backtester import MultiFactorBacktester

def optimize_etf(etf_code, start_date='20200101', end_date='20231231'):
    """
    优化指定ETF的因子权重
    """

    print("=" * 70)
    print(f"开始优化 {etf_code} 的因子权重")
    print("=" * 70)

    # ==================== 1. 加载数据 ====================
    print(f"\n步骤1: 加载 {etf_code} 数据 ({start_date} - {end_date})")

    data = get_etf_daily_data(etf_code, start_date, end_date)

    if not data or len(data) == 0:
        print(f"❌ 错误: 无法加载 {etf_code} 的数据")
        return None

    df = pd.DataFrame(data)
    print(f"✅ 加载了 {len(df)} 条数据")

    # ==================== 2. 构建因子矩阵 ====================
    print("\n步骤2: 构建22个技术因子")

    builder = FactorBuilder()
    df_factors = builder.build_factor_matrix(df)

    factor_cols = [col for col in df_factors.columns if col.startswith('f_')]
    print(f"✅ 构建了 {len(factor_cols)} 个因子")

    # ==================== 3. 优化权重（核心步骤）====================
    print("\n步骤3: 使用遗传算法优化权重")
    print("⏰ 这需要 5-15 分钟，请耐心等待...")
    print("-" * 70)

    result = optimize_for_short_term(
        df=df_factors,
        holding_period=1,               # 隔夜交易（1天）
        objective='total_return',       # 最大化收益率
        method='genetic',               # 使用遗传算法
        population_size=30,             # 种群大小（可改：更快=10，更准=50）
        generations=50,                 # 迭代次数（可改：更快=20，更准=100）
        initial_capital=2000,
        commission=0.005,
        verbose=True                    # 显示优化进度
    )

    print("-" * 70)
    print("\n✅ 优化完成！")

    # ==================== 4. 显示优化结果 ====================
    print("\n" + "=" * 70)
    print("优化结果:")
    print("=" * 70)
    print(f"最佳收益率:     {result.best_fitness:6.2f}%")
    print(f"夏普比率:       {result.best_metrics['sharpe_ratio']:6.2f}")
    print(f"最大回撤:       {result.best_metrics['max_drawdown']*100:6.2f}%")
    print(f"胜率:           {result.best_metrics['win_rate']*100:6.2f}%")
    print(f"盈利因子:       {result.best_metrics['profit_factor']:6.2f}")
    print(f"交易次数:       {result.best_metrics['total_trades']}")

    # ==================== 5. 显示最优权重 ====================
    print("\n" + "=" * 70)
    print("最优因子权重（按重要性排序）:")
    print("=" * 70)

    best_weights = result.best_weights
    sorted_weights = sorted(best_weights.items(),
                           key=lambda x: abs(x[1]),
                           reverse=True)

    for i, (factor, weight) in enumerate(sorted_weights, 1):
        if abs(weight) > 0.01:  # 只显示有意义的权重
            print(f"{i:2d}. {factor:30s}: {weight:7.3f}")

    # ==================== 6. 保存权重 ====================
    import json
    import os

    weights_file = f"weights_{etf_code}.json"
    with open(weights_file, 'w') as f:
        json.dump(best_weights, f, indent=2)

    print(f"\n✅ 权重已保存到: {weights_file}")

    # ==================== 7. 用最优权重回测验证 ====================
    print("\n" + "=" * 70)
    print("步骤4: 用最优权重进行完整回测验证")
    print("=" * 70)

    signal_gen = MultiFactorSignalGenerator(weights=best_weights)
    backtester = MultiFactorBacktester(
        signal_generator=signal_gen,
        holding_period=1
    )

    backtest_result = backtester.run_backtest(
        etf_code=etf_code,
        start_date=start_date,
        end_date=end_date
    )

    metrics = backtest_result['metrics']

    print("\n完整回测结果:")
    print(f"  初始资金:    ¥{metrics['initial_capital']:,.2f}")
    print(f"  最终资金:    ¥{metrics['final_capital']:,.2f}")
    print(f"  总收益率:    {metrics['total_return_pct']:+6.2f}%")
    print(f"  夏普比率:    {metrics['sharpe_ratio']:6.2f}")
    print(f"  最大回撤:    {metrics['max_drawdown']*100:6.2f}%")
    print(f"  胜率:        {metrics['win_rate']*100:6.2f}%")
    print(f"  交易次数:    {metrics['total_trades']}")
    print(f"  平均持仓:    {metrics['avg_hold_days']:.1f}天")

    # ==================== 8. 显示最近交易 ====================
    trades = backtest_result['trades']
    if trades:
        print("\n" + "=" * 70)
        print("最近10笔交易:")
        print("=" * 70)

        trades_df = pd.DataFrame(trades)
        display_cols = ['date', 'type', 'shares', 'price', 'value', 'reason']
        if 'holding_days' in trades_df.columns:
            display_cols.append('holding_days')

        print(trades_df[display_cols].tail(10).to_string(index=False))

    print("\n" + "=" * 70)
    print(f"✅ {etf_code} 优化完成！")
    print("=" * 70)

    return {
        'etf_code': etf_code,
        'weights': best_weights,
        'optimization_result': result,
        'backtest_result': backtest_result
    }


if __name__ == '__main__':
    # ================== 在这里修改ETF代码 ==================
    ETF_CODE = '510330.SH'      # 沪深300ETF
    START_DATE = '20230101'     # 用3年数据：2023年开始
    END_DATE = '20260213'       # 到最新数据：2026年2月13日
    # =====================================================

    result = optimize_etf(ETF_CODE, START_DATE, END_DATE)
