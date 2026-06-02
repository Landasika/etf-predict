"""
过滤器组合回测测试脚本

系统测试不同过滤器组合和参数，找出近一年收益率最高的策略配置。

测试内容:
1. 无过滤器 (基准)
2. KDJ 过滤器: J > threshold 拒绝买入, J < threshold 拒绝卖出
3. BOLL 过滤器: 位置过高拒绝买入, 位置过低拒绝卖出
4. 成交量过滤器: volume_ratio < threshold 拒绝买入
5. 市场环境过滤器: 牛市/震荡/熊市 仓位缩放
6. 所有过滤器组合

参数变体:
- KDJ: J>70/80/90 (买入否决), J<10/20/30 (卖出否决)
- BOLL: 0.5/0.5, 0.6/0.4, 0.7/0.3, 0.8/0.2
- 成交量: volume_ratio > 0.8/1.0/1.2/1.5
"""

import sys
import os
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime
from itertools import product

# 确保项目根目录在 path 中
# 脚本位于 scripts/ 子目录，因此向上查找项目根目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # 上一级 = etf-predict/
sys.path.insert(0, PROJECT_ROOT)

from core import database
from strategies.indicators import MACDIndicators
from strategies.backtester import MACDBacktester


# ============================================================================
# 数据加载
# ============================================================================

def load_watchlist():
    """加载 watchlist ETF 列表"""
    with open(os.path.join(PROJECT_ROOT, 'data/watchlist_etfs.json'), 'r') as f:
        data = json.load(f)
    return data.get('etfs', [])


def get_optimized_params(etf_info):
    """获取 ETF 的优化 MACD 参数"""
    params = etf_info.get('optimized_macd_params', {})
    if not params:
        # 默认参数
        params = {'macd_fast': 8, 'macd_slow': 17, 'macd_signal': 5}
    return params


# ============================================================================
# 过滤器实现
# ============================================================================

def apply_kdj_filter(df, buy_threshold=80, sell_threshold=20):
    """
    KDJ 过滤器

    买入信号: 当 J > buy_threshold 时拒绝 (超买区)
    卖出信号: 当 J < sell_threshold 时拒绝 (超卖区)

    Args:
        df: 含 signal_type 列的 DataFrame
        buy_threshold: 买入否决的 J 值上限
        sell_threshold: 卖出否决的 J 值下限
    """
    df = df.copy()

    # 确保 KDJ 已计算
    if 'kdj_j' not in df.columns:
        df = MACDIndicators.calculate_kdj(df)

    # 拒绝买入: J > threshold 表示超买
    buy_veto = (df['signal_type'] == 'BUY') & (df['kdj_j'] > buy_threshold)
    df.loc[buy_veto, 'signal_type'] = 'HOLD'
    df.loc[buy_veto, 'signal_strength'] = 0

    # 拒绝卖出: J < threshold 表示超卖 (不应卖出)
    sell_veto = (df['signal_type'] == 'SELL') & (df['kdj_j'] < sell_threshold)
    df.loc[sell_veto, 'signal_type'] = 'HOLD'
    df.loc[sell_veto, 'signal_strength'] = 0

    return df


def apply_boll_filter(df, buy_max=0.7, sell_min=0.3):
    """
    BOLL 位置过滤器

    买入信号: 当 BOLL 位置 > buy_max 时拒绝 (已在高位)
    卖出信号: 当 BOLL 位置 < sell_min 时拒绝 (已在低位)

    Args:
        df: 含 signal_type 列的 DataFrame
        buy_max: 买入否决的 BOLL 位置上限
        sell_min: 卖出否决的 BOLL 位置下限
    """
    df = df.copy()

    # 确保 BOLL 已计算
    if 'boll_upper' not in df.columns:
        df = MACDIndicators.calculate_boll(df)

    # 计算 BOLL 位置 (0=下轨, 1=上轨)
    boll_range = df['boll_upper'] - df['boll_lower']
    boll_position = (df['close'] - df['boll_lower']) / boll_range.replace(0, np.finfo(float).eps)

    # 拒绝买入: 位置过高
    buy_veto = (df['signal_type'] == 'BUY') & (boll_position > buy_max)
    df.loc[buy_veto, 'signal_type'] = 'HOLD'
    df.loc[buy_veto, 'signal_strength'] = 0

    # 拒绝卖出: 位置过低
    sell_veto = (df['signal_type'] == 'SELL') & (boll_position < sell_min)
    df.loc[sell_veto, 'signal_type'] = 'HOLD'
    df.loc[sell_veto, 'signal_strength'] = 0

    return df


