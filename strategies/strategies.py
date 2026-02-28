"""
MACD Strategy Configurations

Predefined strategy parameter sets for MACD aggressive strategy.
"""

from typing import Dict
from .signals import MACDSignalGenerator


def get_strategy_params(strategy_name: str) -> Dict:
    """
    Get strategy parameters by name

    Args:
        strategy_name: Name of the strategy (default/aggressive/conservative)

    Returns:
        Dictionary of strategy parameters
    """
    strategies = {
        'default': MACDSignalGenerator.default_params(),

        'aggressive': {
            # Zero-axis: More lenient
            'zero_axis_filter': True,
            'require_zero_above': False,  # Allow buys below zero

            # Period resonance: Disabled
            'enable_resonance': False,
            'major_period': 'weekly',
            'minor_period': 'daily',

            # MA60: More lenient
            'ma60_filter': True,
            'ma60_tolerance': 0.05,  # 5% tolerance

            # Divergence: More aggressive
            'enable_divergence': True,
            'divergence_confirm': False,  # No confirmation needed
            'min_divergence_count': 1,

            # Signal strength: No volume filter
            'volume_confirm': False,
            'volume_increase_min': 0.2,
            'volume_increase_max': 0.8,

            # Patterns: All enabled
            'duck_bill_enable': True,
            'inverted_duck_enable': True
        },

        'conservative': {
            # Zero-axis: Strict
            'zero_axis_filter': True,
            'require_zero_above': True,  # Must be above zero

            # Period resonance: Enabled
            'enable_resonance': False,  # Requires multi-timeframe data
            'major_period': 'weekly',
            'minor_period': 'daily',

            # MA60: Strict
            'ma60_filter': True,
            'ma60_tolerance': 0.01,  # 1% tolerance

            # Divergence: Conservative
            'enable_divergence': True,
            'divergence_confirm': True,  # Must confirm
            'min_divergence_count': 2,  # At least 2 occurrences

            # Signal strength: Require volume confirmation
            'volume_confirm': True,
            'volume_increase_min': 0.3,
            'volume_increase_max': 0.5,

            # Patterns: All enabled
            'duck_bill_enable': True,
            'inverted_duck_enable': True
        },

        'trend_following': {
            # Focus on trend following with zero-axis
            'zero_axis_filter': True,
            'require_zero_above': True,

            # Period resonance
            'enable_resonance': False,
            'major_period': 'weekly',
            'minor_period': 'daily',

            # MA60: Important filter
            'ma60_filter': True,
            'ma60_tolerance': 0.02,

            # Divergence: Disabled (focus on trend)
            'enable_divergence': False,
            'divergence_confirm': True,
            'min_divergence_count': 2,

            # Volume: No filter
            'volume_confirm': False,
            'volume_increase_min': 0.3,
            'volume_increase_max': 0.5,

            # Patterns: Only duck bill
            'duck_bill_enable': True,
            'inverted_duck_enable': False
        },

        'reversal': {
            # Focus on reversal via divergence
            'zero_axis_filter': False,
            'require_zero_above': False,

            # Period resonance
            'enable_resonance': False,
            'major_period': 'weekly',
            'minor_period': 'daily',

            # MA60: Less important
            'ma60_filter': False,
            'ma60_tolerance': 0.02,

            # Divergence: Main signal
            'enable_divergence': True,
            'divergence_confirm': True,
            'min_divergence_count': 2,

            # Volume: Require confirmation
            'volume_confirm': True,
            'volume_increase_min': 0.4,
            'volume_increase_max': 0.6,

            # Patterns: Disabled
            'duck_bill_enable': False,
            'inverted_duck_enable': False
        }
    }

    return strategies.get(strategy_name, strategies['default'])


def print_available_strategies():
    """Print all available strategies with descriptions"""
    strategies = {
        'default': 'Default balanced strategy with all features enabled',
        'aggressive': 'Aggressive strategy with more signals, less filtering',
        'conservative': 'Conservative strategy with strict filters and confirmations',
        'trend_following': 'Focus on trend following, zero-axis and MA60',
        'reversal': 'Focus on catching reversals via divergence patterns'
    }

    print("Available MACD Strategies:")
    print("=" * 60)
    for name, desc in strategies.items():
        print(f"  {name:20s} - {desc}")
    print("=" * 60)
