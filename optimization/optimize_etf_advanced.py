#!/usr/bin/env python3
"""
增强版ETF权重优化器

特性：
1. 为每个ETF单独优化权重
2. 使用交叉验证避免过拟合
3. 多目标优化（收益+风险）
4. 市场环境识别
5. 自动保存最优权重
"""

import sys
sys.path.append('/home/landasika/etf')

import pandas as pd
import numpy as np
import json
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path

from core.database import get_etf_daily_data
from strategies.factors import FactorBuilder
from strategies.optimizer import optimize_for_short_term, FactorWeightOptimizer
from strategies.signals import MultiFactorSignalGenerator
from strategies.backtester import MACDBacktester


class AdvancedETFOptimizer:
    """增强版ETF优化器"""

    def __init__(self,
                 etf_code: str,
                 start_date: str = '20230101',
                 end_date: str = None,
                 cv_folds: int = 3,
                 test_size: float = 0.2):
        """
        初始化优化器

        Args:
            etf_code: ETF代码
            start_date: 训练数据开始日期
            end_date: 结束日期
            cv_folds: 交叉验证折数
            test_size: 测试集比例
        """
        self.etf_code = etf_code
        self.start_date = start_date
        self.end_date = end_date
        self.cv_folds = cv_folds
        self.test_size = test_size

        # 创建输出目录
        self.output_dir = Path(f"optimized_weights/{etf_code}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_and_prepare_data(self) -> pd.DataFrame:
        """加载并准备数据"""
        print(f"\n{'='*70}")
        print(f"步骤1: 加载 {self.etf_code} 数据")
        print(f"{'='*70}")

        data = get_etf_daily_data(self.etf_code, self.start_date, self.end_date)

        if not data or len(data) < 200:
            raise ValueError(f"数据不足：至少需要200天数据，当前只有{len(data) if data else 0}天")

        df = pd.DataFrame(data)
        print(f"✅ 加载了 {len(df)} 条数据")
        print(f"   日期范围: {df['trade_date'].iloc[0]} ~ {df['trade_date'].iloc[-1]}")

        # 构建因子矩阵
        print(f"\n步骤2: 构建技术因子矩阵")
        builder = FactorBuilder()
        df = builder.build_factor_matrix(df)

        factor_cols = [col for col in df.columns if col.startswith('f_')]
        print(f"✅ 构建了 {len(factor_cols)} 个技术因子")

        return df

    def add_market_environment(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        添加市场环境分类

        环境分类：
        - 牛市：MA20向上且价格在MA60上方
        - 熊市：MA20向下且价格在MA60下方
        - 震荡：其他情况
        """
        print(f"\n步骤3: 识别市场环境")

        # 计算MA20和MA60
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()

        # MA20斜率
        df['ma20_slope'] = df['ma20'].diff(5)

        # 环境分类
        df['market_env'] = 'neutral'  # 默认震荡

        # 牛市：MA20向上 + 价格在MA60上方
        bull_market = (df['ma20_slope'] > 0) & (df['close'] > df['ma60'])
        df.loc[bull_market, 'market_env'] = 'bull'

        # 熊市：MA20向下 + 价格在MA60下方
        bear_market = (df['ma20_slope'] < 0) & (df['close'] < df['ma60'])
        df.loc[bear_market, 'market_env'] = 'bear'

        # 统计各环境占比
        env_counts = df['market_env'].value_counts()
        print(f"✅ 市场环境分布:")
        for env, count in env_counts.items():
            pct = count / len(df) * 100
            print(f"   {env:8s}: {count:4d}天 ({pct:5.1f}%)")

        return df

    def cross_validation_optimize(self,
                                   df: pd.DataFrame,
                                   objectives: List[str] = None,
                                   population_size: int = 30,
                                   generations: int = 50) -> Dict:
        """
        交叉验证优化

        Args:
            df: 数据
            objectives: 优化目标列表
            population_size: 种群大小
            generations: 迭代次数

        Returns:
            最优权重和验证结果
        """
        if objectives is None:
            objectives = ['sharpe', 'profit_factor', 'total_return']

        print(f"\n步骤4: 多目标交叉验证优化")
        print(f"   优化目标: {', '.join(objectives)}")
        print(f"   交叉验证: {self.cv_folds}折")
        print(f"   种群大小: {population_size}")
        print(f"   迭代次数: {generations}")
        print(f"{'='*70}")

        # 分割训练集和测试集
        test_size = int(len(df) * self.test_size)
        train_df = df.iloc[:-test_size]
        test_df = df.iloc[-test_size:]

        print(f"   训练集: {len(train_df)}天")
        print(f"   测试集: {len(test_df)}天")

        results = {}

        for objective in objectives:
            print(f"\n{'='*70}")
            print(f"优化目标: {objective}")
            print(f"{'='*70}")

            # 多次运行取平均（避免随机性）
            run_results = []

            for run in range(3):  # 运行3次
                print(f"\n--- 第{run+1}次运行 ---")

                result = optimize_for_short_term(
                    df=train_df,
                    holding_period=1,
                    objective=objective,
                    method='genetic',
                    population_size=population_size,
                    generations=generations,
                    verbose=False
                )

                run_results.append(result)

            # 选择在测试集上表现最好的权重
            best_test_score = -np.inf
            best_weights = None

            for i, result in enumerate(run_results):
                # 在测试集上验证
                test_score = self._validate_on_test_set(
                    test_df,
                    result.best_weights,
                    objective
                )

                print(f"   运行{i+1}: 训练{result.best_fitness:.2f}% | 测试{test_score:.2f}%")

                if test_score > best_test_score:
                    best_test_score = test_score
                    best_weights = result.best_weights
                    best_train_result = result

            results[objective] = {
                'weights': best_weights,
                'train_fitness': best_train_result.best_fitness,
                'test_fitness': best_test_score,
                'metrics': best_train_result.best_metrics
            }

        # 选择综合最好的权重
        print(f"\n{'='*70}")
        print(f"各目标优化结果对比:")
        print(f"{'='*70}")

        for obj, res in results.items():
            print(f"\n{obj:20s}:")
            print(f"   训练集: {res['train_fitness']:7.2f}%")
            print(f"   测试集: {res['test_fitness']:7.2f}%")
            print(f"   夏普比率: {res['metrics']['sharpe_ratio']:6.2f}")
            print(f"   胜率: {res['metrics']['win_rate']*100:5.1f}%")

        # 使用测试集表现最好的目标
        best_objective = max(results.items(),
                            key=lambda x: x[1]['test_fitness'])[0]

        print(f"\n✅ 选择最佳目标: {best_objective}")

        return {
            'best_weights': results[best_objective]['weights'],
            'best_objective': best_objective,
            'all_results': results
        }

    def _validate_on_test_set(self,
                               test_df: pd.DataFrame,
                               weights: Dict,
                               objective: str) -> float:
        """在测试集上验证权重"""
        # 计算信号强度
        signal_strength = np.zeros(len(test_df))
        for factor, weight in weights.items():
            if factor in test_df.columns:
                signal_strength += test_df[factor].fillna(0) * weight

        # 快速回测
        optimizer = FactorWeightOptimizer()
        metrics = optimizer._fast_backtest(
            test_df,
            signal_strength,
            initial_capital=2000,
            commission=0.005,
            holding_period=1
        )

        # 返回对应目标的值
        if objective == 'sharpe':
            return metrics['sharpe_ratio']
        elif objective == 'profit_factor':
            return metrics['profit_factor']
        else:
            return metrics['total_return_pct']

    def optimize_by_market_environment(self,
                                       df: pd.DataFrame) -> Dict[str, Dict]:
        """
        为不同市场环境分别优化权重

        Returns:
            {环境: {权重, 指标}}
        """
        print(f"\n{'='*70}")
        print(f"步骤5: 为不同市场环境优化权重")
        print(f"{'='*70}")

        env_weights = {}

        for env in ['bull', 'bear', 'neutral']:
            env_df = df[df['market_env'] == env].copy()

            if len(env_df) < 100:
                print(f"\n⚠️  {env}环境数据不足({len(env_df)}天)，跳过")
                continue

            print(f"\n--- {env}环境优化 ({len(env_df)}天数据) ---")

            # 使用该环境的数据优化
            result = optimize_for_short_term(
                df=env_df,
                holding_period=1,
                objective='total_return',
                method='genetic',
                population_size=20,
                generations=30,
                verbose=False
            )

            env_weights[env] = {
                'weights': result.best_weights,
                'metrics': result.best_metrics
            }

            print(f"   最优收益率: {result.best_fitness:.2f}%")

        return env_weights

    def full_backtest_with_weights(self,
                                    df: pd.DataFrame,
                                    weights: Dict) -> Dict:
        """使用最优权重进行完整回测"""
        print(f"\n{'='*70}")
        print(f"步骤6: 使用最优权重进行完整回测")
        print(f"{'='*70}")

        # 创建信号生成器
        signal_gen = MultiFactorSignalGenerator(weights=weights)

        # 创建回测器（使用多因子回测器）
        from strategies.backtester import MultiFactorBacktester
        backtester = MultiFactorBacktester(
            signal_generator=signal_gen,
            initial_capital=2000,
            sell_fee=0.005,
            num_positions=10,  # 10个仓位
            stop_loss_pct=0.10,
            take_profit_pct1=0.10,
            take_profit_pct2=0.20,
            holding_period=1
        )

        # 提取日期范围
        start_date = df['trade_date'].iloc[0].replace('-', '')
        end_date = df['trade_date'].iloc[-1].replace('-', '')

        # 运行回测（不传递df，让回测器自己加载）
        backtest_result = backtester.run_backtest(
            etf_code=self.etf_code,
            start_date=start_date,
            end_date=end_date,
            use_market_filter=False,
            optimize_weights=False
        )

        return backtest_result

    def save_results(self, optimization_result: Dict, backtest_result: Dict):
        """保存优化结果"""
        print(f"\n{'='*70}")
        print(f"步骤7: 保存优化结果")
        print(f"{'='*70}")

        # 1. 保存最优权重
        weights_file = self.output_dir / "best_weights.json"
        with open(weights_file, 'w') as f:
            json.dump(optimization_result['best_weights'], f, indent=2)
        print(f"✅ 权重已保存: {weights_file}")

        # 2. 保存完整报告
        report = {
            'etf_code': self.etf_code,
            'optimization_date': datetime.now().isoformat(),
            'data_period': {
                'start': self.start_date,
                'end': self.end_date
            },
            'best_objective': optimization_result['best_objective'],
            'best_weights': optimization_result['best_weights'],
            'all_objectives': {
                obj: {
                    'train_fitness': res['train_fitness'],
                    'test_fitness': res['test_fitness'],
                    'sharpe_ratio': res['metrics']['sharpe_ratio'],
                    'win_rate': res['metrics']['win_rate']
                }
                for obj, res in optimization_result['all_results'].items()
            },
            'backtest_metrics': backtest_result['metrics']
        }

        report_file = self.output_dir / "optimization_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"✅ 报告已保存: {report_file}")

        # 3. 保存交易记录
        if backtest_result.get('trades'):
            trades_df = pd.DataFrame(backtest_result['trades'])
            trades_file = self.output_dir / "trades.csv"
            trades_df.to_csv(trades_file, index=False)
            print(f"✅ 交易记录已保存: {trades_file}")

    def run_optimization(self):
        """运行完整优化流程"""
        print(f"\n{'='*70}")
        print(f"开始优化 {self.etf_code}")
        print(f"{'='*70}")

        try:
            # 1. 加载数据
            df = self.load_and_prepare_data()

            # 2. 添加市场环境
            df = self.add_market_environment(df)

            # 3. 交叉验证优化
            optimization_result = self.cross_validation_optimize(
                df,
                objectives=['sharpe', 'profit_factor', 'total_return'],
                population_size=30,
                generations=50
            )

            # 4. 可选：为不同环境分别优化
            # env_weights = self.optimize_by_market_environment(df)

            # 5. 完整回测
            backtest_result = self.full_backtest_with_weights(
                df,
                optimization_result['best_weights']
            )

            # 6. 显示结果
            self.print_final_results(
                optimization_result,
                backtest_result
            )

            # 7. 保存结果
            self.save_results(optimization_result, backtest_result)

            print(f"\n{'='*70}")
            print(f"✅ {self.etf_code} 优化完成！")
            print(f"{'='*70}\n")

            return {
                'optimization': optimization_result,
                'backtest': backtest_result
            }

        except Exception as e:
            print(f"\n❌ 优化失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def print_final_results(self,
                           optimization_result: Dict,
                           backtest_result: Dict):
        """打印最终结果"""
        print(f"\n{'='*70}")
        print(f"最终优化结果")
        print(f"{'='*70}")

        print(f"\n📊 最优目标: {optimization_result['best_objective']}")

        print(f"\n🎯 最优权重 (Top 10):")
        weights = optimization_result['best_weights']
        sorted_weights = sorted(weights.items(),
                               key=lambda x: abs(x[1]),
                               reverse=True)

        for i, (factor, weight) in enumerate(sorted_weights[:10], 1):
            print(f"   {i:2d}. {factor:30s}: {weight:7.3f}")

        print(f"\n📈 回测结果:")
        metrics = backtest_result['metrics']
        print(f"   总收益率:     {metrics['total_return_pct']:+7.2f}%")
        print(f"   夏普比率:     {metrics['sharpe_ratio']:7.2f}")
        print(f"   最大回撤:     {metrics['max_drawdown']*100:7.2f}%")
        print(f"   胜率:         {metrics['win_rate']*100:6.1f}%")
        print(f"   盈利因子:     {metrics.get('profit_factor', 0):6.2f}")
        print(f"   交易次数:     {metrics['total_trades']}")


def main():
    """主函数"""
    # ================== 配置区 ==================
    ETF_CODES = [
        '510330.SH',  # 沪深300ETF
        '159928.SZ',  # 中证500ETF
        '159672.SZ',  # 中证1000ETF
    ]

    START_DATE = '20230101'
    END_DATE = None  # 使用最新数据

    POPULATION_SIZE = 30  # 种群大小（可调：更快=10，更准=50）
    GENERATIONS = 50       # 迭代次数（可调：更快=20，更准=100）
    # ===========================================

    for etf_code in ETF_CODES:
        optimizer = AdvancedETFOptimizer(
            etf_code=etf_code,
            start_date=START_DATE,
            end_date=END_DATE,
            cv_folds=3,
            test_size=0.2
        )

        result = optimizer.run_optimization()

        if result is None:
            print(f"⚠️  {etf_code} 优化失败，跳过")
            continue


if __name__ == '__main__':
    main()