def apply_volume_filter(df, min_ratio=1.0):
    """
    成交量过滤器

    买入信号: 当 volume_ratio < min_ratio 时拒绝 (缩量不买)

    Args:
        df: 含 signal_type 列的 DataFrame
        min_ratio: 最低成交量比率阈值
    """
    df = df.copy()

    # 确保成交量因子已计算
    if 'volume_ratio' not in df.columns:
        df = MACDIndicators.calculate_volume_factors(df)

    # 拒绝买入: 成交量不足
    buy_veto = (df['signal_type'] == 'BUY') & (df['volume_ratio'] < min_ratio)
    df.loc[buy_veto, 'signal_type'] = 'HOLD'
    df.loc[buy_veto, 'signal_strength'] = 0

    return df


def apply_market_env_filter(df, bull_scale=1.0, neutral_scale=0.5, bear_scale=0.3):
    """
    市场环境过滤器 (仓位缩放)

    通过 MA60 和 MA20 判断市场环境:
    - 牛市: 价格 > MA60 且 MA20 > MA60 -> 仓位 x bull_scale
    - 熊市: 价格 < MA60 且 MA20 < MA60 -> 仓位 x bear_scale
    - 震荡: 其他 -> 仓位 x neutral_scale

    Args:
        df: 含 signal_type 列的 DataFrame
        bull_scale: 牛市仓位系数
        neutral_scale: 震荡仓位系数
        bear_scale: 熊市仓位系数
    """
    df = df.copy()

    # 确保 MA60 已计算
    if 'ma60' not in df.columns:
        df = MACDIndicators.add_ma60(df)

    # 计算 MA20
    df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()

    # 判断市场环境
    is_bull = (df['close'] > df['ma60']) & (df['ma20'] > df['ma60'])
    is_bear = (df['close'] < df['ma60']) & (df['ma20'] < df['ma60'])

    # 对买入信号应用仓位缩放
    buy_mask = df['signal_type'] == 'BUY'

    # 熊市: 大幅降低信号强度
    bear_buy = buy_mask & is_bear
    df.loc[bear_buy, 'signal_strength'] = np.maximum(
        1, np.floor(df.loc[bear_buy, 'signal_strength'] * bear_scale).astype(int)
    )

    # 震荡: 中度降低信号强度
    neutral_buy = buy_mask & ~is_bull & ~is_bear
    df.loc[neutral_buy, 'signal_strength'] = np.maximum(
        1, np.floor(df.loc[neutral_buy, 'signal_strength'] * neutral_scale).astype(int)
    )

    # 牛市: 保持或增强信号强度
    bull_buy = buy_mask & is_bull
    df.loc[bull_buy, 'signal_strength'] = np.minimum(
        10, np.floor(df.loc[bull_buy, 'signal_strength'] * bull_scale).astype(int)
    )

    return df


# ============================================================================
# 自定义信号生成器 (在原有基础上支持 KDJ/volume 过滤)
# ============================================================================

