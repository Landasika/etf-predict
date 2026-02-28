"""
Pytest configuration and shared fixtures
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def sample_ohlcv_data():
    """生成模拟 OHLCV 数据"""
    np.random.seed(42)
    n = 500
    price = 10.0
    prices = [price]
    for _ in range(n - 1):
        price = price * (1 + np.random.randn() * 0.02)
        prices.append(price)
    prices = np.array(prices)

    df = pd.DataFrame({
        'trade_date': pd.date_range('2023-01-01', periods=n),
        'open': prices * (1 + np.random.randn(n) * 0.005),
        'high': prices * (1 + abs(np.random.randn(n)) * 0.01),
        'low': prices * (1 - abs(np.random.randn(n)) * 0.01),
        'close': prices,
        'vol': np.random.randint(1000000, 10000000, n)
    })
    df['trade_date'] = df['trade_date'].dt.strftime('%Y%m%d')
    return df


@pytest.fixture
def macd_kdj_params():
    """MACD+KDJ 策略参数"""
    return {
        'macd_fast': 8, 'macd_slow': 17, 'macd_signal': 5,
        'kdj_n': 9, 'kdj_m1': 3, 'kdj_m2': 3,
        'kdj_overbought': 80, 'kdj_severe_overbought': 85,
        'kdj_oversold': 20, 'kdj_low_cross': 30,
        'kdj_j_overbought': 100, 'kdj_j_severe': 110,
        'enable_divergence': True
    }
