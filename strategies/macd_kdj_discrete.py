"""
MACD + KDJ 离散仓位系统 2.0 信号生成器

核心逻辑：
1. MACD判断趋势方向（BULL/BEAR）
2. KDJ确定0-10成离散仓位
3. 严格防未来函数（信号和仓位都shift(1)）
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class MACDKDJDiscreteSignalGenerator:
    """
    MACD + KDJ 离散仓位系统 2.0 信号生成器

    核心逻辑：
    1. MACD判断趋势方向（BULL/BEAR）
    2. KDJ确定0-10成离散仓位
    3. 严格防未来函数（信号和仓位都shift(1)）
    """

    def __init__(self, params: Dict = None):
        self.params = params or self.default_params()

    @staticmethod
    def default_params():
        return {
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'kdj_n': 9,
            'kdj_m1': 3,
            'kdj_m2': 3
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成离散仓位信号

        Returns:
            DataFrame with columns:
            - trend: MACD趋势 (BULL/BEAR)
            - kdj_zone: KDJ区间 (A/B/C/D/E)
            - golden_cross: KDJ金叉
            - dead_cross: KDJ死叉
            - k_slope_up: K上升
            - k_slope_dn: K下降
            - target_position: 目标仓位 (0-10)
            - exec_position: 执行仓位 (shift(1))
            - signal_reason: 信号说明
        """
        df = df.copy()

        # 计算指标
        df = self._calculate_indicators(df)

        # 判断趋势
        df = self._determine_trend(df)

        # 判断KDJ区间
        df = self._classify_kdj_zone(df)

        # 检测交叉
        df = self._detect_crosses(df)

        # 计算目标仓位
        df = self._calculate_target_position(df)

        # 执行仓位（T+1）
        df['exec_position'] = df['target_position'].shift(1).fillna(0)

        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算MACD和KDJ指标"""
        # MACD(12,26,9)
        ema_fast = df['close'].ewm(span=self.params['macd_fast'], adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.params['macd_slow'], adjust=False).mean()

        df['macd_dif'] = ema_fast - ema_slow
        df['macd_dea'] = df['macd_dif'].ewm(span=self.params['macd_signal'], adjust=False).mean()
        df['macd_hist'] = 2 * (df['macd_dif'] - df['macd_dea'])

        # KDJ(9,3,3)
        n = self.params['kdj_n']
        m1 = self.params['kdj_m1']
        m2 = self.params['kdj_m2']

        # RSV计算
        low_list = df['low'].rolling(window=n, min_periods=1).min()
        high_list = df['high'].rolling(window=n, min_periods=1).max()

        # 避免除零
        high_low_diff = high_list - low_list
        high_low_diff = high_low_diff.replace(0, np.finfo(float).eps)

        rsv = (df['close'] - low_list) / high_low_diff * 100

        # K, D, J 计算（使用EMA，即pandas的ewm）
        df['kdj_k'] = rsv.ewm(com=m1-1, adjust=False).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=m2-1, adjust=False).mean()
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']

        return df

    def _determine_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        MACD趋势判断

        BULL: DIF > DEA (允许做多，上限10成)
        BEAR: DIF <= DEA (空仓，上限0成)
        """
        df['trend'] = df.apply(
            lambda row: 'BULL' if row['macd_dif'] > row['macd_dea'] else 'BEAR',
            axis=1
        )
        return df

    def _classify_kdj_zone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        KDJ区间划分

        A区: K < 20 (超卖区)
        B区: 20 ≤ K < 50 (弱势修复区)
        C区: 50 ≤ K < 80 (强势区/主升)
        D区: 80 ≤ K < 90 (高位区)
        E区: K ≥ 90 (极高位)
        """
        conditions = [
            df['kdj_k'] < 20,
            (df['kdj_k'] >= 20) & (df['kdj_k'] < 50),
            (df['kdj_k'] >= 50) & (df['kdj_k'] < 80),
            (df['kdj_k'] >= 80) & (df['kdj_k'] < 90),
            df['kdj_k'] >= 90
        ]
        choices = ['A', 'B', 'C', 'D', 'E']
        df['kdj_zone'] = np.select(conditions, choices, default='Unknown')
        return df

    def _detect_crosses(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        检测KDJ金叉和死叉，以及K线斜率

        金叉: K从下向上穿过D
        死叉: K从上向下穿过D
        """
        # 前一日数据
        k_prev = df['kdj_k'].shift(1)
        d_prev = df['kdj_d'].shift(1)

        # 金叉判断
        df['golden_cross'] = (k_prev <= d_prev) & (df['kdj_k'] > df['kdj_d'])

        # 死叉判断
        df['dead_cross'] = (k_prev >= d_prev) & (df['kdj_k'] < df['kdj_d'])

        # K线斜率
        df['k_slope_up'] = df['kdj_k'] > k_prev
        df['k_slope_dn'] = df['kdj_k'] < k_prev

        return df

    def _calculate_target_position(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        根据离散仓位表计算目标仓位

        核心逻辑：MACD=BULL时，根据KDJ区间和交叉状态查表
        MACD=BEAR时直接空仓
        """
        # 初始化目标仓位为0
        df['target_position'] = 0
        df['signal_reason'] = ''

        # BEAR趋势直接空仓
        bear_mask = df['trend'] == 'BEAR'
        df.loc[bear_mask, 'target_position'] = 0
        df.loc[bear_mask, 'signal_reason'] = 'MACD空头趋势，空仓'

        # BULL趋势：根据KDJ查表
        bull_mask = ~bear_mask

        # A区：K < 20
        zone_a = bull_mask & (df['kdj_k'] < 20)
        golden_cross_a = zone_a & df['golden_cross']
        df.loc[golden_cross_a, 'target_position'] = 8
        df.loc[golden_cross_a, 'signal_reason'] = 'A区金叉：建仓8成'
        df.loc[zone_a & ~golden_cross_a, 'target_position'] = 5
        df.loc[zone_a & ~golden_cross_a, 'signal_reason'] = 'A区超卖：建仓5成'

        # B区：20-50
        zone_b = bull_mask & (df['kdj_k'] >= 20) & (df['kdj_k'] < 50)
        up_b = zone_b & df['k_slope_up'] & (df['kdj_k'] > df['kdj_d'])
        df.loc[up_b, 'target_position'] = 7
        df.loc[up_b, 'signal_reason'] = 'B区上升：建仓7成'
        df.loc[zone_b & ~up_b, 'target_position'] = 4
        df.loc[zone_b & ~up_b, 'signal_reason'] = 'B区下降：建仓4成'

        # C区：50-80
        zone_c = bull_mask & (df['kdj_k'] >= 50) & (df['kdj_k'] < 80)
        up_c = zone_c & df['k_slope_up'] & (df['kdj_k'] > df['kdj_d'])
        dead_c = zone_c & df['dead_cross']
        df.loc[up_c, 'target_position'] = 10
        df.loc[up_c, 'signal_reason'] = 'C区主升：满仓10成'
        df.loc[zone_c & dead_c, 'target_position'] = 5
        df.loc[zone_c & dead_c, 'signal_reason'] = 'C区死叉：减仓5成'
        df.loc[zone_c & ~(up_c | dead_c), 'target_position'] = 7
        df.loc[zone_c & ~(up_c | dead_c), 'signal_reason'] = 'C区回调：持有7成'

        # D区：80-90
        zone_d = bull_mask & (df['kdj_k'] >= 80) & (df['kdj_k'] < 90)
        up_d = zone_d & df['k_slope_up'] & (df['kdj_k'] > df['kdj_d'])
        df.loc[up_d, 'target_position'] = 6
        df.loc[up_d, 'signal_reason'] = 'D区上升：建仓6成'
        df.loc[zone_d & ~up_d, 'target_position'] = 3
        df.loc[zone_d & ~up_d, 'signal_reason'] = 'D区下降：建仓3成'

        # E区：K ≥ 90
        zone_e = bull_mask & (df['kdj_k'] >= 90)
        still_rising = zone_e & df['k_slope_up'] & ~df['dead_cross']
        drop_e = zone_e & ((df['kdj_k'] < 80) | df['dead_cross'] | df['k_slope_dn'])
        df.loc[still_rising, 'target_position'] = 3
        df.loc[still_rising, 'signal_reason'] = 'E区极高位：持有3成'
        df.loc[drop_e, 'target_position'] = 1
        df.loc[drop_e, 'signal_reason'] = 'E区回落：建仓1成'

        # K从E区跌破80：清仓
        k_prev = df['kdj_k'].shift(1)
        drop_from_peak = k_prev >= 90
        df.loc[drop_from_peak & (df['kdj_k'] < 80), 'target_position'] = 0
        df.loc[drop_from_peak & (df['kdj_k'] < 80), 'signal_reason'] = 'E区跌破80：清仓'

        # 确保仓位是离散值
        valid_positions = [0, 1, 3, 4, 5, 6, 7, 8, 10]
        df['target_position'] = df['target_position'].apply(
            lambda x: int(x) if int(x) in valid_positions else 0
        )

        return df