class CustomSignalGenerator:
    """自定义信号生成器，在标准 MACD 信号基础上应用各种过滤器"""

    def __init__(self, base_params, filter_config):
        """
        Args:
            base_params: 基础 MACD 参数
            filter_config: 过滤器配置字典
        """
        self.base_params = base_params
        self.filter_config = filter_config

    def generate_signals(self, df):
        """生成信号并应用过滤器"""
        from strategies.signals import MACDSignalGenerator

        df = df.copy()

        # 1. 使用标准 MACD 信号生成器
        gen = MACDSignalGenerator(self.base_params)

        # 添加 KDJ 指标 (供后续过滤器使用)
        df = MACDIndicators.calculate_kdj(df)

        # 添加 BOLL 指标 (如果 BOLL 过滤器启用)
        if self.filter_config.get('boll_filter', False):
            df = MACDIndicators.calculate_boll(df)

        # 添加成交量因子 (如果成交量过滤器启用)
        if self.filter_config.get('volume_filter', False):
            df = MACDIndicators.calculate_volume_factors(df)

        # 生成基础信号
        df = gen.generate_signals(df)

        # 2. 应用 KDJ 过滤器
        if self.filter_config.get('kdj_filter', False):
            df = apply_kdj_filter(
                df,
                buy_threshold=self.filter_config.get('kdj_buy_threshold', 80),
                sell_threshold=self.filter_config.get('kdj_sell_threshold', 20)
            )

        # 3. 应用 BOLL 过滤器
        if self.filter_config.get('boll_filter', False):
            df = apply_boll_filter(
                df,
                buy_max=self.filter_config.get('boll_buy_max', 0.7),
                sell_min=self.filter_config.get('boll_sell_min', 0.3)
            )

        # 4. 应用成交量过滤器
        if self.filter_config.get('volume_filter', False):
            df = apply_volume_filter(
                df,
                min_ratio=self.filter_config.get('volume_min_ratio', 1.0)
            )

        # 5. 应用市场环境过滤器
        if self.filter_config.get('market_env_filter', False):
            df = apply_market_env_filter(
                df,
                bull_scale=self.filter_config.get('bull_scale', 1.0),
                neutral_scale=self.filter_config.get('neutral_scale', 0.5),
                bear_scale=self.filter_config.get('bear_scale', 0.3)
            )

        return df


# ============================================================================
# 回测执行器 (使用自定义信号生成器)
# ============================================================================

class CustomBacktester(MACDBacktester):
    """使用自定义信号生成器的回测器"""

    def __init__(self, signal_generator, **kwargs):
        super().__init__(**kwargs)
        self.custom_signal_generator = signal_generator

    def run_backtest(self, etf_code, strategy_params=None, start_date=None, end_date=None):
        """运行回测，使用自定义信号生成器"""
        # 加载数据
        data = self._load_data(etf_code, start_date, end_date)
        if data is None or len(data) == 0:
            raise ValueError(f"No data for {etf_code}")

        # 使用自定义信号生成器 (而非默认的 MACDSignalGenerator)
        data = self.custom_signal_generator.generate_signals(data)

        # 转换信号为交易强度
        data = self._convert_signals_to_strength(data)

        # 执行交易
        trades, performance = self._execute_trades(data)

        # 计算指标
        metrics = self._calculate_metrics(trades, performance, data)

        return {
            'trades': trades,
            'performance': performance,
            'metrics': metrics,
            'strategy_params': strategy_params or {}
        }


# ============================================================================
# 测试配置定义
# ============================================================================

