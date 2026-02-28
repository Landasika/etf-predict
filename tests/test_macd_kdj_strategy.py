"""
Tests for MACD+KDJ fusion strategy
"""
import pytest
import pandas as pd
from strategies.signals import MACDKDJSignalGenerator


class TestMACDKDJSignalGenerator:
    """MACD+KDJ 信号生成器测试"""

    def test_initialization(self):
        """测试初始化"""
        generator = MACDKDJSignalGenerator()
        assert 'macd_fast' in generator.params
        assert 'kdj_n' in generator.params
        assert generator.params['macd_fast'] == 8

    def test_default_params_has_divergence(self):
        """测试默认参数包含背离检测"""
        params = MACDKDJSignalGenerator.default_params()
        assert 'enable_divergence' in params
        assert params['enable_divergence'] == True
        assert 'divergence_confirm' in params
        assert 'min_divergence_count' in params

    def test_generate_signals_returns_required_columns(self, sample_ohlcv_data):
        """测试信号生成返回必需列"""
        generator = MACDKDJSignalGenerator()
        df = generator.generate_signals(sample_ohlcv_data)

        required = ['signal_type', 'macd_level', 'kdj_factor',
                   'fusion_level', 'kdj_position_cap', 'kdj_daily_add_cap']
        for col in required:
            assert col in df.columns, f"Missing required column: {col}"

    def test_kdj_indicators_calculated(self, sample_ohlcv_data):
        """测试 KDJ 指标计算"""
        generator = MACDKDJSignalGenerator()
        df = generator.generate_signals(sample_ohlcv_data)

        assert 'kdj_k' in df.columns
        assert 'kdj_d' in df.columns
        assert 'kdj_j' in df.columns
        assert df['kdj_k'].between(0, 100).all()

    def test_fusion_level_in_valid_range(self, sample_ohlcv_data):
        """测试融合强度在有效范围内"""
        generator = MACDKDJSignalGenerator()
        df = generator.generate_signals(sample_ohlcv_data)

        buy_signals = df[df['signal_type'] == 'BUY']
        fusion = buy_signals['fusion_level'].dropna()
        if len(fusion) > 0:
            assert (fusion >= 1).all() and (fusion <= 10).all()

    def test_position_cap_is_integer(self, sample_ohlcv_data):
        """测试仓位上限为整数"""
        generator = MACDKDJSignalGenerator()
        df = generator.generate_signals(sample_ohlcv_data)

        caps = df['kdj_position_cap'].dropna()
        if len(caps) > 0:
            assert caps.apply(lambda x: x == int(x)).all()

    def test_custom_params_override(self):
        """测试自定义参数覆盖"""
        # The strategy replaces params entirely when custom ones are provided,
        # so we need to provide all required params or merge with defaults
        default_params = MACDKDJSignalGenerator.default_params()
        custom_params = default_params.copy()
        custom_params['macd_fast'] = 12
        custom_params['kdj_n'] = 14

        generator = MACDKDJSignalGenerator(custom_params)
        assert generator.params['macd_fast'] == 12
        assert generator.params['kdj_n'] == 14
        # Default values should still be present
        assert generator.params['macd_slow'] == 17
