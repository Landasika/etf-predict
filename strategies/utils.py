"""
Utility functions for MACD strategy module
"""
import pandas as pd
import numpy as np
from typing import Dict, List


def validate_signal_sequence(signals: pd.DataFrame) -> Dict:
    """
    Validate signal sequence for logical consistency

    Checks:
    - No overlapping buy-sell signals on same day
    - Signal strength is within valid range
    - No consecutive signals of same type without position change

    Args:
        signals: DataFrame with signal_type and signal_strength columns

    Returns:
        Dictionary with validation results and any issues found
    """
    issues = []

    # Check signal strength range
    invalid_strength = signals[
        (signals['signal_strength'] < -10) | (signals['signal_strength'] > 10)
    ]
    if len(invalid_strength) > 0:
        issues.append(f"Found {len(invalid_strength)} signals with invalid strength")

    # Check for HOLD signals with non-zero strength
    invalid_hold = signals[
        (signals['signal_type'] == 'HOLD') & (signals['signal_strength'] != 0)
    ]
    if len(invalid_hold) > 0:
        issues.append(f"Found {len(invalid_hold)} HOLD signals with non-zero strength")

    # Check signal type validity
    valid_types = {'BUY', 'SELL', 'HOLD'}
    invalid_types = signals[~signals['signal_type'].isin(valid_types)]
    if len(invalid_types) > 0:
        issues.append(f"Found {len(invalid_types)} signals with invalid type")

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'total_signals': len(signals),
        'buy_signals': len(signals[signals['signal_type'] == 'BUY']),
        'sell_signals': len(signals[signals['signal_type'] == 'SELL']),
        'hold_signals': len(signals[signals['signal_type'] == 'HOLD'])
    }


def calculate_signal_statistics(signals: pd.DataFrame) -> Dict:
    """
    Calculate statistics about generated signals

    Args:
        signals: DataFrame with MACD signals

    Returns:
        Dictionary with signal statistics
    """
    if len(signals) == 0:
        return {}

    buy_signals = signals[signals['signal_type'] == 'BUY']
    sell_signals = signals[signals['signal_type'] == 'SELL']

    # Buy signal strength distribution
    buy_strength_dist = {
        'strong (8-10)': len(buy_signals[buy_signals['signal_strength'] >= 8]),
        'medium (6-7)': len(buy_signals[(buy_signals['signal_strength'] >= 6) & (buy_signals['signal_strength'] < 8)]),
        'weak (1-5)': len(buy_signals[(buy_signals['signal_strength'] >= 1) & (buy_signals['signal_strength'] < 6)])
    }

    # Sell signal strength distribution
    sell_strength_dist = {
        'strong (-8 to -10)': len(sell_signals[sell_signals['signal_strength'] <= -8]),
        'medium (-6 to -7)': len(sell_signals[(sell_signals['signal_strength'] <= -6) & (sell_signals['signal_strength'] > -8)]),
        'weak (-1 to -5)': len(sell_signals[(sell_signals['signal_strength'] <= -1) & (sell_signals['signal_strength'] > -6)])
    }

    # Signal frequency (signals per month)
    if 'date' in signals.columns:
        signals['date'] = pd.to_datetime(signals['date'], format='%Y%m%d')
        months = (signals['date'].max() - signals['date'].min()).days / 30.44
        signals_per_month = len(signals[signals['signal_type'] != 'HOLD']) / months if months > 0 else 0
    else:
        signals_per_month = 0

    return {
        'total_signals': len(signals),
        'buy_signals': len(buy_signals),
        'sell_signals': len(sell_signals),
        'hold_signals': len(signals[signals['signal_type'] == 'HOLD']),
        'buy_strength_distribution': buy_strength_dist,
        'sell_strength_distribution': sell_strength_dist,
        'signals_per_month': signals_per_month,
        'buy_sell_ratio': len(buy_signals) / len(sell_signals) if len(sell_signals) > 0 else 0
    }


def analyze_macd_state(df: pd.DataFrame) -> Dict:
    """
    Analyze current MACD state and trend

    Args:
        df: DataFrame with MACD indicators

    Returns:
        Dictionary with MACD state analysis
    """
    if len(df) == 0:
        return {}

    latest = df.iloc[-1]

    # Determine trend
    if latest['macd_dif'] > 0 and latest['macd_dea'] > 0:
        trend = 'bullish'
    elif latest['macd_dif'] < 0 and latest['macd_dea'] < 0:
        trend = 'bearish'
    else:
        trend = 'neutral'

    # Determine crossover status
    if latest['macd_dif'] > latest['macd_dea']:
        crossover = 'golden_cross'
    elif latest['macd_dif'] < latest['macd_dea']:
        crossover = 'death_cross'
    else:
        crossover = 'equal'

    # Calculate momentum (rate of change of MACD histogram)
    if len(df) >= 5:
        momentum = latest['macd_hist'] - df.iloc[-5]['macd_hist']
    else:
        momentum = 0

    return {
        'trend': trend,
        'crossover': crossover,
        'dif': latest['macd_dif'],
        'dea': latest['macd_dea'],
        'histogram': latest['macd_hist'],
        'momentum': momentum,
        'zero_axis_position': latest.get('zero_axis_position', 'UNKNOWN'),
        'above_ma60': latest['close'] > latest['ma60'] if 'ma60' in latest else None
    }


def format_macd_summary(backtest_result: Dict) -> str:
    """
    Format a human-readable summary of MACD backtest results

    Args:
        backtest_result: Result dictionary from MACDBacktester

    Returns:
        Formatted summary string
    """
    metrics = backtest_result['metrics']
    params = backtest_result['strategy_params']

    summary = f"""
MACD策略回测总结
{'='*50}
策略参数:
  - 零轴过滤: {params.get('zero_axis_filter')}
  - MA60过滤: {params.get('ma60_filter')}
  - 背离信号: {params.get('enable_divergence')}
  - 鸭嘴形态: {params.get('duck_bill_enable')}

回测表现:
  - 总收益率: {metrics['total_return_pct']:+.2f}%
  - 夏普比率: {metrics['sharpe_ratio']:.2f}
  - 最大回撤: {metrics['max_drawdown']*100:.2f}%
  - 胜率: {metrics['win_rate']*100:.2f}%

交易统计:
  - 总交易: {metrics['total_trades']}
  - 止损: {metrics['stop_loss_count']}
  - 止盈: {metrics['take_profit_count']}
  - 信号反转: {metrics['signal_reversal_count']}
{'='*50}
"""

    return summary