def get_test_configs():
    """
    定义所有要测试的过滤器配置

    Returns:
        list of (config_name, filter_config) tuples
    """
    configs = []

    # -------------------------------------------------------
    # 1. 无过滤器 (基准)
    # -------------------------------------------------------
    configs.append(("BASELINE (无过滤器)", {}))

    # -------------------------------------------------------
    # 2. 单个过滤器测试
    # -------------------------------------------------------

    # KDJ 过滤器参数变体
    for buy_t, sell_t in [(70, 30), (80, 20), (90, 10)]:
        configs.append((
            f"KDJ(J>{buy_t}/J<{sell_t})",
            {
                'kdj_filter': True,
                'kdj_buy_threshold': buy_t,
                'kdj_sell_threshold': sell_t,
            }
        ))

    # BOLL 过滤器参数变体
    for buy_max, sell_min in [(0.5, 0.5), (0.6, 0.4), (0.7, 0.3), (0.8, 0.2)]:
        configs.append((
            f"BOLL({buy_max}/{sell_min})",
            {
                'boll_filter': True,
                'boll_buy_max': buy_max,
                'boll_sell_min': sell_min,
            }
        ))

    # 成交量过滤器参数变体
    for vol_ratio in [0.8, 1.0, 1.2, 1.5]:
        configs.append((
            f"VOL(>{vol_ratio})",
            {
                'volume_filter': True,
                'volume_min_ratio': vol_ratio,
            }
        ))

    # 市场环境过滤器参数变体
    for bull, neutral, bear in [(1.0, 0.5, 0.3), (1.0, 0.7, 0.5), (1.0, 0.3, 0.0)]:
        configs.append((
            f"ENV(B{bull}/N{neutral}/Be{bear})",
            {
                'market_env_filter': True,
                'bull_scale': bull,
                'neutral_scale': neutral,
                'bear_scale': bear,
            }
        ))

    # -------------------------------------------------------
    # 3. 两两组合
    # -------------------------------------------------------

    # KDJ(80/20) + BOLL(0.7/0.3)
    configs.append((
        "KDJ(80/20)+BOLL(0.7/0.3)",
        {
            'kdj_filter': True, 'kdj_buy_threshold': 80, 'kdj_sell_threshold': 20,
            'boll_filter': True, 'boll_buy_max': 0.7, 'boll_sell_min': 0.3,
        }
    ))

    # KDJ(80/20) + VOL(>1.0)
    configs.append((
        "KDJ(80/20)+VOL(>1.0)",
        {
            'kdj_filter': True, 'kdj_buy_threshold': 80, 'kdj_sell_threshold': 20,
            'volume_filter': True, 'volume_min_ratio': 1.0,
        }
    ))

    # KDJ(80/20) + ENV
    configs.append((
        "KDJ(80/20)+ENV(B1/N0.5/Be0.3)",
        {
            'kdj_filter': True, 'kdj_buy_threshold': 80, 'kdj_sell_threshold': 20,
            'market_env_filter': True, 'bull_scale': 1.0, 'neutral_scale': 0.5, 'bear_scale': 0.3,
        }
    ))

    # BOLL(0.7/0.3) + VOL(>1.0)
    configs.append((
        "BOLL(0.7/0.3)+VOL(>1.0)",
        {
            'boll_filter': True, 'boll_buy_max': 0.7, 'boll_sell_min': 0.3,
            'volume_filter': True, 'volume_min_ratio': 1.0,
        }
    ))

    # BOLL(0.7/0.3) + ENV
    configs.append((
        "BOLL(0.7/0.3)+ENV(B1/N0.5/Be0.3)",
        {
            'boll_filter': True, 'boll_buy_max': 0.7, 'boll_sell_min': 0.3,
            'market_env_filter': True, 'bull_scale': 1.0, 'neutral_scale': 0.5, 'bear_scale': 0.3,
        }
    ))

    # VOL(>1.0) + ENV
    configs.append((
        "VOL(>1.0)+ENV(B1/N0.5/Be0.3)",
        {
            'volume_filter': True, 'volume_min_ratio': 1.0,
            'market_env_filter': True, 'bull_scale': 1.0, 'neutral_scale': 0.5, 'bear_scale': 0.3,
        }
    ))

    # -------------------------------------------------------
    # 4. 三重组合
    # -------------------------------------------------------

    # KDJ + BOLL + VOL
    configs.append((
        "KDJ(80/20)+BOLL(0.7/0.3)+VOL(>1.0)",
        {
            'kdj_filter': True, 'kdj_buy_threshold': 80, 'kdj_sell_threshold': 20,
            'boll_filter': True, 'boll_buy_max': 0.7, 'boll_sell_min': 0.3,
            'volume_filter': True, 'volume_min_ratio': 1.0,
        }
    ))

    # KDJ + BOLL + ENV
    configs.append((
        "KDJ(80/20)+BOLL(0.7/0.3)+ENV",
        {
            'kdj_filter': True, 'kdj_buy_threshold': 80, 'kdj_sell_threshold': 20,
            'boll_filter': True, 'boll_buy_max': 0.7, 'boll_sell_min': 0.3,
            'market_env_filter': True, 'bull_scale': 1.0, 'neutral_scale': 0.5, 'bear_scale': 0.3,
        }
    ))

    # KDJ + VOL + ENV
    configs.append((
        "KDJ(80/20)+VOL(>1.0)+ENV",
        {
            'kdj_filter': True, 'kdj_buy_threshold': 80, 'kdj_sell_threshold': 20,
            'volume_filter': True, 'volume_min_ratio': 1.0,
            'market_env_filter': True, 'bull_scale': 1.0, 'neutral_scale': 0.5, 'bear_scale': 0.3,
        }
    ))

    # BOLL + VOL + ENV
    configs.append((
        "BOLL(0.7/0.3)+VOL(>1.0)+ENV",
        {
            'boll_filter': True, 'boll_buy_max': 0.7, 'boll_sell_min': 0.3,
            'volume_filter': True, 'volume_min_ratio': 1.0,
            'market_env_filter': True, 'bull_scale': 1.0, 'neutral_scale': 0.5, 'bear_scale': 0.3,
        }
    ))

    # -------------------------------------------------------
    # 5. 全部组合
    # -------------------------------------------------------
    configs.append((
        "ALL(KDJ80+BOLL0.7+VOL1.0+ENV)",
        {
            'kdj_filter': True, 'kdj_buy_threshold': 80, 'kdj_sell_threshold': 20,
            'boll_filter': True, 'boll_buy_max': 0.7, 'boll_sell_min': 0.3,
            'volume_filter': True, 'volume_min_ratio': 1.0,
            'market_env_filter': True, 'bull_scale': 1.0, 'neutral_scale': 0.5, 'bear_scale': 0.3,
        }
    ))

    # 另一种激进组合
    configs.append((
        "ALL-STRICT(KDJ70+BOLL0.6+VOL1.2+ENV)",
        {
            'kdj_filter': True, 'kdj_buy_threshold': 70, 'kdj_sell_threshold': 30,
            'boll_filter': True, 'boll_buy_max': 0.6, 'boll_sell_min': 0.4,
            'volume_filter': True, 'volume_min_ratio': 1.2,
            'market_env_filter': True, 'bull_scale': 1.0, 'neutral_scale': 0.5, 'bear_scale': 0.3,
        }
    ))

    # 宽松组合
    configs.append((
        "ALL-LOOSE(KDJ90+BOLL0.8+VOL0.8+ENV)",
        {
            'kdj_filter': True, 'kdj_buy_threshold': 90, 'kdj_sell_threshold': 10,
            'boll_filter': True, 'boll_buy_max': 0.8, 'boll_sell_min': 0.2,
            'volume_filter': True, 'volume_min_ratio': 0.8,
            'market_env_filter': True, 'bull_scale': 1.0, 'neutral_scale': 0.5, 'bear_scale': 0.3,
        }
    ))

    return configs


