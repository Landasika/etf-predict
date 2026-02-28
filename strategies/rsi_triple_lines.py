"""
RSI三线金叉死叉0-10仓策略信号生成器

核心逻辑：
- 三根RSI线：RSI1(6)短期、RSI2(12)中期、RSI3(24)长期
- 金叉买入、死叉卖出、多空排列定趋势
- 0-10成精准仓位管理

策略口诀：
"20以下拐头试1仓，上穿中期加到3-4；上穿长期半仓进，
多头排列+59-80重仓拿；下穿中期减一半，下穿长期清仓走，空头排列绝不留。"
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class RSITripleLinesSignalGenerator:
    """
    RSI三线金叉死叉策略信号生成器

    核心逻辑：
    1. 计算三根不同周期的RSI线
    2. 检测RSI1上穿/下穿RSI2和RSI3（金叉/死叉）
    3. 判断三线多空排列状态
    4. 根据金叉梯度、排列状态、数值区间计算0-10仓位
    """

    def __init__(self, params: Dict = None):
        self.params = params or self.default_params()

    @staticmethod
    def default_params():
        return {
            'rsi1_period': 6,   # 短期RSI
            'rsi2_period': 12,  # 中期RSI
            'rsi3_period': 24,  # 长期RSI
            'rsi_overbought': 80,
            'rsi_oversold': 20,
            'rsi_middle': 50,
            'slope_threshold': 0.5,
            'slope_window': 3,
            'line_glued_threshold': 5,  # 三线黏合判断阈值
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成RSI三线策略信号

        Returns:
            DataFrame with columns:
            - rsi1, rsi2, rsi3: 三根RSI线
            - rsi1_cross_above_rsi2: RSI1上穿RSI2（金叉）
            - rsi1_cross_below_rsi2: RSI1下穿RSI2（死叉）
            - rsi1_cross_above_rsi3: RSI1上穿RSI3（二次金叉）
            - rsi1_cross_below_rsi3: RSI1下穿RSI3（二次死叉）
            - triple_alignment: 多空排列状态（BULLISH/BEARISH/NEUTRAL/GLUED）
            - rsi1_direction: RSI1方向（UP/DOWN/FLAT）
            - rsi1_turning_up: RSI1向上拐头
            - rsi1_turning_down: RSI1向下拐头
            - rsi1_consecutive_up: RSI1连续向上天数
            - target_position: 目标仓位 (0-10)
            - exec_position: 执行仓位 (shift(1))
            - position_reason: 仓位说明
        """
        df = df.copy()

        # 计算三根RSI线
        df = self._calculate_triple_rsi(df)

        # 检测金叉死叉
        df = self._detect_crossings(df)

        # 判断多空排列
        df = self._detect_alignment(df)

        # 检测RSI1方向和拐头
        df = self._detect_rsi1_direction(df)

        # 计算目标仓位
        df = self._calculate_target_position(df)

        # 执行仓位（T+1）
        df['exec_position'] = df['target_position'].shift(1).fillna(0)

        return df

    def _calculate_triple_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算三根不同周期的RSI线"""
        for period_key in ['rsi1_period', 'rsi2_period', 'rsi3_period']:
            period = self.params[period_key]
            col_name = period_key.replace('_period', '')  # rsi1, rsi2, rsi3

            # 计算RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / (loss + 1e-10)
            df[col_name] = 100 - (100 / (1 + rs))

        return df

    def _detect_crossings(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测RSI1上穿/下穿RSI2和RSI3（金叉/死叉）"""
        rsi1_prev = df['rsi1'].shift(1)
        rsi2_prev = df['rsi2'].shift(1)
        rsi3_prev = df['rsi3'].shift(1)

        # RSI1上穿/下穿RSI2（金叉/死叉）
        df['rsi1_cross_above_rsi2'] = (rsi1_prev <= rsi2_prev) & (df['rsi1'] > df['rsi2'])
        df['rsi1_cross_below_rsi2'] = (rsi1_prev >= rsi2_prev) & (df['rsi1'] < df['rsi2'])

        # RSI1上穿/下穿RSI3（二次金叉/二次死叉）
        df['rsi1_cross_above_rsi3'] = (rsi1_prev <= rsi3_prev) & (df['rsi1'] > df['rsi3'])
        df['rsi1_cross_below_rsi3'] = (rsi1_prev >= rsi3_prev) & (df['rsi1'] < df['rsi3'])

        # 检测快速从80跌穿50
        rsi1_2_days_ago = df['rsi1'].shift(2)
        df['rsi1_fast_drop_80_to_50'] = (
            (rsi1_2_days_ago >= 80) &
            (df['rsi1'] < 50)
        )

        return df

    def _detect_alignment(self, df: pd.DataFrame) -> pd.DataFrame:
        """判断三线多空排列状态"""
        # 多头排列：RSI1 > RSI2 > RSI3
        bullish_alignment = (df['rsi1'] > df['rsi2']) & (df['rsi2'] > df['rsi3'])

        # 空头排列：RSI1 < RSI2 < RSI3
        bearish_alignment = (df['rsi1'] < df['rsi2']) & (df['rsi2'] < df['rsi3'])

        # 黏合：三线差异小于阈值
        max_diff = (
            df[['rsi1', 'rsi2', 'rsi3']].max(axis=1) -
            df[['rsi1', 'rsi2', 'rsi3']].min(axis=1)
        )
        glued = max_diff < self.params['line_glued_threshold']

        # 判断排列状态
        conditions = [
            glued,  # 黏合
            bullish_alignment,  # 多头排列
            bearish_alignment,  # 空头排列
        ]
        choices = ['GLUED', 'BULLISH', 'BEARISH']
        df['triple_alignment'] = np.select(conditions, choices, default='NEUTRAL')

        # 检测三线是否向上发散（多头增强）
        df['bullish_divergence'] = (
            (df['triple_alignment'] == 'BULLISH') &
            (df['rsi1'].diff(3) > 0) &
            (df['rsi2'].diff(3) > 0) &
            (df['rsi3'].diff(3) > 0)
        )

        # 检测三线是否向下发散（空头增强）
        df['bearish_divergence'] = (
            (df['triple_alignment'] == 'BEARISH') &
            (df['rsi1'].diff(3) < 0) &
            (df['rsi2'].diff(3) < 0) &
            (df['rsi3'].diff(3) < 0)
        )

        return df

    def _detect_rsi1_direction(self, df: pd.DataFrame) -> pd.DataFrame:
        """检测RSI1方向和拐头"""
        slope_window = self.params['slope_window']
        slope_threshold = self.params['slope_threshold']

        # 计算斜率
        df['rsi1_slope'] = df['rsi1'].diff(slope_window)

        # 判断方向
        df['rsi1_direction'] = 'FLAT'
        df.loc[df['rsi1_slope'] > slope_threshold, 'rsi1_direction'] = 'UP'
        df.loc[df['rsi1_slope'] < -slope_threshold, 'rsi1_direction'] = 'DOWN'

        # 检测拐头
        prev_direction = df['rsi1_direction'].shift(1)
        df['rsi1_turning_up'] = (
            (prev_direction.isin(['DOWN', 'FLAT'])) &
            (df['rsi1_direction'] == 'UP')
        )
        df['rsi1_turning_down'] = (
            (prev_direction.isin(['UP', 'FLAT'])) &
            (df['rsi1_direction'] == 'DOWN')
        )

        # 连续向上/向下计数
        df['rsi1_consecutive_up'] = 0
        df['rsi1_consecutive_down'] = 0

        for i in range(1, len(df)):
            if df.loc[df.index[i], 'rsi1_direction'] == 'UP':
                df.loc[df.index[i], 'rsi1_consecutive_up'] = \
                    df.loc[df.index[i-1], 'rsi1_consecutive_up'] + 1
            elif df.loc[df.index[i], 'rsi1_direction'] == 'DOWN':
                df.loc[df.index[i], 'rsi1_consecutive_down'] = \
                    df.loc[df.index[i-1], 'rsi1_consecutive_down'] + 1

        return df

    def _calculate_target_position(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        根据RSI三线规则计算目标仓位(0-10)

        核心规则：
        1. 0仓：空头排列、死叉、RSI1<20持续向下
        2. 1-2仓：RSI1<20首次拐头向上
        3. 3-4仓：RSI1上穿RSI2（金叉）
        4. 5-6仓：RSI1上穿RSI3（二次金叉）+初步多头排列
        5. 7-8仓：多头排列确认 + RSI1进入59-80
        6. 9-10仓：极强多头排列 + RSI1在55-75健康区
        """
        df['target_position'] = 0
        df['position_reason'] = ''

        for idx in range(len(df)):
            if idx < 24:  # 需要至少24天RSI3数据
                continue

            row = df.iloc[idx]
            rsi1 = row['rsi1']
            rsi1_direction = row['rsi1_direction']
            rsi1_turning_up = row['rsi1_turning_up']
            rsi1_consecutive_up = row['rsi1_consecutive_up']
            triple_alignment = row['triple_alignment']

            cross_above_rsi2 = row['rsi1_cross_above_rsi2']
            cross_below_rsi2 = row['rsi1_cross_below_rsi2']
            cross_above_rsi3 = row['rsi1_cross_above_rsi3']
            cross_below_rsi3 = row['rsi1_cross_below_rsi3']

            fast_drop_80_to_50 = row['rsi1_fast_drop_80_to_50']
            bullish_divergence = row['bullish_divergence']

            current_position = df.at[df.index[idx], 'target_position']

            # ========== 优先级1: 紧急清仓（0仓）==========
            # 空头排列或二次死叉
            if triple_alignment == 'BEARISH' or cross_below_rsi3:
                df.at[df.index[idx], 'target_position'] = 0
                df.at[df.index[idx], 'position_reason'] = \
                    '空头排列/二次死叉，紧急清仓' if triple_alignment == 'BEARISH' else 'RSI1下穿RSI3，清仓'
                continue

            # RSI1从80快速跌穿50
            if fast_drop_80_to_50:
                df.at[df.index[idx], 'target_position'] = 0
                df.at[df.index[idx], 'position_reason'] = 'RSI1从80快速跌穿50，紧急清仓'
                continue

            # RSI1<20且持续向下
            if rsi1 < 20 and rsi1_direction == 'DOWN' and rsi1_consecutive_up == 0:
                df.at[df.index[idx], 'target_position'] = 0
                df.at[df.index[idx], 'position_reason'] = 'RSI1极度超卖且持续向下，空仓观望'
                continue

            # ========== 优先级2: 极轻仓试错（1-2仓）==========
            if rsi1 < 20 and rsi1_turning_up and not cross_above_rsi2:
                if current_position == 0:
                    df.at[df.index[idx], 'target_position'] = 1
                    df.at[df.index[idx], 'position_reason'] = 'RSI1<20首次拐头向上，试错1仓'
                elif current_position == 1 and rsi1_direction == 'UP':
                    df.at[df.index[idx], 'target_position'] = 2
                    df.at[df.index[idx], 'position_reason'] = 'RSI1继续向上，加仓到2仓'
                continue

            # ========== 优先级3: 轻仓进场（3-4仓）==========
            if cross_above_rsi2:
                df.at[df.index[idx], 'target_position'] = 3
                df.at[df.index[idx], 'position_reason'] = 'RSI1上穿RSI2（金叉），建仓3成'
                continue

            # 金叉后RSI1继续向上且站稳20以上
            if rsi1 > 20 and rsi1_direction == 'UP' and rsi1_consecutive_up >= 1:
                if current_position >= 3:
                    df.at[df.index[idx], 'target_position'] = 4
                    df.at[df.index[idx], 'position_reason'] = '金叉后RSI1持续向上，持仓4成'
                continue

            # ========== 优先级4: 半仓加仓（5-6仓）==========
            if cross_above_rsi3:
                df.at[df.index[idx], 'target_position'] = 5
                df.at[df.index[idx], 'position_reason'] = 'RSI1上穿RSI3（二次金叉），建仓5成'
                continue

            # 初步多头排列 + RSI1站上50
            if triple_alignment == 'BULLISH' and rsi1 >= 50:
                df.at[df.index[idx], 'target_position'] = 5
                df.at[df.index[idx], 'position_reason'] = '初步多头排列+RSI1站上50，持仓5成'
                continue

            # 二次金叉后继续向上
            if rsi1 > 50 and rsi1_direction == 'UP' and rsi1_consecutive_up >= 1:
                if current_position >= 5:
                    df.at[df.index[idx], 'target_position'] = 6
                    df.at[df.index[idx], 'position_reason'] = '二次金叉后RSI1持续向上，持仓6成'
                continue

            # ========== 优先级5: 重仓持有（7-8仓）==========
            if triple_alignment == 'BULLISH' and 59 <= rsi1 < 80:
                if bullish_divergence and rsi1_consecutive_up >= 2:
                    df.at[df.index[idx], 'target_position'] = 8
                    df.at[df.index[idx], 'position_reason'] = '多头排列向上发散+RSI1在59-80，持仓8成'
                else:
                    df.at[df.index[idx], 'target_position'] = 7
                    df.at[df.index[idx], 'position_reason'] = '多头排列+RSI1在59-80，持仓7成'
                continue

            # ========== 优先级6: 满仓（9-10仓）慢牛专用==========
            if triple_alignment == 'BULLISH' and bullish_divergence:
                if 55 <= rsi1 <= 75 and rsi1_consecutive_up >= 3:
                    df.at[df.index[idx], 'target_position'] = 9
                    df.at[df.index[idx], 'position_reason'] = '极强多头排列+RSI1在健康区，持仓9成'
                if 60 <= rsi1 <= 70 and rsi1_consecutive_up >= 5:
                    df.at[df.index[idx], 'target_position'] = 10
                    df.at[df.index[idx], 'position_reason'] = '极强多头排列持续，满仓10成'
                continue

            # ========== 优先级7: 死叉减仓 ==========
            if cross_below_rsi2 and current_position > 4:
                # 死叉减仓50%
                new_position = max(current_position // 2, 3)
                df.at[df.index[idx], 'target_position'] = new_position
                df.at[df.index[idx], 'position_reason'] = f'RSI1下穿RSI2（死叉），减仓到{new_position}成'
                continue

            # RSI1>80拐头向下，减仓50%
            if rsi1 >= 80 and row['rsi1_turning_down'] and current_position > 4:
                new_position = max(current_position // 2, 3)
                df.at[df.index[idx], 'target_position'] = new_position
                df.at[df.index[idx], 'position_reason'] = f'RSI1超买拐头向下，减仓到{new_position}成'
                continue

            # ========== 默认: 保持当前仓位 ==========
            if current_position > 0:
                df.at[df.index[idx], 'target_position'] = current_position
                df.at[df.index[idx], 'position_reason'] = f'保持当前仓位{current_position}成'

        # 确保仓位是有效离散值
        valid_positions = list(range(11))  # 0-10
        df['target_position'] = df['target_position'].apply(
            lambda x: int(x) if int(x) in valid_positions else 0
        )

        return df
