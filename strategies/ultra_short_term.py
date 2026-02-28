"""
超短线交易策略模块

包含：
1. 隔日T+0策略：基于日线数据，但持仓周期1-3天
2. 日内波动策略：利用开盘缺口、尾盘效应等
3. 量价配合策略：结合成交量突变的短线信号
"""

from .signals import MACDSignalGenerator
from typing import Dict
import pandas as pd
import numpy as np


class UltraShortTermSignalGenerator(MACDSignalGenerator):
    """
    超短线信号生成器

    特点：
    1. 更敏感的参数
    2. 更短的持仓周期（1-3天）
    3. 更严格的止损（3-5%）
    4. 更快的止盈（5-10%）
    """

    def __init__(self, params: Dict = None):
        # 默认使用超短线参数
        default_params = {
            # MACD参数 - 使用更快的参数
            'fast_period': 8,    # 默认12，改为8更敏感
            'slow_period': 16,   # 默认26，改为16
            'signal_period': 4,  # 默认9，改为4

            # KDJ参数 - 保持默认
            'kdj_n': 9,
            'kdj_m1': 3,
            'kdj_m2': 3,

            # 买入条件 - 非常宽松
            'zero_axis_filter': False,      # 不要求在零轴上方
            'require_zero_above': False,
            'ma60_filter': False,           # 不使用MA60过滤
            'enable_divergence': False,     # 不使用背离（太慢）

            # 卖出条件 - 非常严格
            'volume_confirm': True,         # 需要成交量确认
            'volume_increase_min': 0.5,     # 至少放量50%

            # 图形形态
            'duck_bill_enable': False,      # 不使用鸭嘴（太慢）
            'inverted_duck_enable': False,

            # 超短线特定参数
            'use_rsi': True,                # 使用RSI
            'rsi_period': 7,                # 7日RSI
            'rsi_oversold': 25,             # RSI超卖线
            'rsi_overbought': 75,           # RSI超买线
        }
        if params:
            default_params.update(params)
        super().__init__(default_params)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成超短线交易信号"""
        # 先生成基础MACD信号
        df = super().generate_signals(df)

        # 添加超短线指标
        df = self._add_ultra_short_indicators(df)

        # 生成超短线信号
        df = self._generate_ultra_short_signals(df)

        return df

    def _add_ultra_short_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加超短线特定指标"""

        # RSI指标
        if self.params.get('use_rsi'):
            period = self.params.get('rsi_period', 7)
            df['rsi'] = self._calculate_rsi(df['close'], period)

        # 5日涨跌幅
        df['pct_change_5'] = df['close'].pct_change(5) * 100

        # 3日涨跌幅
        df['pct_change_3'] = df['close'].pct_change(3) * 100

        # 成交量变化
        df['volume_ratio'] = df['vol'] / df['vol'].rolling(5).mean()

        # 开盘跳空
        df['gap_up'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        df['gap_down'] = (df['close'].shift(1) - df['open']) / df['close'].shift(1)

        # 尾盘强度（收盘价相对于当日最高最低价的位置）
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 0.0001)

        return df

    def _generate_ultra_short_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成超短线交易信号"""

        # 初始化信号列
        df['ultra_short_signal'] = 0
        df['ultra_short_strength'] = 0.0

        for i in range(20, len(df)):
            current = df.iloc[i]
            prev = df.iloc[i-1]

            buy_score = 0
            sell_score = 0
            signal_type = 'HOLD'

            # === 买入条件 ===

            # 1. RSI超卖
            if self.params.get('use_rsi') and current['rsi'] < self.params.get('rsi_oversold', 25):
                buy_score += 3
                signal_type = 'BUY'

            # 2. 短期暴跌（3日跌超5%）
            if current['pct_change_3'] < -5:
                buy_score += 2
                signal_type = 'BUY'

            # 3. MACD金叉（敏感参数）
            if (prev['macd_dif'] <= prev['macd_dea'] and
                current['macd_dif'] > current['macd_dea']):
                buy_score += 2
                signal_type = 'BUY'

            # 4. 底部放量
            if (current['volume_ratio'] > 1.5 and
                current['close'] > current['open'] and
                current['pct_change_5'] < -3):
                buy_score += 2
                signal_type = 'BUY'

            # 5. 跳空低开高走
            if (current['gap_down'] > 0.01 and
                current['close'] > current['open'] and
                current['close_position'] > 0.6):
                buy_score += 2
                signal_type = 'BUY'

            # 6. 连续下跌后反弹
            if (current['close'] > current['open'] and
                current['pct_change_5'] < -5 and
                df.iloc[i-1]['close'] < df.iloc[i-1]['open']):
                buy_score += 1

            # === 卖出条件 ===

            # 1. RSI超买
            if self.params.get('use_rsi') and current['rsi'] > self.params.get('rsi_overbought', 75):
                sell_score += 3
                signal_type = 'SELL'

            # 2. 短期暴涨（3日涨超8%）
            if current['pct_change_3'] > 8:
                sell_score += 3
                signal_type = 'SELL'

            # 3. MACD死叉
            if (prev['macd_dif'] >= prev['macd_dea'] and
                current['macd_dif'] < current['macd_dea']):
                sell_score += 2
                signal_type = 'SELL'

            # 4. 高位放量滞涨
            if (current['volume_ratio'] > 2.0 and
                current['pct_change_3'] > 5 and
                current['close_position'] < 0.3):
                sell_score += 2
                signal_type = 'SELL'

            # 5. 尾盘走弱
            if (current['close_position'] < 0.2 and
                current['volume_ratio'] > 1.2):
                sell_score += 1

            # 6. 5日连涨后高位十字星
            if (current['pct_change_5'] > 8 and
                abs(current['close'] - current['open']) / current['open'] < 0.01):
                sell_score += 2
                signal_type = 'SELL'

            # 计算最终信号
            total_score = buy_score - sell_score

            if total_score >= 3:
                df.loc[df.index[i], 'ultra_short_signal'] = 1
                df.loc[df.index[i], 'ultra_short_strength'] = min(total_score / 5.0, 1.0)
            elif total_score <= -3:
                df.loc[df.index[i], 'ultra_short_signal'] = -1
                df.loc[df.index[i], 'ultra_short_strength'] = min(abs(total_score) / 5.0, 1.0)

        return df

    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi


# 超短线策略配置
ULTRA_SHORT_TERM_PARAMS = {
    'scalping_day': {  # 日内剥头皮
        'description': '持仓1-2天，快进快出',
        'fast_period': 6,
        'slow_period': 12,
        'signal_period': 3,
        'stop_loss_pct': 0.03,   # 3%止损
        'take_profit_pct1': 0.05,  # 5%第一止盈
        'take_profit_pct2': 0.08,  # 8%第二止盈
        'max_holding_days': 2,
    },
    'swing_3days': {  # 3日波段
        'description': '持仓2-4天，捕捉短期波动',
        'fast_period': 8,
        'slow_period': 16,
        'signal_period': 4,
        'stop_loss_pct': 0.05,   # 5%止损
        'take_profit_pct1': 0.08,  # 8%第一止盈
        'take_profit_pct2': 0.12,  # 12%第二止盈
        'max_holding_days': 4,
    },
    'gap_trading': {  # 缺口交易
        'description': '利用开盘缺口交易',
        'fast_period': 8,
        'slow_period': 16,
        'signal_period': 4,
        'stop_loss_pct': 0.04,
        'take_profit_pct1': 0.06,
        'take_profit_pct2': 0.10,
        'max_holding_days': 3,
        'use_gap_signals': True,
    }
}


def get_ultra_short_params(style: str = 'scalping_day') -> Dict:
    """获取超短线策略参数"""
    return ULTRA_SHORT_TERM_PARAMS.get(style, ULTRA_SHORT_TERM_PARAMS['scalping_day'])