# ============================================================================
# 主测试流程
# ============================================================================

def run_single_backtest(etf_code, etf_params, filter_config, start_date, end_date):
    """
    对单个 ETF 运行单个配置的回测

    Returns:
        dict with metrics, or None if failed
    """
    try:
        # 构建信号生成器
        base_params = MACDSignalGenerator_default_params()
        base_params.update(etf_params)  # 使用优化后的 MACD 参数

        signal_gen = CustomSignalGenerator(base_params, filter_config)

        # 构建回测器
        backtester = CustomBacktester(
            signal_gen,
            initial_capital=2000,
            num_positions=10,
            stop_loss_pct=0.10,
            take_profit_pct1=0.15,
            take_profit_pct2=0.30,
            take_profit_pct3=0.35,
        )

        result = backtester.run_backtest(
            etf_code=etf_code,
            start_date=start_date,
            end_date=end_date,
        )

        return result['metrics']

    except Exception as e:
        return None


def MACDSignalGenerator_default_params():
    """获取 MACDSignalGenerator 默认参数"""
    from strategies.signals import MACDSignalGenerator
    return MACDSignalGenerator.default_params()


def run_all_tests():
    """运行所有测试"""

    print("=" * 100)
    print("过滤器组合回测测试")
    print("=" * 100)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"回测区间: 20250101 - 最新数据")
    print(f"初始资金: 2000, 仓位: 10")
    print()

    # 加载 watchlist
    watchlist = load_watchlist()
    print(f"加载 {len(watchlist)} 个 ETF")

    # 预加载数据检查
    etf_codes = [etf['code'] for etf in watchlist]
    available_etfs = []
    for etf in watchlist:
        data = database.get_etf_daily_data(etf['code'], start_date='20240101')
        if data and len(data) > 60:
            available_etfs.append(etf)
        else:
            print(f"  跳过 {etf['code']} ({etf.get('name', 'N/A')}): 数据不足")

    print(f"有效 ETF: {len(available_etfs)} 个")
    print()

    # 获取测试配置
    test_configs = get_test_configs()
    print(f"测试配置: {len(test_configs)} 种")
    print()

    # 结果存储
    all_results = {}

    start_date = '20250101'
    end_date = None

    total_configs = len(test_configs)
    total_etfs = len(available_etfs)

    for config_idx, (config_name, filter_config) in enumerate(test_configs):
        config_start_time = time.time()
        print(f"[{config_idx+1}/{total_configs}] 测试: {config_name}")

        etf_results = []
        failed_count = 0

        for etf in available_etfs:
            etf_code = etf['code']
            etf_params = get_optimized_params(etf)

            metrics = run_single_backtest(
                etf_code, etf_params, filter_config, start_date, end_date
            )

            if metrics:
                etf_results.append({
                    'code': etf_code,
                    'name': etf.get('name', ''),
                    **metrics
                })
            else:
                failed_count += 1

        if etf_results:
            # 计算平均指标
            df_results = pd.DataFrame(etf_results)

            avg_return = df_results['total_return_pct'].mean()
            avg_win_rate = df_results['win_rate'].mean()
            avg_max_dd = df_results['max_drawdown'].mean()
            avg_sharpe = df_results['sharpe_ratio'].mean()
            avg_trades = df_results['total_trades'].mean()
            total_trades = df_results['total_trades'].sum()
            avg_hold_days = df_results['avg_hold_days'].mean()

            # 中位数收益率
            median_return = df_results['total_return_pct'].median()

            # 盈利 ETF 数量
            profitable = len(df_results[df_results['total_return_pct'] > 0])
            total_etfs_tested = len(df_results)

            # 收益率分布
            std_return = df_results['total_return_pct'].std()

            all_results[config_name] = {
                'avg_return_pct': round(avg_return, 2),
                'median_return_pct': round(median_return, 2),
                'std_return_pct': round(std_return, 2),
                'avg_win_rate': round(avg_win_rate * 100, 1),
                'avg_max_drawdown': round(avg_max_dd * 100, 2),
                'avg_sharpe': round(avg_sharpe, 3),
                'avg_trades': round(avg_trades, 1),
                'total_trades': int(total_trades),
                'avg_hold_days': round(avg_hold_days, 1),
                'profitable_count': profitable,
                'total_etfs': total_etfs_tested,
                'failed_count': failed_count,
            }

            elapsed = time.time() - config_start_time
            print(f"  -> 平均收益: {avg_return:+.2f}% | 胜率: {avg_win_rate*100:.1f}% | "
                  f"最大回撤: {avg_max_dd*100:.2f}% | 夏普: {avg_sharpe:.3f} | "
                  f"总交易: {total_trades} | {elapsed:.1f}s")
        else:
            print(f"  -> 全部失败!")

    return all_results


