"""
RSI+MACD+KDJ 三指标共振策略信号生成器（重构版）

核心逻辑 - 三大优化：

【第一步：趋势铁律】
彻底解决踏空和抄底问题
- 多头趋势（可重仓）：股价站上MA60，且MA20向上拐头 → 0-8仓
- 震荡趋势（轻仓）：股价在MA60上下10%区间，MA20走平 → 3-5仓
- 空头趋势（空仓）：股价在MA60下方，且MA20向下 → 0-1仓

【第二步：重构指标共振】
改为"MACD定大方向，KDJ+RSI找买卖点"
- 买入：MACD在零轴上方 + KDJ金叉 + RSI>50
- 卖出：MACD在零轴下方 + KDJ死叉 + RSI<50
- 极端止盈：RSI>80 减仓50%

【第三步：绑定趋势的仓位管理】
顺势加仓、逆势减仓
- 多头：首买5仓，涨5%加3仓，最高8仓，止损-5%或跌破MA20
- 震荡：固定3-4仓，止损-3%
- 空头：0仓，最多1仓试错，止损-2%

参数固定：
- MA: 20日、60日均线
- RSI: 14
- MACD: 12, 26, 9
- KDJ: 14, 3, 3
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class RSIMACDKDJTripleSignalGenerator:
    """
    RSI+MACD+KDJ 三指标共振信号生成器（重构版）
    """

    def __init__(self, params: Dict = None):
        self.params = params or self.default_params()

    @staticmethod
    def default_params():
        return {
            # MA参数
            'ma_fast': 20,
            'ma_slow': 60,
            'ma_flat_threshold': 0.10,  # MA60上下10%算震荡

            # RSI参数
            'rsi_period': 14,
            'rsi_overbought': 80,
            'rsi_oversold': 20,
            'rsi_middle': 50,

            # MACD参数
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,

            # KDJ参数
            'kdj_n': 14,
            'kdj_m1': 3,
            'kdj_m2': 3,

            # 仓位参数
            'max_position_bull': 8,      # 多头趋势最大仓位
            'max_position_flat': 5,      # 震荡趋势最大仓位
            'max_position_bear': 1,      # 空头趋势最大仓位
            'initial_position_bull': 5,  # 多头趋势首买仓位
            'add_position_bull': 3,      # 多头趋势加仓幅度
            'add_threshold_bull': 0.05,  # 多头加仓阈值（涨5%）
            'position_flat': 4,          # 震荡趋势固定仓位

            # 止损止盈
            'stop_loss_bull': 0.05,      # 多头止损-5%
            'stop_loss_flat': 0.03,      # 震荡止损-3%
            'stop_loss_bear': 0.02,      # 空头止损-2%
            'take_profit_bull': 0.15,    # 多头止盈15-20%
            'take_profit_flat': 0.08,    # 震荡止盈8-10%
            'take_profit_bear': 0.05,    # 空头止盈5%
            'extreme_overbought': 80,    # 极端超买减仓阈值
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成三指标共振信号

        Returns:
            DataFrame with columns:
            - ma20, ma60, ma60_up, ma60_down: 均线指标
            - ma_trend_type: 趋势类型 (BULL/FLAT/BEAR)
            - ma20_slope: MA20斜率
            - rsi: RSI指标值
            - macd_dif, macd_dea, macd_hist: MACD指标
            - macd_above_zero: MACD是否在零轴上方
            - kdj_k, kdj_d, kdj_j: KDJ指标
            - kdj_golden_cross, kdj_dead_cross: KDJ金叉死叉
            - target_position: 目标仓位 (0-8)
            - exec_position: 执行仓位 (shift(1))
            - signal_type: 信号类型 (BUY/SELL/HOLD)
            - signal_reason: 信号说明
        """
        df = df.copy()

        # 计算指标
        df = self._calculate_indicators(df)

        # 判断趋势类型（趋势铁律）
        df = self._classify_trend_type(df)

        # 检测买卖信号（重构的指标共振）
        df = self._detect_trading_signals(df)

        # 计算目标仓位（绑定趋势的仓位管理）
        df = self._calculate_target_position(df)

        # 执行仓位（T+1）
        df['exec_position'] = df['target_position'].shift(1).fillna(0)

        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        # MA20和MA60
        df['ma20'] = df['close'].rolling(window=self.params['ma_fast'], min_periods=1).mean()
        df['ma60'] = df['close'].rolling(window=self.params['ma_slow'], min_periods=1).mean()

        # MA60上界和下界（用于判断震荡趋势）
        threshold = self.params['ma_flat_threshold']
        df['ma60_upper'] = df['ma60'] * (1 + threshold)
        df['ma60_lower'] = df['ma60'] * (1 - threshold)

        # MA20斜率（判断拐头）
        df['ma20_slope'] = df['ma20'].diff(5)  # 5日斜率更稳定

        # RSI(14)
        df['rsi'] = self._calculate_rsi(df['close'], self.params['rsi_period'])

        # MACD(12,26,9)
        ema_fast = df['close'].ewm(span=self.params['macd_fast'], adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.params['macd_slow'], adjust=False).mean()

        df['macd_dif'] = ema_fast - ema_slow
        df['macd_dea'] = df['macd_dif'].ewm(span=self.params['macd_signal'], adjust=False).mean()
        df['macd_hist'] = 2 * (df['macd_dif'] - df['macd_dea'])
        df['macd_above_zero'] = df['macd_dif'] > 0

        # KDJ(14,3,3)
        n = self.params['kdj_n']
        m1 = self.params['kdj_m1']
        m2 = self.params['kdj_m2']

        low_list = df['low'].rolling(window=n, min_periods=1).min()
        high_list = df['high'].rolling(window=n, min_periods=1).max()
        high_low_diff = high_list - low_list
        high_low_diff = high_low_diff.replace(0, np.finfo(float).eps)

        rsv = (df['close'] - low_list) / high_low_diff * 100
        df['kdj_k'] = rsv.ewm(com=m1-1, adjust=False).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=m2-1, adjust=False).mean()
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']

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

    def _classify_trend_type(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        趋势铁律：判断趋势类型

        多头趋势（BULL）: 股价>MA60 且 MA20向上拐头
        震荡趋势（FLAT）: 股价在MA60上下10%区间，MA20走平
        空头趋势（BEAR）: 股价<MA60下界 或 MA20向下拐头
        """
        # 判断MA20方向
        ma20_rising = df['ma20_slope'] > 0
        ma20_falling = df['ma20_slope'] < 0
        ma20_flat = (~ma20_rising) & (~ma20_falling)

        # 判断价格相对于MA60的位置
        price_above_ma60 = df['close'] > df['ma60_upper']
        price_below_ma60 = df['close'] < df['ma60_lower']
        price_near_ma60 = (~price_above_ma60) & (~price_below_ma60)

        # 判断趋势类型
        df['trend_type'] = 'FLAT'  # 默认震荡

        # 多头趋势：价格在MA60上方且MA20向上
        bull_condition = price_above_ma60 & ma20_rising
        df.loc[bull_condition, 'trend_type'] = 'BULL'

        # 空头趋势：价格在MA60下方或MA20向下
        bear_condition = price_below_ma60 | ma20_falling
        df.loc[bear_condition, 'trend_type'] = 'BEAR'

        # 震荡趋势：价格在MA60附近且MA20走平
        flat_condition = price_near_ma60 & ma20_flat
        df.loc[flat_condition, 'trend_type'] = 'FLAT'

        return df

    def _detect_trading_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        重构的指标共振：MACD定大方向，KDJ+RSI找买卖点

        买入信号：
        1. 前提：MACD在零轴上方（多头趋势）
        2. 触发：KDJ金叉 + RSI>50

        卖出信号：
        1. 前提：MACD在零轴下方（空头趋势）
        2. 触发：KDJ死叉 + RSI<50
        3. 极端止盈：RSI>80 减仓50%
        """
        # KDJ交叉检测
        k_prev = df['kdj_k'].shift(1)
        d_prev = df['kdj_d'].shift(1)
        df['kdj_golden_cross'] = (k_prev <= d_prev) & (df['kdj_k'] > df['kdj_d'])
        df['kdj_dead_cross'] = (k_prev >= d_prev) & (df['kdj_k'] < df['kdj_d'])

        # 初始化信号列
        df['signal_type'] = 'HOLD'
        df['signal_reason'] = '观望'

        # ========== 买入信号 ==========
        # MACD在零轴上方 + KDJ金叉 + RSI>50
        buy_condition = (
            df['macd_above_zero'] &  # MACD在零轴上方
            df['kdj_golden_cross'] &   # KDJ金叉
            (df['rsi'] > self.params['rsi_middle'])  # RSI>50
        )

        df.loc[buy_condition, 'signal_type'] = 'BUY'
        df.loc[buy_condition, 'signal_reason'] = 'MACD多头+KDJ金叉+RSI>50，买入'

        # ========== 卖出信号 ==========
        # 条件1: MACD在零轴下方 + KDJ死叉 + RSI<50
        sell_condition_1 = (
            (~df['macd_above_zero']) &  # MACD在零轴下方
            df['kdj_dead_cross'] &      # KDJ死叉
            (df['rsi'] < self.params['rsi_middle'])  # RSI<50
        )
        df.loc[sell_condition_1, 'signal_type'] = 'SELL'
        df.loc[sell_condition_1, 'signal_reason'] = 'MACD空头+KDJ死叉+RSI<50，卖出'

        # 条件2: 极端止盈 - RSI>80
        sell_condition_2 = df['rsi'] > self.params['extreme_overbought']
        df.loc[sell_condition_2 & (df['signal_type'] != 'SELL'), 'signal_type'] = 'SELL'
        df.loc[sell_condition_2 & (df['signal_type'] != 'SELL'), 'signal_reason'] = 'RSI极度超买>80，减仓50%'

        return df

    def _calculate_target_position(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        绑定趋势的仓位管理

        多头趋势：首买5仓，涨5%加3仓，最高8仓
        震荡趋势：固定3-4仓
        空头趋势：0仓，最多1仓试错
        """
        df['target_position'] = 0
        df['position_reason'] = ''

        # 初始化基础仓位
        df['base_position'] = 0
        df['max_allowed'] = 0

        for idx in range(len(df)):
            if idx < 60:  # 需要足够的MA数据
                continue

            row = df.iloc[idx]
            trend = row['trend_type']
            signal_type = row['signal_type']
            close_price = row['close']
            ma20 = row['ma20']
            position = df.at[df.index[idx], 'target_position']

            # ========== 空头趋势（BEAR）==========
            if trend == 'BEAR':
                df.at[df.index[idx], 'max_allowed'] = self.params['max_position_bear']

                # 空头趋势：0仓为主，最多1仓试错
                if signal_type == 'BUY' and position == 0:
                    # 只在空仓时允许1仓试错
                    df.at[df.index[idx], 'target_position'] = 1
                    df.at[df.index[idx], 'position_reason'] = '空头趋势试错，轻仓1'
                else:
                    df.at[df.index[idx], 'target_position'] = 0
                    df.at[df.index[idx], 'position_reason'] = '空头趋势，空仓观望'

            # ========== 震荡趋势（FLAT）==========
            elif trend == 'FLAT':
                df.at[df.index[idx], 'max_allowed'] = self.params['max_position_flat']

                # 震荡趋势：固定3-4仓
                if signal_type == 'BUY' and position < self.params['position_flat']:
                    df.at[df.index[idx], 'target_position'] = self.params['position_flat']
                    df.at[df.index[idx], 'position_reason'] = f'震荡趋势，固定{self.params["position_flat"]}仓'
                elif signal_type == 'SELL':
                    df.at[df.index[idx], 'target_position'] = 0
                    df.at[df.index[idx], 'position_reason'] = '震荡趋势卖出信号，空仓'
                # 持有逻辑：超出4仓减到4仓，低于3仓加到3仓
                elif position > self.params['position_flat']:
                    df.at[df.index[idx], 'target_position'] = self.params['position_flat']
                    df.at[df.index[idx], 'position_reason'] = '震荡趋势减仓'
                elif position > 0 and position < 3:
                    df.at[df.index[idx], 'target_position'] = 3
                    df.at[df.index[idx], 'position_reason'] = '震荡趋势加仓到3'

            # ========== 多头趋势（BULL）==========
            elif trend == 'BULL':
                df.at[df.index[idx], 'max_allowed'] = self.params['max_position_bull']

                if signal_type == 'BUY':
                    # 买入信号：根据当前仓位决定
                    if position == 0:
                        # 首次买入：5仓
                        df.at[df.index[idx], 'target_position'] = self.params['initial_position_bull']
                        df.at[df.index[idx], 'position_reason'] = f'多头首买入，建仓{self.params["initial_position_bull"]}成'
                    elif position >= 2:
                        # 计算涨跌幅（简单估算：对比最近的入场价）
                        add_threshold = self.params['add_threshold_bull']
                        # 这里用当前价格相对于MA20的涨跌作为估算
                        price_change = (close_price - ma20) / ma20 if ma20 > 0 else 0

                        if price_change >= add_threshold and position < self.params['max_position_bull']:
                            # 涨5%后加3仓
                            new_position = min(position + self.params['add_position_bull'],
                                              self.params['max_position_bull'])
                            df.at[df.index[idx], 'target_position'] = new_position
                            df.at[df.index[idx], 'position_reason'] = f'多头涨5%，加仓到{new_position}成'
                        elif position < self.params['max_position_bull']:
                            # 未达到加仓条件，保持当前仓位
                            df.at[df.index[idx], 'target_position'] = position
                            df.at[df.index[idx], 'position_reason'] = f'多头持有，保持{position}成'
                        else:
                            df.at[df.index[idx], 'target_position'] = position
                            df.at[df.index[idx], 'position_reason'] = '多头持有，保持仓位'

                elif signal_type == 'SELL':
                    # 卖出信号：清仓
                    df.at[df.index[idx], 'target_position'] = 0
                    df.at[df.index[idx], 'position_reason'] = '多头卖出信号，清仓'

                # 极端超买减仓
                elif row['rsi'] > self.params['extreme_overbought'] and position > 4:
                    # RSI>80，减仓50%
                    new_position = max(position // 2, 1)
                    df.at[df.index[idx], 'target_position'] = new_position
                    df.at[df.index[idx], 'position_reason'] = f'RSI极度超买>80，减仓到{new_position}成'

        # 确保仓位是有效离散值
        valid_positions = [0, 1, 2, 3, 4, 5, 6, 7, 8]
        df['target_position'] = df['target_position'].apply(
            lambda x: int(x) if int(x) in valid_positions else 0
        )

        return df
