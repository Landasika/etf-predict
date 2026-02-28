#!/usr/bin/env python3
"""
包装脚本：运行MACD+KDJ离散策略参数优化

使用方法:
    python run_optimize_macd_kdj_discrete.py <ETF代码> [回溯天数] [是否优化KDJ: 1/0]

示例:
    python run_optimize_macd_kdj_discrete.py 159300.SZ 365 1
"""

import sys
import os

# 确保项目根目录在Python路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategies.macd_kdj_discrete_param_optimizer import optimize_macd_kdj_discrete_params

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python run_optimize_macd_kdj_discrete.py <ETF代码> [回溯天数] [是否优化KDJ: 1/0]")
        print("示例: python run_optimize_macd_kdj_discrete.py 159300.SZ 365 1")
        print()
        print("参数说明:")
        print("  ETF代码:     如 159300.SZ 或 510330.SH")
        print("  回溯天数:     优化使用的天数，默认365天")
        print("  是否优化KDJ:  1=优化MACD+KDJ参数(默认), 0=只优化MACD参数")
        sys.exit(1)

    etf_code = sys.argv[1]
    lookback_days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    optimize_kdj = True if len(sys.argv) <= 3 or sys.argv[3] == '1' else False

    print(f"开始优化 {etf_code} 的MACD+KDJ离散参数（回溯 {lookback_days} 天，优化KDJ: {optimize_kdj}）")
    print("=" * 60)

    try:
        result = optimize_macd_kdj_discrete_params(etf_code, lookback_days, optimize_kdj)

        print("\n" + "=" * 60)
        print("优化完成！")
        print(f"最优MACD参数:")
        print(f"  - Fast:   {result['best_params']['macd_fast']}")
        print(f"  - Slow:   {result['best_params']['macd_slow']}")
        print(f"  - Signal: {result['best_params']['macd_signal']}")
        if optimize_kdj:
            print(f"最优KDJ参数:")
            print(f"  - N:      {result['best_params']['kdj_n']}")
            print(f"  - M1:     {result['best_params']['kdj_m1']}")
            print(f"  - M2:     {result['best_params']['kdj_m2']}")
        print(f"\n性能指标:")
        print(f"  - 收益率:    {result['metrics']['total_return_pct']:.2f}%")
        print(f"  - 夏普比率:  {result['metrics']['sharpe_ratio']:.2f}")
        print(f"  - 最大回撤:  {result['metrics']['max_drawdown_pct']:.2f}%")
        print(f"  - 胜率:      {result['metrics']['win_rate_pct']:.2f}%")
        print(f"  - 交易次数:  {result['metrics']['total_trades']}")
        print(f"\n数据期间: {result['data_period']['start']} 至 {result['data_period']['end']}")
        print(f"数据天数: {result['data_period']['days']} 天")
    except Exception as e:
        print(f"\n优化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
