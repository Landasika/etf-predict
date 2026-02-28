"""
纯RSI 0-10仓策略信号生成器

核心逻辑：
- 仅使用RSI(9)单一指标
- 仓位决策基于RSI数值区间（<20, 20-50, 50-59, 59-80等）
- 结合RSI拐头方向（向上/向下）确认买卖信号
- 0-10成渐进式仓位管理
- T+1执行避免未来函数

策略口诀：
"20以下拐头试1仓，上穿20加到3-4；站上50半仓进，59-80重仓拿；
碰80拐头减一半，跌穿50直接空。"

固定参数：
- RSI周期: 9
- 超买线: 80
- 超卖线: 20
- 中位线: 50
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class PureRSISignalGenerator:
    """
    纯RSI 0-10仓策略信号生成器

    核心逻辑：
    1. RSI(9)计算
    2. RSI拐头检测（向上/向下）
    3. RSI区间分类
    4. RSI上穿/下穿关键点位检测
    5. 0-10成仓位决策
    """

    def __init__(self, params: Dict = None):
        self.params = params or self.default_params()

    @staticmethod
    def default_params():
        return {
            'rsi_period': 9,
            'rsi_overbought': 80,
            'rsi_oversold': 20,
            'rsi_middle': 50,
            'slope_threshold': 0.5,  # 斜率阈值，用于判断方向
            'slope_window': 3,  # 斜率计算窗口
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成纯RSI策略信号

        Returns:
            DataFrame with columns:
            - rsi: RSI指标值
            - rsi_slope: RSI斜率
            - rsi_direction: RSI方向 (UP/DOWN/FLAT)
            - rsi_turning_up: RSI向上拐头
            - rsi_turning_down: RSI向下拐头
            - rsi_consecutive_up: 连续向上天数
            - rsi_consecutive_down: 连续向下天数
            - rsi_zone: RSI区间
            - rsi_cross_above_20: RSI上穿20
            - rsi_cross_below_20: RSI下穿20
            - rsi_cross_above_50: RSI上穿50
            - rsi_cross_below_50: RSI下穿50
            - rsi_cross_above_80: RSI上穿80
            - rsi_cross_below_80: RSI下穿80
            - rsi_fast_drop_80_to_50: RSI从80快速跌穿50
            - target_position: 目标仓位 (0-10)
            - exec_position: 执行仓位 (shift(1))
            - position_reason: 仓位说明
        """
        df = df.copy()

        # 计算RSI指标
        df = self._calculate_rsi(df)

        # 检测RSI拐头
        df = self._detect_rsi_turning_points(df)

        # 检测RSI上穿/下穿关键点位
        df = self._detect_rsi_crossings(df)

        # 分类RSI区间
        df = self._classify_rsi_zone(df)

        # 计算目标仓位
        df = self._calculate_target_position(df)

        # 执行仓位（T+1）
        df['exec_position'] = df['target_position'].shift(1).fillna(0)

        return df

    def _calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算RSI(9)指标

        RSI = 100 - (100 / (1 + RS))
        RS = 平均涨幅 / 平均跌幅
        """
        period = self.params['rsi_period']

        # 计算价格变化
        delta = df['close'].diff()

        # 分离涨跌
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # 计算RS和RSI
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        return df

    def _detect_rsi_turning_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        检测RSI拐头（向上/向下）

        使用3日斜率判断方向变化
        """
        slope_window = self.params['slope_window']
        slope_threshold = self.params['slope_threshold']

        # 计算斜率
        df['rsi_slope'] = df['rsi'].diff(slope_window)

        # 判断方向
        df['rsi_direction'] = 'FLAT'
        df.loc[df['rsi_slope'] > slope_threshold, 'rsi_direction'] = 'UP'
        df.loc[df['rsi_slope'] < -slope_threshold, 'rsi_direction'] = 'DOWN'

        # 检测拐头
        prev_direction = df['rsi_direction'].shift(1)
        df['rsi_turning_up'] = (
            (prev_direction.isin(['DOWN', 'FLAT'])) &
            (df['rsi_direction'] == 'UP')
        )
        df['rsi_turning_down'] = (
            (prev_direction.isin(['UP', 'FLAT'])) &
            (df['rsi_direction'] == 'DOWN')
        )

        # 连续向上/向下计数
        df['rsi_consecutive_up'] = 0
        df['rsi_consecutive_down'] = 0

        for i in range(1, len(df)):
            if df.loc[df.index[i], 'rsi_direction'] == 'UP':
                df.loc[df.index[i], 'rsi_consecutive_up'] = \
                    df.loc[df.index[i-1], 'rsi_consecutive_up'] + 1
            elif df.loc[df.index[i], 'rsi_direction'] == 'DOWN':
                df.loc[df.index[i], 'rsi_consecutive_down'] = \
                    df.loc[df.index[i-1], 'rsi_consecutive_down'] + 1

        return df

    def _detect_rsi_crossings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        检测RSI上穿/下穿关键点位（20, 50, 80）
        """
        rsi_prev = df['rsi'].shift(1)

        # 上穿/下穿20
        df['rsi_cross_above_20'] = (rsi_prev <= 20) & (df['rsi'] > 20)
        df['rsi_cross_below_20'] = (rsi_prev >= 20) & (df['rsi'] < 20)

        # 上穿/下穿50
        df['rsi_cross_above_50'] = (rsi_prev <= 50) & (df['rsi'] > 50)
        df['rsi_cross_below_50'] = (rsi_prev >= 50) & (df['rsi'] < 50)

        # 上穿/下穿80
        df['rsi_cross_above_80'] = (rsi_prev <= 80) & (df['rsi'] > 80)
        df['rsi_cross_below_80'] = (rsi_prev >= 80) & (df['rsi'] < 80)

        # 检测从80快速跌穿50（2天内）
        rsi_2_days_ago = df['rsi'].shift(2)
        df['rsi_fast_drop_80_to_50'] = (
            (rsi_2_days_ago >= 80) &
            (df['rsi'] < 50)
        )

        return df

    def _classify_rsi_zone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        分类RSI区间

        DEEP_OVERSOLD: RSI < 20 (极度超卖)
        OVERSOLD: 20 <= RSI < 30 (超卖)
        WEAK: 30 <= RSI < 50 (弱势)
        NEUTRAL: 50 <= RSI < 59 (中性)
        STRONG: 59 <= RSI < 80 (强势)
        OVERBOUGHT: 80 <= RSI < 90 (超买)
        EXTREME: RSI >= 90 (极端)
        """
        conditions = [
            df['rsi'] < 20,
            (df['rsi'] >= 20) & (df['rsi'] < 30),
            (df['rsi'] >= 30) & (df['rsi'] < 50),
            (df['rsi'] >= 50) & (df['rsi'] < 59),
            (df['rsi'] >= 59) & (df['rsi'] < 80),
            (df['rsi'] >= 80) & (df['rsi'] < 90),
            df['rsi'] >= 90
        ]
        choices = ['DEEP_OVERSOLD', 'OVERSOLD', 'WEAK', 'NEUTRAL',
                   'STRONG', 'OVERBOUGHT', 'EXTREME']
        df['rsi_zone'] = np.select(conditions, choices, default='UNKNOWN')

        return df

    def _calculate_target_position(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        根据RSI规则计算目标仓位(0-10)

        核心规则：
        1. 紧急清仓（0仓）：
           - RSI从80快速跌穿50（2天内）
           - RSI跌破50且拐头向下

        2. 空仓观望（0仓）：
           - RSI<20且持续向下

        3. 极轻仓试错（1-2仓）：
           - RSI<20且首次拐头向上（未上穿20）

        4. 轻仓进场（3-4仓）：
           - RSI上穿20 → 3仓
           - RSI在20-50区间且持续向上 → 4仓

        5. 半仓加仓（5-6仓）：
           - RSI站上50且站稳1天以上 → 5仓
           - RSI进入59-80区间 → 6仓

        6. 重仓持有（7-8仓）：
           - RSI在59-80区间且连续2天向上 → 7仓
           - RSI在65-75健康区 → 8仓

        7. 满仓（9-10仓）：
           - RSI在55-75且连续3天向上 → 9仓
           - RSI在60-70且连续5天向上 → 10仓
        """
        df['target_position'] = 0
        df['position_reason'] = ''

        for idx in range(len(df)):
            if idx < 9:  # 需要至少9天RSI数据
                continue

            row = df.iloc[idx]
            rsi = row['rsi']
            rsi_direction = row['rsi_direction']
            rsi_turning_up = row['rsi_turning_up']
            rsi_turning_down = row['rsi_turning_down']
            rsi_consecutive_up = row['rsi_consecutive_up']
            rsi_zone = row['rsi_zone']

            cross_above_20 = row['rsi_cross_above_20']
            cross_above_50 = row['rsi_cross_above_50']
            cross_below_50 = row['rsi_cross_below_50']
            fast_drop_80_to_50 = row['rsi_fast_drop_80_to_50']

            current_position = df.at[df.index[idx], 'target_position']

            # ========== 优先级1: 紧急清仓 ==========
            if fast_drop_80_to_50:
                df.at[df.index[idx], 'target_position'] = 0
                df.at[df.index[idx], 'position_reason'] = 'RSI从80快速跌穿50，紧急清仓'
                continue

            if cross_below_50 and rsi_turning_down:
                df.at[df.index[idx], 'target_position'] = 0
                df.at[df.index[idx], 'position_reason'] = 'RSI跌破50且拐头向下，清仓'
                continue

            # ========== 优先级2: 空仓观望 ==========
            if rsi < 20 and rsi_direction == 'DOWN' and rsi_consecutive_up == 0:
                df.at[df.index[idx], 'target_position'] = 0
                df.at[df.index[idx], 'position_reason'] = 'RSI极度超卖且持续向下，空仓观望'
                continue

            # ========== 优先级3: 极轻仓试错（1-2仓）==========
            if rsi < 20 and rsi_turning_up and not cross_above_20:
                # RSI<20且首次拐头向上，但未上穿20
                if current_position == 0:
                    df.at[df.index[idx], 'target_position'] = 1
                    df.at[df.index[idx], 'position_reason'] = 'RSI极度超卖拐头向上，试错1仓'
                elif current_position == 1 and rsi_direction == 'UP':
                    # 次日确认继续向上，加到2仓
                    df.at[df.index[idx], 'target_position'] = 2
                    df.at[df.index[idx], 'position_reason'] = 'RSI继续向上，加仓到2仓'
                continue

            # ========== 优先级4: 轻仓进场（3-4仓）==========
            if cross_above_20:
                df.at[df.index[idx], 'target_position'] = 3
                df.at[df.index[idx], 'position_reason'] = 'RSI上穿20，建仓3成'
                continue

            if 20 <= rsi < 50 and rsi_direction == 'UP' and rsi_consecutive_up >= 1:
                df.at[df.index[idx], 'target_position'] = 4
                df.at[df.index[idx], 'position_reason'] = 'RSI在20-50区间且持续向上，持仓4成'
                continue

            # ========== 优先级5: 半仓加仓（5-6仓）==========
            if cross_above_50:
                df.at[df.index[idx], 'target_position'] = 5
                df.at[df.index[idx], 'position_reason'] = 'RSI站上50，建仓5成'
                continue

            if rsi >= 50 and rsi_zone == 'NEUTRAL' and rsi_consecutive_up >= 1:
                df.at[df.index[idx], 'target_position'] = 5
                df.at[df.index[idx], 'position_reason'] = 'RSI站稳50，持仓5成'
                continue

            if 59 <= rsi < 80 and rsi_direction == 'UP':
                df.at[df.index[idx], 'target_position'] = 6
                df.at[df.index[idx], 'position_reason'] = 'RSI进入59-80强势区，持仓6成'
                continue

            # ========== 优先级6: 重仓持有（7-8仓）==========
            if 59 <= rsi < 80 and rsi_consecutive_up >= 2:
                df.at[df.index[idx], 'target_position'] = 7
                df.at[df.index[idx], 'position_reason'] = 'RSI在59-80区间且连续向上，持仓7成'
                continue

            if 65 <= rsi <= 75 and rsi_direction == 'UP':
                df.at[df.index[idx], 'target_position'] = 8
                df.at[df.index[idx], 'position_reason'] = 'RSI在65-75健康区，持仓8成'
                continue

            # ========== 优先级7: 满仓（9-10仓）==========
            if 55 <= rsi <= 75 and rsi_consecutive_up >= 3:
                df.at[df.index[idx], 'target_position'] = 9
                df.at[df.index[idx], 'position_reason'] = 'RSI在健康区且连续3天向上，持仓9成'
                continue

            if 60 <= rsi <= 70 and rsi_consecutive_up >= 5:
                df.at[df.index[idx], 'target_position'] = 10
                df.at[df.index[idx], 'position_reason'] = 'RSI在强势健康区且连续5天向上，满仓10成'
                continue

            # ========== 默认: 持有或减仓 ==========
            if rsi >= 80 and rsi_turning_down and current_position > 5:
                # 碰80拐头向下，减仓一半
                new_position = max(current_position // 2, 3)
                df.at[df.index[idx], 'target_position'] = new_position
                df.at[df.index[idx], 'position_reason'] = f'RSI碰80拐头向下，减仓到{new_position}成'
            elif current_position > 0:
                # 保持当前仓位
                df.at[df.index[idx], 'target_position'] = current_position
                df.at[df.index[idx], 'position_reason'] = f'保持当前仓位{current_position}成'

        # 确保仓位是有效离散值
        valid_positions = list(range(11))  # 0-10
        df['target_position'] = df['target_position'].apply(
            lambda x: int(x) if int(x) in valid_positions else 0
        )

        return df
