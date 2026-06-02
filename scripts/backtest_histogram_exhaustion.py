"""
回测对比：MACD激进 vs MACD激进+柱衰竭提前入场

对比三种配置：
1. MACD激进（entry_ratio=0，不启用柱衰竭）
2. MACD激进+柱衰竭 entry_ratio=0.3
3. MACD激进+柱衰竭 entry_ratio=0.5
4. MACD激进+柱衰竭 entry_ratio=0.7
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from typing import Dict, List
from core.database import get_etf_daily_data, get_etf_info
from strategies.backtester import MACDBacktester
from strategies.signals import MACDSignalGenerator
import config

def backtest_single_etf(etf_code: str, entry_ratio: float, start_date: str = '20240101') -> Dict:
    """回测单个ETF

    Args:
        etf_code: ETF代码
        entry_ratio: 柱衰竭比率（0=关闭）
        start_date: 开始日期

    Returns:
        回测结果字典
    """
    # 使用默认参数，只修改 entry_ratio
    strategy_params = MACDSignalGenerator.default_params()
    strategy_params['entry_ratio'] = entry_ratio

    # 回测参数
    backtest_params = {
        'initial_capital': 2000,
        'num_positions': 10,
        'stop_loss_pct': 0.10,
        'take_profit_pct1': 0.15,
        'take_profit_pct2': 0.30,
        'take_profit_pct3': 0.35
    }

    # 运行回测
    backtester = MACDBacktester(**backtest_params)
    result = backtester.run_backtest(etf_code, strategy_params, start_date=start_date)

    return result


def compare_strategies(etf_codes: List[str], start_date: str = '20240101') -> pd.DataFrame:
    """对比多个ETF在不同entry_ratio下的表现

    Args:
        etf_codes: ETF代码列表
        start_date: 开始日期

    Returns:
        对比结果DataFrame
    """
    entry_ratios = [0, 0.3, 0.5, 0.7]
    results = []

    for etf_code in etf_codes:
        etf_info = get_etf_info(etf_code)
        etf_name = etf_info.get('name', etf_code) if etf_info else etf_code

        print(f"\n{'='*60}")
        print(f"回测 {etf_name} ({etf_code})")
        print(f"{'='*60}")

        etf_results = {
            'etf_code': etf_code,
            'etf_name': etf_name
        }

        for entry_ratio in entry_ratios:
            strategy_name = f"MACD激进" if entry_ratio == 0 else f"柱衰竭{int(entry_ratio*100)}%"
            print(f"\n策略: {strategy_name} (entry_ratio={entry_ratio})")

            result = backtest_single_etf(etf_code, entry_ratio, start_date)

            if result:
                metrics = result['metrics']
                total_return = metrics.get('total_return', 0)
                sharpe = metrics.get('sharpe_ratio', 0)
                max_dd = metrics.get('max_drawdown', 0)
                win_rate = metrics.get('win_rate', 0)
                total_trades = metrics.get('total_trades', 0)

                print(f"  总收益率: {total_return:.2f}%")
                print(f"  夏普比率: {sharpe:.2f}")
                print(f"  最大回撤: {max_dd:.2f}%")
                print(f"  胜率: {win_rate:.1f}%")
                print(f"  交易次数: {total_trades}")

                etf_results[f'return_{entry_ratio}'] = total_return
                etf_results[f'sharpe_{entry_ratio}'] = sharpe
                etf_results[f'max_dd_{entry_ratio}'] = max_dd
                etf_results[f'win_rate_{entry_ratio}'] = win_rate
                etf_results[f'trades_{entry_ratio}'] = total_trades
            else:
                print(f"  ⚠️  数据不足，跳过")
                etf_results[f'return_{entry_ratio}'] = None

        results.append(etf_results)

    return pd.DataFrame(results)


def print_comparison_table(df: pd.DataFrame):
    """打印对比表格"""
    print("\n" + "="*100)
    print("📊 回测结果对比汇总")
    print("="*100)

    print("\n【收益率对比】")
    print("-" * 100)
    print(f"{'ETF名称':<20} {'MACD激进':>12} {'柱衰竭30%':>12} {'柱衰竭50%':>12} {'柱衰竭70%':>12} {'最优策略':>15}")
    print("-" * 100)

    for _, row in df.iterrows():
        name = row['etf_name'][:18]
        r0 = row.get('return_0')
        r3 = row.get('return_0.3')
        r5 = row.get('return_0.5')
        r7 = row.get('return_0.7')

        returns = [
            ('MACD激进', r0),
            ('柱衰竭30%', r3),
            ('柱衰竭50%', r5),
            ('柱衰竭70%', r7)
        ]

        # 找出最优策略
        valid_returns = [(n, r) for n, r in returns if r is not None]
        if valid_returns:
            best = max(valid_returns, key=lambda x: x[1])
            best_name = best[0]
        else:
            best_name = 'N/A'

        print(f"{name:<20} "
              f"{r0 if r0 else 'N/A':>12} "
              f"{r3 if r3 else 'N/A':>12} "
              f"{r5 if r5 else 'N/A':>12} "
              f"{r7 if r7 else 'N/A':>12} "
              f"{best_name:>15}")

    print("-" * 100)

    # 计算平均表现
    print("\n【平均表现】")
    print("-" * 100)
    avg_r0 = df['return_0'].mean()
    avg_r3 = df['return_0.3'].mean()
    avg_r5 = df['return_0.5'].mean()
    avg_r7 = df['return_0.7'].mean()

    print(f"{'平均收益率':<20} "
          f"{avg_r0:>12.2f} "
          f"{avg_r3:>12.2f} "
          f"{avg_r5:>12.2f} "
          f"{avg_r7:>12.2f}")

    # 夏普比率
    avg_s0 = df['sharpe_0'].mean()
    avg_s3 = df['sharpe_0.3'].mean()
    avg_s5 = df['sharpe_0.5'].mean()
    avg_s7 = df['sharpe_0.7'].mean()

    print(f"{'平均夏普比率':<20} "
          f"{avg_s0:>12.2f} "
          f"{avg_s3:>12.2f} "
          f"{avg_s5:>12.2f} "
          f"{avg_s7:>12.2f}")

    # 最大回撤
    avg_dd0 = df['max_dd_0'].mean()
    avg_dd3 = df['max_dd_0.3'].mean()
    avg_dd5 = df['max_dd_0.5'].mean()
    avg_dd7 = df['max_dd_0.7'].mean()

    print(f"{'平均最大回撤':<20} "
          f"{avg_dd0:>12.2f} "
          f"{avg_dd3:>12.2f} "
          f"{avg_dd5:>12.2f} "
          f"{avg_dd7:>12.2f}")

    print("-" * 100)

    # 统计最优策略分布
    print("\n【最优策略分布】")
    print("-" * 100)
    best_counts = {
        'MACD激进': 0,
        '柱衰竭30%': 0,
        '柱衰竭50%': 0,
        '柱衰竭70%': 0
    }

    for _, row in df.iterrows():
        returns = [
            ('MACD激进', row.get('return_0')),
            ('柱衰竭30%', row.get('return_0.3')),
            ('柱衰竭50%', row.get('return_0.5')),
            ('柱衰竭70%', row.get('return_0.7'))
        ]
        valid_returns = [(n, r) for n, r in returns if r is not None]
        if valid_returns:
            best = max(valid_returns, key=lambda x: x[1])
            best_counts[best[0]] += 1

    total = sum(best_counts.values())
    for strategy, count in best_counts.items():
        pct = count / total * 100 if total > 0 else 0
        print(f"{strategy:<15} {count:>3} 次 ({pct:>5.1f}%)")

    print("-" * 100)


if __name__ == '__main__':
    # 选择要回测的ETF列表（从自选列表或配置中选择）
    test_etfs = [
        '510300.SH',  # 沪深300ETF
        '510500.SH',  # 中证500ETF
        '159915.SZ',  # 创业板ETF
        '512170.SH',  # 医药ETF
        '512760.SH',  # 芯片ETF
        '159949.SZ',  # 创业板50
        '515050.SH',  # 5G ETF
        '512480.SH',  # 半导体ETF
    ]

    print("="*100)
    print("🔬 MACD激进 vs MACD激进+柱衰竭提前入场 策略回测对比")
    print("="*100)
    print(f"回测期间: 2024-01-01 至今")
    print(f"初始资金: 2000元")
    print(f"最大仓位: 10成")
    print(f"止损: 10%, 止盈: 15%")
    print("="*100)

    # 运行回测
    results_df = compare_strategies(test_etfs, start_date='20240101')

    # 打印对比表格
    print_comparison_table(results_df)

    # 保存结果
    output_file = 'backtest_histogram_exhaustion_results.csv'
    results_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n✅ 详细结果已保存到: {output_file}")