def print_results_table(results):
    """打印结果对比表"""

    if not results:
        print("没有结果可显示")
        return

    # 按 avg_return_pct 降序排列
    sorted_results = sorted(results.items(), key=lambda x: x[1]['avg_return_pct'], reverse=True)

    print("\n")
    print("=" * 140)
    print("回测结果对比表 (按平均收益率排序)")
    print("=" * 140)

    # 表头
    header = (
        f"{'排名':>4} | {'配置名称':<40} | {'平均收益%':>10} | {'中位收益%':>10} | "
        f"{'标准差%':>8} | {'胜率%':>7} | {'最大回撤%':>10} | "
        f"{'夏普':>7} | {'总交易':>7} | {'盈利/总数':>9}"
    )
    print(header)
    print("-" * 140)

    # 基准数据
    baseline = results.get("BASELINE (无过滤器)", None)

    for rank, (name, data) in enumerate(sorted_results, 1):
        # 与基准对比
        diff_str = ""
        if baseline and name != "BASELINE (无过滤器)":
            diff = data['avg_return_pct'] - baseline['avg_return_pct']
            diff_str = f" ({diff:+.2f}%)"
        elif name == "BASELINE (无过滤器)":
            diff_str = " [基准]"

        profitable_str = f"{data['profitable_count']}/{data['total_etfs']}"

        row = (
            f"{rank:>4} | {name:<40} | {data['avg_return_pct']:>+10.2f} | "
            f"{data['median_return_pct']:>+10.2f} | {data['std_return_pct']:>8.2f} | "
            f"{data['avg_win_rate']:>7.1f} | {data['avg_max_drawdown']:>10.2f} | "
            f"{data['avg_sharpe']:>7.3f} | {data['total_trades']:>7} | {profitable_str:>9}"
        )
        print(row)

    print("-" * 140)

    # 基准对比摘要
    if baseline:
        print("\n")
        print("=" * 80)
        print("与基准对比 (基准平均收益率: {:.2f}%)".format(baseline['avg_return_pct']))
        print("=" * 80)

        improvements = []
        declines = []

        for name, data in sorted_results:
            if name == "BASELINE (无过滤器)":
                continue
            diff = data['avg_return_pct'] - baseline['avg_return_pct']
            if diff > 0:
                improvements.append((name, diff, data))
            else:
                declines.append((name, diff, data))

        if improvements:
            print("\n收益率提升的配置:")
            for name, diff, data in sorted(improvements, key=lambda x: x[1], reverse=True):
                print(f"  +{diff:.2f}%  {name}  (胜率:{data['avg_win_rate']}% 夏普:{data['avg_sharpe']} 交易:{data['total_trades']})")

        if declines:
            print("\n收益率下降的配置:")
            for name, diff, data in sorted(declines, key=lambda x: x[1]):
                print(f"  {diff:.2f}%  {name}  (胜率:{data['avg_win_rate']}% 夏普:{data['avg_sharpe']} 交易:{data['total_trades']})")

    # Top 3 推荐
    print("\n")
    print("=" * 80)
    print("Top 3 推荐配置 (综合考虑收益率、胜率、夏普比率)")
    print("=" * 80)

    # 综合评分: 收益率权重 0.5, 夏普权重 0.3, 胜率权重 0.2
    # 归一化后打分
    if sorted_results:
        max_ret = max(d['avg_return_pct'] for _, d in sorted_results)
        min_ret = min(d['avg_return_pct'] for _, d in sorted_results)
        ret_range = max_ret - min_ret if max_ret != min_ret else 1

        max_sharpe = max(d['avg_sharpe'] for _, d in sorted_results)
        min_sharpe = min(d['avg_sharpe'] for _, d in sorted_results)
        sharpe_range = max_sharpe - min_sharpe if max_sharpe != min_sharpe else 1

        max_wr = max(d['avg_win_rate'] for _, d in sorted_results)
        min_wr = min(d['avg_win_rate'] for _, d in sorted_results)
        wr_range = max_wr - min_wr if max_wr != min_wr else 1

        scored = []
        for name, data in sorted_results:
            ret_score = (data['avg_return_pct'] - min_ret) / ret_range
            sharpe_score = (data['avg_sharpe'] - min_sharpe) / sharpe_range
            wr_score = (data['avg_win_rate'] - min_wr) / wr_range
            total_score = ret_score * 0.5 + sharpe_score * 0.3 + wr_score * 0.2
            scored.append((name, total_score, data))

        scored.sort(key=lambda x: x[1], reverse=True)

        for rank, (name, score, data) in enumerate(scored[:3], 1):
            print(f"\n  #{rank} {name}")
            print(f"       综合评分: {score:.3f}")
            print(f"       平均收益: {data['avg_return_pct']:+.2f}%  中位收益: {data['median_return_pct']:+.2f}%")
            print(f"       胜率: {data['avg_win_rate']}%  最大回撤: {data['avg_max_drawdown']}%  夏普: {data['avg_sharpe']}")
            print(f"       总交易次数: {data['total_trades']}  盈利ETF: {data['profitable_count']}/{data['total_etfs']}")

            # 与基准对比
            if baseline and name != "BASELINE (无过滤器)":
                diff = data['avg_return_pct'] - baseline['avg_return_pct']
                print(f"       vs 基准: {diff:+.2f}%")

    print("\n" + "=" * 140)

    # 各 ETF 收益率详细表 (仅 Top 5 配置)
    print("\n")
    print("=" * 140)
    print("Top 5 配置各 ETF 详细收益表")
    print("=" * 140)


