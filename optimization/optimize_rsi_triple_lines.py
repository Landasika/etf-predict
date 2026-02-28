"""
RSI三线策略参数优化脚本

使用网格搜索寻找最优的RSI三线参数组合
优化目标：最大化近一年夏普比率
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

from core.database import get_etf_daily_data
from strategies.rsi_triple_lines_backtester import RSITripleLinesBacktester


class RSITripleLinesOptimizer:
    """RSI三线策略参数优化器"""

    def __init__(self, etf_code: str):
        self.etf_code = etf_code
        self.start_date = '20200101'  # 使用更长历史数据

    def load_data(self) -> pd.DataFrame:
        """加载ETF数据"""
        data = get_etf_daily_data(self.etf_code, self.start_date)
        if not data or len(data) < 200:
            raise ValueError(f"数据不足，至少需要200天，当前有{len(data) if data else 0}天")

        df = pd.DataFrame(data)
        if 'trade_date' in df.columns:
            df = df.rename(columns={'trade_date': 'date'})
        df = df.sort_values('date').reset_index(drop=True)
        return df

    def calculate_sharpe(self, returns: pd.Series) -> float:
        """计算夏普比率"""
        if len(returns) == 0 or returns.std() == 0:
            return -999
        return np.sqrt(252) * returns.mean() / returns.std()

    def evaluate_params(self, params: Dict) -> Dict:
        """评估单组参数"""
        try:
            # 运行回测
            backtester = RSITripleLinesBacktester(
                initial_capital=2000,
                total_positions=10
            )

            result = backtester.run_backtest(
                self.etf_code,
                start_date=self.start_date,
                strategy_params=params
            )

            if not result['success']:
                return {
                    'params': params,
                    'sharpe_ratio': -999,
                    'total_return_pct': 0,
                    'max_drawdown_pct': 0,
                    'win_rate_pct': 0
                }

            metrics = result['metrics']
            return {
                'params': params,
                'sharpe_ratio': metrics.get('sharpe_ratio', -999),
                'total_return_pct': metrics.get('total_return_pct', 0),
                'max_drawdown_pct': abs(metrics.get('max_drawdown_pct', 0)),
                'win_rate_pct': metrics.get('win_rate_pct', 0),
                'total_trades': metrics.get('total_trades', 0)
            }
        except Exception as e:
            return {
                'params': params,
                'sharpe_ratio': -999,
                'total_return_pct': 0,
                'max_drawdown_pct': 0,
                'win_rate_pct': 0,
                'error': str(e)
            }

    def grid_search(self, param_grid: Dict) -> List[Dict]:
        """网格搜索最优参数"""
        results = []

        # 生成所有参数组合
        rsi1_range = param_grid['rsi1_period']
        rsi2_range = param_grid['rsi2_period']
        rsi3_range = param_grid['rsi3_period']

        total_combinations = len(rsi1_range) * len(rsi2_range) * len(rsi3_range)
        print(f"开始网格搜索，共 {total_combinations} 种参数组合...")

        count = 0
        for rsi1 in rsi1_range:
            for rsi2 in rsi2_range:
                for rsi3 in rsi3_range:
                    # 确保满足 rsi1 < rsi2 < rsi3
                    if not (rsi1 < rsi2 < rsi3):
                        continue

                    params = {
                        'rsi1_period': rsi1,
                        'rsi2_period': rsi2,
                        'rsi3_period': rsi3,
                        'rsi_overbought': 80,
                        'rsi_oversold': 20,
                        'rsi_middle': 50,
                        'slope_threshold': 0.5,
                        'slope_window': 3,
                        'line_glued_threshold': 5  # 三线黏合判断阈值
                    }

                    count += 1
                    print(f"[{count}/{total_combinations}] 测试参数: RSI1={rsi1}, RSI2={rsi2}, RSI3={rsi3}")

                    result = self.evaluate_params(params)
                    results.append(result)

        # 按夏普比率排序
        results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
        return results

    def optimize(self, n_workers: int = 4) -> Dict:
        """执行参数优化"""
        print(f"开始优化 {self.etf_code} 的RSI三线参数...")

        # 定义参数搜索空间
        param_grid = {
            'rsi1_period': range(4, 10),      # 短期RSI: 4-9
            'rsi2_period': range(8, 18),      # 中期RSI: 8-17
            'rsi3_period': range(18, 32),     # 长期RSI: 18-31
        }

        results = self.grid_search(param_grid)

        if not results:
            return {
                'success': False,
                'message': '优化失败，无有效结果'
            }

        best_result = results[0]

        # 格式化最佳参数
        best_params = best_result['params']

        return {
            'success': True,
            'etf_code': self.etf_code,
            'best_params': best_params,
            'sharpe_ratio': best_result['sharpe_ratio'],
            'total_return_pct': best_result['total_return_pct'],
            'max_drawdown_pct': best_result['max_drawdown_pct'],
            'win_rate_pct': best_result['win_rate_pct'],
            'total_trades': best_result['total_trades'],
            'all_results': results[:10]  # 返回前10个结果
        }


def save_optimized_params(etf_code: str, optimized_params: Dict):
    """保存优化后的参数到watchlist"""
    from core.watchlist import load_watchlist, save_watchlist

    watchlist = load_watchlist()

    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            etf['optimized_params'] = {
                'rsi1_period': optimized_params['rsi1_period'],
                'rsi2_period': optimized_params['rsi2_period'],
                'rsi3_period': optimized_params['rsi3_period'],
            }
            break

    save_watchlist(watchlist)
    print(f"已保存优化参数到自选列表")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='优化RSI三线策略参数')
    parser.add_argument('--etf_code', type=str, required=True, help='ETF代码，例如 510330.SH')
    parser.add_argument('--workers', type=int, default=4, help='并行进程数')

    args = parser.parse_args()

    optimizer = RSITripleLinesOptimizer(args.etf_code)

    try:
        result = optimizer.optimize(n_workers=args.workers)

        if result['success']:
            print("\n" + "="*60)
            print("优化完成！")
            print("="*60)
            print(f"ETF代码: {result['etf_code']}")
            print(f"最佳参数:")
            print(f"  RSI1(短期): {result['best_params']['rsi1_period']}")
            print(f"  RSI2(中期): {result['best_params']['rsi2_period']}")
            print(f"  RSI3(长期): {result['best_params']['rsi3_period']}")
            print(f"\n优化后指标:")
            print(f"  夏普比率: {result['sharpe_ratio']:.4f}")
            print(f"  总收益率: {result['total_return_pct']:.2f}%")
            print(f"  最大回撤: {result['max_drawdown_pct']:.2f}%")
            print(f"  胜率: {result['win_rate_pct']:.2f}%")
            print(f"  交易次数: {result['total_trades']}")

            # 保存优化参数
            save_optimized_params(args.etf_code, result['best_params'])
            print("\n参数已保存到自选列表！")
        else:
            print(f"优化失败: {result['message']}")

    except Exception as e:
        print(f"优化过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
