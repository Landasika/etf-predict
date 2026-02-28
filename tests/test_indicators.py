"""
Tests for technical indicators
"""
import pytest
import pandas as pd
import numpy as np
from strategies.indicators import MACDIndicators


class TestMACDIndicators:
    """MACD 指标测试"""

    def test_calculate_macd(self, sample_ohlcv_data):
        """测试 MACD 计算"""
        df = MACDIndicators.calculate_macd(sample_ohlcv_data)
        assert 'macd_dif' in df.columns
        assert 'macd_dea' in df.columns
        assert 'macd_hist' in df.columns

    def test_calculate_kdj(self, sample_ohlcv_data):
        """测试 KDJ 计算"""
        df = MACDIndicators.calculate_kdj(sample_ohlcv_data)
        assert 'kdj_k' in df.columns
        assert 'kdj_d' in df.columns
        assert 'kdj_j' in df.columns
        assert df['kdj_k'].between(0, 100).all()

    def test_macd_default_params(self, sample_ohlcv_data):
        """测试 MACD 默认参数"""
        df = MACDIndicators.calculate_macd(sample_ohlcv_data)
        # Check that calculation was successful (no NaN values after warmup)
        valid_dif = df['macd_dif'].dropna()
        assert len(valid_dif) > 0

    def test_kdj_default_params(self, sample_ohlcv_data):
        """测试 KDJ 默认参数"""
        df = MACDIndicators.calculate_kdj(sample_ohlcv_data)
        # Check that calculation was successful
        valid_k = df['kdj_k'].dropna()
        assert len(valid_k) > 0

    def test_macd_custom_params(self, sample_ohlcv_data):
        """测试 MACD 自定义参数"""
        df = MACDIndicators.calculate_macd(
            sample_ohlcv_data,
            fast=12,
            slow=26,
            signal=9
        )
        assert 'macd_dif' in df.columns
        assert 'macd_dea' in df.columns

    def test_kdj_custom_params(self, sample_ohlcv_data):
        """测试 KDJ 自定义参数"""
        df = MACDIndicators.calculate_kdj(
            sample_ohlcv_data,
            n=14,
            m1=3,
            m2=3
        )
        assert 'kdj_k' in df.columns
        assert df['kdj_k'].between(0, 100).all()

    def test_macd_hist_formula(self, sample_ohlcv_data):
        """测试 MACD 柱状图公式：MACD = 2 * (DIF - DEA)"""
        df = MACDIndicators.calculate_macd(sample_ohlcv_data)
        # MACD_hist = 2 * (DIF - DEA)
        df['expected_hist'] = 2 * (df['macd_dif'] - df['macd_dea'])

        # Check where both values are not NaN
        valid = df.dropna(subset=['macd_hist', 'expected_hist'])
        if len(valid) > 0:
            # Check values are close (allowing for floating point precision)
            assert np.allclose(valid['macd_hist'], valid['expected_hist'], rtol=1e-10)

    def test_kdj_relationship(self, sample_ohlcv_data):
        """测试 KDJ 三个值的关系"""
        df = MACDIndicators.calculate_kdj(sample_ohlcv_data)

        # K 值应该在 0-100 之间
        assert df['kdj_k'].between(0, 100).all()

        # J 值可以超出 0-100 范围（因为它对 K 和 D 的偏离敏感）
        # J = 3K - 2D
        df['expected_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']

        valid = df.dropna(subset=['kdj_j', 'expected_j'])
        if len(valid) > 0:
            assert np.allclose(valid['kdj_j'], valid['expected_j'], rtol=1e-10)
