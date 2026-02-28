"""
Factor Weight Optimizer

Uses genetic algorithm to find optimal factor weights for short-term profit maximization.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Callable, Optional
import random
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed


@dataclass
class OptimizationResult:
    """优化结果"""
    best_weights: Dict[str, float]
    best_fitness: float
    best_metrics: Dict
    generation: int
    history: List[Dict]


class FactorWeightOptimizer:
    """
    因子权重优化器

    使用遗传算法优化因子权重，以最大化短期盈利为目标。
    """

    def __init__(self,
                 factor_groups: Dict[str, List[str]] = None,
                 population_size: int = 50,
                 generations: int = 100,
                 mutation_rate: float = 0.1,
                 elite_size: int = 5,
                 tournament_size: int = 5):
        """
        初始化优化器

        Args:
            factor_groups: 因子分组字典
            population_size: 种群大小
            generations: 迭代代数
            mutation_rate: 变异率
            elite_size: 精英个体数量
            tournament_size: 锦标赛选择规模
        """
        self.factor_groups = factor_groups or self._get_default_factor_groups()
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size
        self.tournament_size = tournament_size

        # 展平所有因子
        self.all_factors = []
        for group_factors in self.factor_groups.values():
            self.all_factors.extend(group_factors)

        # 确定权重约束
        self.weight_bounds = (-2.0, 2.0)  # 每个因子的权重范围

    def _get_default_factor_groups(self) -> Dict[str, List[str]]:
        """获取默认因子分组"""
        return {
            'macd': ['f_macd_trend', 'f_macd_cross', 'f_macd_hist_slope'],
            'kdj': ['f_k_oversold', 'f_k_overbought', 'f_k_slope', 'f_kd_cross'],
            'boll': ['f_boll_lower_touch', 'f_boll_upper_touch', 'f_boll_position'],
            'volume': ['f_volume_ratio', 'f_volume_spike'],
            'trend': ['f_ma60_trend', 'f_price_momentum']
        }

    def optimize(self,
                 df: pd.DataFrame,
                 objective: str = 'total_return',
                 initial_capital: float = 2000,
                 commission: float = 0.005,
                 holding_period: int = 1,
                 verbose: bool = True) -> OptimizationResult:
        """
        优化因子权重

        Args:
            df: 包含因子的DataFrame
            objective: 优化目标 ('total_return', 'sharpe', 'profit_factor', 'win_rate')
            initial_capital: 初始资金
            commission: 手续费率
            holding_period: 持仓周期（天）
            verbose: 是否输出进度

        Returns:
            OptimizationResult: 优化结果
        """
        # 初始化种群
        population = self._initialize_population()

        best_fitness = -np.inf
        best_individual = None
        best_metrics = {}
        history = []

        for generation in range(self.generations):
            # 评估适应度
            fitness_scores = []
            for individual in population:
                fitness, metrics = self._calculate_fitness(
                    individual, df, objective, initial_capital,
                    commission, holding_period
                )
                fitness_scores.append((fitness, metrics, individual))

            # 排序
            fitness_scores.sort(key=lambda x: x[0], reverse=True)

            # 更新最佳个体
            if fitness_scores[0][0] > best_fitness:
                best_fitness = fitness_scores[0][0]
                best_individual = fitness_scores[0][2]
                best_metrics = fitness_scores[0][1]

            # 记录历史
            history.append({
                'generation': generation,
                'best_fitness': best_fitness,
                'avg_fitness': np.mean([f[0] for f in fitness_scores]),
                'best_metrics': best_metrics
            })

            if verbose and generation % 10 == 0:
                print(f"Generation {generation}: Best {objective} = {best_fitness:.4f}")

            # 选择、交叉、变异（传入完整的fitness_scores）
            population = self._evolve_population(fitness_scores, population)

        # 转换为权重字典
        best_weights = dict(zip(self.all_factors, best_individual))

        return OptimizationResult(
            best_weights=best_weights,
            best_fitness=best_fitness,
            best_metrics=best_metrics,
            generation=generation,
            history=history
        )

    def _initialize_population(self) -> List[np.ndarray]:
        """初始化种群"""
        population = []
        for _ in range(self.population_size):
            # 随机生成权重
            individual = np.random.uniform(
                self.weight_bounds[0],
                self.weight_bounds[1],
                len(self.all_factors)
            )
            # 归一化，使权重总和在合理范围
            individual = self._normalize_weights(individual)
            population.append(individual)
        return population

    def _normalize_weights(self, weights: np.ndarray) -> np.ndarray:
        """归一化权重"""
        # 方法1: 按比例缩放，使绝对值之和为1
        total = np.sum(np.abs(weights))
        if total > 0:
            weights = weights / total
        return weights

    def _calculate_fitness(self,
                          individual: np.ndarray,
                          df: pd.DataFrame,
                          objective: str,
                          initial_capital: float,
                          commission: float,
                          holding_period: int) -> Tuple[float, Dict]:
        """
        计算适应度

        Args:
            individual: 权重个体
            df: 数据
            objective: 优化目标
            initial_capital: 初始资金
            commission: 手续费
            holding_period: 持仓天数

        Returns:
            (适应度值, 指标字典)
        """
        # 计算加权信号强度
        weights_dict = dict(zip(self.all_factors, individual))

        signal_strength = np.zeros(len(df))
        for factor, weight in weights_dict.items():
            if factor in df.columns:
                signal_strength += df[factor].fillna(0) * weight

        # 执行回测
        metrics = self._fast_backtest(
            df,
            signal_strength,
            initial_capital,
            commission,
            holding_period
        )

        # 根据目标返回适应度
        if objective == 'total_return':
            fitness = metrics['total_return_pct']
        elif objective == 'sharpe':
            fitness = metrics['sharpe_ratio']
        elif objective == 'profit_factor':
            fitness = metrics['profit_factor']
        elif objective == 'win_rate':
            fitness = metrics['win_rate'] * 100
        elif objective == 'custom':
            # 自定义：收益率 + 夏普比率 - 最大回撤惩罚
            fitness = metrics['total_return_pct'] + \
                     metrics['sharpe_ratio'] * 10 - \
                     metrics['max_drawdown'] * 100
        else:
            fitness = metrics['total_return_pct']

        return fitness, metrics

    def _fast_backtest(self,
                      df: pd.DataFrame,
                      signal_strength: np.ndarray,
                      initial_capital: float,
                      commission: float,
                      holding_period: int) -> Dict:
        """
        快速回测（用于优化器内部）

        简化版回测，专注于计算性能
        """
        # 确保 signal_strength 是 numpy 数组
        if isinstance(signal_strength, pd.Series):
            signal_strength = signal_strength.values

        cash = initial_capital
        position_shares = 0
        entry_price = 0
        entry_idx = 0

        trades = []  # (buy_idx, sell_idx, buy_price, sell_price, shares)
        daily_returns = []

        for i in range(1, len(df)):
            price = df['close'].iloc[i]
            signal = signal_strength[i]

            # 如果有持仓
            if position_shares > 0:
                # 检查是否应该卖出（达到持仓期或信号反转）
                days_held = i - entry_idx
                should_sell = (days_held >= holding_period) or (signal < -0.5)

                if should_sell:
                    # 卖出
                    proceeds = position_shares * price * (1 - commission)
                    cash += proceeds
                    trades.append((entry_idx, i, entry_price, price, position_shares))
                    position_shares = 0
                    entry_price = 0
                    entry_idx = 0

            # 如果有空仓且信号为正
            elif signal > 0.5 and cash > price * 100:
                # 买入（使用固定金额或按信号强度）
                buy_amount = min(cash, initial_capital * 0.2)  # 每次最多20%资金
                shares = int(buy_amount / price)
                if shares > 0:
                    cost = shares * price
                    cash -= cost
                    position_shares = shares
                    entry_price = price
                    entry_idx = i

            # 计算当日资产价值
            position_value = position_shares * price
            portfolio_value = cash + position_value
            daily_returns.append((portfolio_value - initial_capital) / initial_capital)

        # 最终平仓
        if position_shares > 0:
            price = df['close'].iloc[-1]
            proceeds = position_shares * price * (1 - commission)
            cash += proceeds
            trades.append((entry_idx, len(df)-1, entry_price, price, position_shares))

        final_value = cash

        # 计算指标
        total_return = (final_value - initial_capital) / initial_capital
        total_return_pct = total_return * 100

        # 夏普比率
        if len(daily_returns) > 1:
            returns_array = np.array(daily_returns)
            sharpe = np.sqrt(252) * returns_array.mean() / (returns_array.std() + 1e-8)
        else:
            sharpe = 0

        # 最大回撤
        cummax = np.maximum.accumulate(daily_returns)
        drawdown = (np.array(daily_returns) - cummax)
        max_drawdown = drawdown.min()

        # 胜率和盈利因子
        if trades:
            winning_trades = [t for t in trades if t[3] > t[2]]
            win_rate = len(winning_trades) / len(trades)

            gross_profit = sum([t[3] - t[2] for t in trades if t[3] > t[2]])
            gross_loss = abs(sum([t[3] - t[2] for t in trades if t[3] <= t[2]]))
            profit_factor = gross_profit / (gross_loss + 1e-8)
        else:
            win_rate = 0
            profit_factor = 0

        return {
            'total_return_pct': total_return_pct,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(trades)
        }

    def _evolve_population(self,
                          fitness_scores: List[Tuple],
                          old_population: List[np.ndarray]) -> List[np.ndarray]:
        """进化种群"""
        new_population = []

        # 精英保留
        for i in range(self.elite_size):
            new_population.append(fitness_scores[i][2].copy())

        # 生成剩余个体
        while len(new_population) < self.population_size:
            # 锦标赛选择
            parent1 = self._tournament_selection(fitness_scores)
            parent2 = self._tournament_selection(fitness_scores)

            # 交叉
            child = self._crossover(parent1, parent2)

            # 变异
            if random.random() < self.mutation_rate:
                child = self._mutate(child)

            new_population.append(child)

        return new_population

    def _tournament_selection(self, fitness_scores: List[Tuple]) -> np.ndarray:
        """锦标赛选择"""
        tournament = random.sample(fitness_scores, self.tournament_size)
        tournament.sort(key=lambda x: x[0], reverse=True)
        return tournament[0][2].copy()

    def _crossover(self, parent1: np.ndarray, parent2: np.ndarray) -> np.ndarray:
        """单点交叉"""
        crossover_point = random.randint(1, len(parent1) - 1)
        child = np.concatenate([
            parent1[:crossover_point],
            parent2[crossover_point:]
        ])
        return self._normalize_weights(child)

    def _mutate(self, individual: np.ndarray) -> np.ndarray:
        """变异操作"""
        mutated = individual.copy()

        # 随机选择几个基因进行变异
        num_mutations = random.randint(1, max(1, len(mutated) // 5))
        for _ in range(num_mutations):
            idx = random.randint(0, len(mutated) - 1)
            # 添加高斯噪声
            mutated[idx] += np.random.normal(0, 0.5)

        return self._normalize_weights(mutated)


class GridSearchOptimizer:
    """
    网格搜索优化器

    用于因子数量较少时的穷举搜索。
    """

    def __init__(self,
                 factor_groups: Dict[str, List[str]] = None,
                 weight_range: Tuple[float, float] = (-1.0, 1.0),
                 weight_steps: int = 5):
        """
        初始化网格搜索优化器

        Args:
            factor_groups: 因子分组
            weight_range: 权重范围
            weight_steps: 权重步数
        """
        self.factor_groups = factor_groups or self._get_default_factor_groups()
        self.weight_range = weight_range
        self.weight_steps = weight_steps

        # 展平所有因子
        self.all_factors = []
        for group_factors in self.factor_groups.values():
            self.all_factors.extend(group_factors)

    def _get_default_factor_groups(self) -> Dict[str, List[str]]:
        """获取默认因子分组"""
        return {
            'macd': ['f_macd_trend', 'f_macd_cross'],
            'kdj': ['f_k_oversold', 'f_k_slope'],
            'volume': ['f_volume_ratio']
        }

    def optimize(self,
                 df: pd.DataFrame,
                 objective: str = 'total_return',
                 verbose: bool = True) -> OptimizationResult:
        """网格搜索优化"""
        # 生成权重网格
        weight_values = np.linspace(
            self.weight_range[0],
            self.weight_range[1],
            self.weight_steps
        )

        # 限制因子数量（否则组合爆炸）
        if len(self.all_factors) > 6:
            print("警告：因子数量过多，网格搜索可能非常慢")
            print("建议使用遗传算法优化器")

        best_fitness = -np.inf
        best_weights = None
        best_metrics = {}
        history = []

        # 使用简化的网格搜索（随机采样）
        iterations = 1000
        for i in range(iterations):
            # 随机采样权重
            weights = np.random.choice(weight_values, len(self.all_factors))
            weights = weights / np.sum(np.abs(weights))  # 归一化

            weights_dict = dict(zip(self.all_factors, weights))

            # 计算信号强度
            signal_strength = np.zeros(len(df))
            for factor, weight in weights_dict.items():
                if factor in df.columns:
                    signal_strength += df[factor].fillna(0) * weight

            # 快速回测
            from .optimizer import FactorWeightOptimizer
            opt = FactorWeightOptimizer()
            metrics = opt._fast_backtest(
                df, signal_strength,
                initial_capital=2000,
                commission=0.005,
                holding_period=1
            )

            fitness = metrics.get(objective, metrics['total_return_pct'])

            if fitness > best_fitness:
                best_fitness = fitness
                best_weights = weights_dict
                best_metrics = metrics

            if verbose and i % 100 == 0:
                print(f"Iteration {i}: Best {objective} = {best_fitness:.4f}")

        return OptimizationResult(
            best_weights=best_weights,
            best_fitness=best_fitness,
            best_metrics=best_metrics,
            generation=iterations,
            history=history
        )


def optimize_for_short_term(df: pd.DataFrame,
                            holding_period: int = 1,
                            objective: str = 'total_return',
                            method: str = 'genetic',
                            verbose: bool = True,
                            **kwargs) -> OptimizationResult:
    """
    便捷函数：优化超短线因子权重

    Args:
        df: 包含因子的DataFrame
        holding_period: 持仓天数（1=隔夜，0=日内）
        objective: 优化目标
        method: 优化方法 ('genetic' 或 'grid')
        verbose: 是否显示进度
        **kwargs: 其他参数（population_size, generations等）

    Returns:
        OptimizationResult
    """
    # 分离构造函数参数和optimize方法参数
    optimizer_init_kwargs = {}
    optimize_kwargs = {}

    # 构造函数参数
    for key in ['factor_groups', 'population_size', 'generations',
                'mutation_rate', 'elite_size', 'tournament_size']:
        if key in kwargs:
            optimizer_init_kwargs[key] = kwargs.pop(key)

    if method == 'genetic':
        optimizer = FactorWeightOptimizer(**optimizer_init_kwargs)
    elif method == 'grid':
        optimizer = GridSearchOptimizer(**optimizer_init_kwargs)
    else:
        raise ValueError(f"Unknown optimization method: {method}")

    result = optimizer.optimize(
        df=df,
        objective=objective,
        holding_period=holding_period,
        verbose=verbose,
        **kwargs
    )

    return result
