"""
优化的MACD策略配置

针对"高抛低吸做T"的优化：
1. 宽松止损，避免被震荡洗出
2. 严格的买入信号过滤（MA60 + 成交量 + 布林带）
3. 震荡市识别和仓位管理
"""

from .strategies import get_strategy_params

def get_optimized_strategy_params():
    """
    获取优化的策略参数

    特点：
    - 宽松止损（-20%）
    - 动态止盈（根据波动率调整）
    - 严格的买入信号过滤
    - 震荡市降仓
    """
    return {
        # ========== 基础设置 ==========
        'strategy_name': 'optimized_t_trading',

        # ========== 零轴过滤 ==========
        'zero_axis_filter': True,
        'require_zero_above': True,  # 必须在零轴上方才买入

        # ========== MA60过滤（严格）==========
        'ma60_filter': True,
        'ma60_tolerance': 0.02,  # 2%容忍度，更严格

        # ========== 背离信号 ==========
        'enable_divergence': True,
        'divergence_confirm': True,  # 需要确认
        'min_divergence_count': 2,

        # ========== 成交量确认（严格）==========
        'volume_confirm': True,  # 启用成交量过滤
        'volume_increase_min': 0.3,  # 至少放量30%
        'volume_increase_max': 0.7,

        # ========== 形态识别 ==========
        'duck_bill_enable': True,
        'inverted_duck_enable': False,  # 禁用倒鸭嘴（避免在顶部接盘）

        # ========== 周期共振 ==========
        'enable_resonance': False,

        # ========== 新增：布林带过滤 ==========
        'boll_filter': True,  # 启用布林带过滤
        'boll_max_position': 0.7,  # 最多在70%位置（不能接近上轨）
        'boll_min_position': 0.3,  # 至少在30%位置（不能接近下轨）

        # ========== 新增：波动率过滤 ==========
        'volatility_filter': True,
        'low_vol_threshold': 0.015,  # 低波动率阈值
        'high_vol_threshold': 0.04,  # 高波动率阈值
        'volatility_position_multiplier': {
            'low': 1.0,      # 低波动：正常仓位
            'normal': 0.8,   # 正常波动：80%仓位
            'high': 0.5      # 高波动：50%仓位
        }
    }


def get_backtest_params():
    """
    获取优化的回测参数

    针对做T风格：
    - 宽松止损（-20%）
    - 动态止盈
    - 分批止盈
    """
    return {
        'initial_capital': 2000,
        'num_positions': 10,
        'sell_fee': 0.005,

        # 宽松止损，避免被震荡洗出
        'stop_loss_pct': 0.20,  # -20%止损

        # 分批止盈策略
        'take_profit_pct1': 0.10,  # +10%卖出30%（落袋为安）
        'take_profit_pct2': 0.20,  # +20%卖出30%
        'take_profit_pct3': 0.35,  # +35%卖出40%

        # 追踪止盈（保护利润）
        'enable_trailing_stop': True,
        'trailing_stop_pct': 0.05,  # 从高点回落5%止盈
        'trailing_stop_activation': 0.15,  # 盈利15%后启用追踪止盈
    }


def get_market_regime_config():
    """
    获取市场环境识别配置

    区分趋势市和震荡市
    """
    return {
        # 趋势识别参数
        'trend_lookback': 20,  # 20日趋势
        'trend_strength_threshold': 0.5,  # 趋势强度阈值

        # 震荡市识别参数
        'range_bound_threshold': 0.03,  # 3%以内算震荡
        'range_bound_periods': 10,  # 连续10天在范围内算震荡市

        # 震荡市降仓
        'range_market_position_reduction': 0.5,  # 震荡市仓位减半
    }