def save_results_to_csv(results, filepath):
    """保存结果到 CSV"""
    rows = []
    for name, data in results.items():
        row = {'配置名称': name}
        row.update(data)
        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values('avg_return_pct', ascending=False)
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存到: {filepath}")


def run_etf_detail_comparison(watchlist, top_configs, start_date='20250101'):
    """对 Top 配置打印各 ETF 的详细收益"""

    print(f"\n{'ETF代码':<14} {'名称':<10}", end="")
    for config_name, _ in top_configs:
        short_name = config_name[:20]
        print(f" {short_name:>22}", end="")
    print()
    print("-" * (24 + 22 * len(top_configs)))

    for etf in watchlist:
        etf_code = etf['code']
        name = etf.get('name', '')[:8]
        etf_params = get_optimized_params(etf)

        row_str = f"{etf_code:<14} {name:<10}"

        for config_name, filter_config in top_configs:
            metrics = run_single_backtest(
                etf_code, etf_params, filter_config, start_date, None
            )
            if metrics:
                ret = metrics['total_return_pct']
                row_str += f" {ret:>+22.2f}%"
            else:
                row_str += f" {'N/A':>22}"

        print(row_str)


# ============================================================================
# 入口
# ============================================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='过滤器组合回测测试')
    parser.add_argument('--detail', action='store_true',
                        help='显示 Top 5 配置的 ETF 详细收益')
    parser.add_argument('--output', type=str, default='filter_test_results.csv',
                        help='结果 CSV 输出文件名 (默认: filter_test_results.csv)')
    args = parser.parse_args()

    # 运行所有测试
    results = run_all_tests()

    # 打印结果表
    print_results_table(results)

    # 保存结果
    output_path = os.path.join(PROJECT_ROOT, args.output)
    save_results_to_csv(results, output_path)

    # 可选: ETF 详细对比
    if args.detail:
        # 取 Top 5 配置
        sorted_results = sorted(results.items(), key=lambda x: x[1]['avg_return_pct'], reverse=True)
        all_configs = get_test_configs()
        config_dict = {name: cfg for name, cfg in all_configs}
        top_configs = [(name, config_dict[name]) for name, _ in sorted_results[:5] if name in config_dict]
        watchlist = load_watchlist()
        run_etf_detail_comparison(watchlist, top_configs)

    print(f"\n完成!")
