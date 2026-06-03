#!/usr/bin/env python3
"""
混合策略回测：低买 + 趋势卖
- 买入：布林带<0.3 + 超卖信号（低买）
- 卖出：MACD死叉 + 布林带>0.5 或 止盈20% 或 回撤10%（趋势卖）
"""
import sys
sys.path.append('/home/landasika/etf-predict')

import pandas as pd
import numpy as np
from typing import Dict, List
from core.database import get_etf_daily_data
from strategies.indicators import MACDIndicators


def calculate_bollinger_position(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """计算布林带位置（0-1）"""
    df = df.copy()
    df['bb_middle'] = df['close'].rolling(window).mean()
    df['bb_std'] = df['close'].rolling(window).std()
    df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']

    bb_range = df['bb_upper'] - df['bb_lower']
    df['bb_position'] = (df['close'] - df['bb_lower']) / bb_range.replace(0, np.nan)
    df['bb_position'] = df['bb_position'].fillna(0.5).clip(0, 1)

    return df


def calculate_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """计算RSI指标"""
    df = df.copy()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / (loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    return df


def generate_hybrid_signals(df: pd.DataFrame) -> pd.DataFrame:
    """生成混合策略信号

    买入：低买策略（布林带<0.3 + 超卖）
    卖出：趋势策略（MACD死叉+布林带>0.5）
    """
    df = df.copy()

    # 计算所有指标
    df = MACDIndicators.calculate_macd(df)
    df = MACDIndicators.calculate_kdj(df)
    df = calculate_bollinger_position(df)
    df = calculate_rsi(df)

    # 初始化信号
    df['signal'] = 0
    df['signal_reason'] = ''
    df['buy_score'] = 0

    # ========== 买入信号：低买策略 ==========

    # 1. 布林带位置（必须条件）
    bb_low = df['bb_position'] < 0.3
    bb_very_low = df['bb_position'] < 0.2

    # 2. RSI超卖
    rsi_oversold = df['rsi'] < 40
    rsi_very_oversold = df['rsi'] < 30

    # 3. MACD信号
    macd_golden_cross = (df['macd_dif'].shift(1) <= df['macd_dea'].shift(1)) & (df['macd_dif'] > df['macd_dea'])
    macd_positive = df['macd_dif'] > 0

    # 4. KDJ低位金叉
    kdj_golden_cross = (df['kdj_k'].shift(1) <= df['kdj_d'].shift(1)) & (df['kdj_k'] > df['kdj_d'])
    kdj_low = df['kdj_j'] < 30

    # 买入评分
    buy_score = np.where(bb_very_low, 3,
                np.where(bb_low, 2, 0))

    buy_score += np.where(rsi_very_oversold, 2,
                 np.where(rsi_oversold, 1, 0))

    buy_score += np.where(macd_golden_cross, 2,
                 np.where(macd_positive, 1, 0))

    buy_score += np.where(kdj_golden_cross & kdj_low, 2,
                 np.where(kdj_golden_cross, 1, 0))

    df['buy_score'] = buy_score

    # 强买入：评分>=5 且 布林带<0.3
    strong_buy = (buy_score >= 5) & bb_low
    df.loc[strong_buy, 'signal'] = 2
    df.loc[strong_buy, 'signal_reason'] = '低位买入(多指标共振)'

    # 中等买入：评分>=4 且 布林带<0.3
    medium_buy = (buy_score >= 4) & (buy_score < 5) & bb_low
    df.loc[medium_buy, 'signal'] = 1
    df.loc[medium_buy, 'signal_reason'] = '低位买入'

    # ========== 卖出信号：趋势策略 ==========

    # 1. MACD死叉 + 布林带>0.5
    macd_death_cross = (df['macd_dif'].shift(1) >= df['macd_dea'].shift(1)) & (df['macd_dif'] < df['macd_dea'])
    bb_mid_high = df['bb_position'] > 0.5

    # 趋势卖出
    trend_sell = macd_death_cross & bb_mid_high
    df.loc[trend_sell, 'signal'] = -1
    df.loc[trend_sell, 'signal_reason'] = '趋势转弱(MACD死叉)'

    # 2. MACD死叉在零轴下方（更强的卖出信号）
    macd_negative = df['macd_dif'] < 0
    strong_sell = macd_death_cross & macd_negative
    df.loc[strong_sell, 'signal'] = -2
    df.loc[strong_sell, 'signal_reason'] = '趋势转空(零轴下死叉)'

    return df


def hybrid_backtest(df: pd.DataFrame, initial_capital: float = 10000,
                   stop_loss: float = 0.08, take_profit: float = 0.20,
                   trailing_stop: float = 0.10) -> Dict:
    """混合策略回测引擎

    Args:
        df: 包含信号的数据
        initial_capital: 初始资金
        stop_loss: 止损比例 (-8%)
        take_profit: 止盈比例 (+20%)
        trailing_stop: 追踪止损（从最高点回撤10%）
    """
    capital = initial_capital
    position = 0
    cost = 0
    max_price = 0  # 持仓期间最高价

    trades = []
    equity_curve = []
    buy_positions = []
    sell_positions = []

    for i in range(len(df)):
        row = df.iloc[i]
        price = row['close']
        signal = row['signal']

        # 更新最高价
        if position > 0 and price > max_price:
            max_price = price

        # 计算当前权益
        current_value = capital + position * price
        equity_curve.append({
            'date': row['trade_date'],
            'equity': current_value,
            'price': price,
            'position': position
        })

        # 持仓检查
        if position > 0:
            current_return = (price - cost) / cost
            drawdown_from_peak = (max_price - price) / max_price if max_price > 0 else 0

            # 1. 止损检查 (-8%)
            if current_return < -stop_loss:
                sell_value = position * price * 0.995
                capital += sell_value

                trades.append({
                    'date': row['trade_date'],
                    'type': 'SELL_STOP_LOSS',
                    'price': price,
                    'quantity': position,
                    'value': sell_value,
                    'pnl': sell_value - position * cost,
                    'return': current_return,
                    'reason': f'止损 {current_return*100:.1f}%'
                })

                sell_positions.append({
                    'date': row['trade_date'],
                    'price': price,
                    'bb_position': row['bb_position'],
                    'reason': 'STOP_LOSS'
                })

                position = 0
                cost = 0
                max_price = 0
                continue

            # 2. 止盈检查 (+20%)
            if current_return >= take_profit:
                sell_value = position * price * 0.995
                capital += sell_value

                trades.append({
                    'date': row['trade_date'],
                    'type': 'SELL_TAKE_PROFIT',
                    'price': price,
                    'quantity': position,
                    'value': sell_value,
                    'pnl': sell_value - position * cost,
                    'return': current_return,
                    'reason': f'止盈 {current_return*100:.1f}%'
                })

                sell_positions.append({
                    'date': row['trade_date'],
                    'price': price,
                    'bb_position': row['bb_position'],
                    'reason': 'TAKE_PROFIT'
                })

                position = 0
                cost = 0
                max_price = 0
                continue

            # 3. 追踪止损检查（从最高点回撤10%）
            if drawdown_from_peak >= trailing_stop and current_return > 0:
                sell_value = position * price * 0.995
                capital += sell_value

                trades.append({
                    'date': row['trade_date'],
                    'type': 'SELL_TRAILING_STOP',
                    'price': price,
                    'quantity': position,
                    'value': sell_value,
                    'pnl': sell_value - position * cost,
                    'return': current_return,
                    'reason': f'追踪止损 回撤{drawdown_from_peak*100:.1f}% 利润{current_return*100:.1f}%'
                })

                sell_positions.append({
                    'date': row['trade_date'],
                    'price': price,
                    'bb_position': row['bb_position'],
                    'reason': 'TRAILING_STOP'
                })

                position = 0
                cost = 0
                max_price = 0
                continue

        # 买入信号
        if signal > 0 and position == 0:
            position = capital / price
            cost = price
            max_price = price
            capital = 0

            trades.append({
                'date': row['trade_date'],
                'type': 'BUY',
                'price': price,
                'quantity': position,
                'value': position * price,
                'signal_strength': signal,
                'reason': row['signal_reason']
            })

            buy_positions.append({
                'date': row['trade_date'],
                'price': price,
                'bb_position': row['bb_position'],
                'rsi': row['rsi'],
                'buy_score': row['buy_score']
            })

        # 卖出信号（MACD死叉）
        elif signal < 0 and position > 0:
            sell_value = position * price * 0.995
            pnl = sell_value - position * cost
            ret = pnl / (position * cost)

            capital += sell_value

            trades.append({
                'date': row['trade_date'],
                'type': 'SELL_SIGNAL',
                'price': price,
                'quantity': position,
                'value': sell_value,
                'pnl': pnl,
                'return': ret,
                'reason': row['signal_reason']
            })

            sell_positions.append({
                'date': row['trade_date'],
                'price': price,
                'bb_position': row['bb_position'],
                'reason': 'SIGNAL'
            })

            position = 0
            cost = 0
            max_price = 0

    # 最终清算
    if position > 0:
        final_price = df.iloc[-1]['close']
        final_value = position * final_price * 0.995
        capital += final_value

    # 计算指标
    total_return = (capital - initial_capital) / initial_capital
    buy_hold_return = (df.iloc[-1]['close'] - df.iloc[0]['close']) / df.iloc[0]['close']

    # 统计
    avg_buy_bb = np.mean([p['bb_position'] for p in buy_positions]) if buy_positions else 0.5
    avg_sell_bb = np.mean([p['bb_position'] for p in sell_positions]) if sell_positions else 0.5
    avg_buy_rsi = np.mean([p['rsi'] for p in buy_positions]) if buy_positions else 50

    # 胜率
    profitable_trades = [t for t in trades if t.get('pnl', 0) > 0]
    total_trades_with_pnl = [t for t in trades if 'pnl' in t]
    win_rate = len(profitable_trades) / len(total_trades_with_pnl) if total_trades_with_pnl else 0

    # 卖出原因统计
    sell_reasons = {}
    for p in sell_positions:
        reason = p.get('reason', 'UNKNOWN')
        sell_reasons[reason] = sell_reasons.get(reason, 0) + 1

    return {
        'final_capital': capital,
        'total_return': total_return,
        'total_return_pct': total_return * 100,
        'buy_hold_return_pct': buy_hold_return * 100,
        'trades': len(trades),
        'win_rate': win_rate,
        'avg_buy_bb_position': avg_buy_bb,
        'avg_sell_bb_position': avg_sell_bb,
        'avg_buy_rsi': avg_buy_rsi,
        'equity_curve': equity_curve,
        'trade_list': trades,
        'buy_positions': buy_positions,
        'sell_positions': sell_positions,
        'sell_reasons': sell_reasons
    }


def backtest_macd_simple(df: pd.DataFrame, initial_capital: float = 10000) -> Dict:
    """MACD简单策略回测（用于对比）"""
    df = df.copy()
    df = MACDIndicators.calculate_macd(df)

    df['signal'] = 0
    golden_cross = (df['macd_dif'].shift(1) <= df['macd_dea'].shift(1)) & (df['macd_dif'] > df['macd_dea'])
    death_cross = (df['macd_dif'].shift(1) >= df['macd_dea'].shift(1)) & (df['macd_dif'] < df['macd_dea'])

    df.loc[golden_cross, 'signal'] = 1
    df.loc[death_cross, 'signal'] = -1
    df['signal_reason'] = ''
    df['buy_score'] = 0

    df = calculate_bollinger_position(df)
    df = calculate_rsi(df)

    return hybrid_backtest(df, initial_capital, stop_loss=0.05, take_profit=0.15, trailing_stop=0.08)


def run_comparison(etf_code: str, etf_name: str, start_date: str = '20240101'):
    """运行对比测试"""
    print(f"\n{'='*80}")
    print(f"回测ETF: {etf_name} ({etf_code})")
    print(f"{'='*80}")

    # 加载数据
    data = get_etf_daily_data(etf_code, start_date)
    if not data or len(data) < 60:
        print(f"❌ 数据不足")
        return None

    df = pd.DataFrame(data)
    print(f"数据周期: {df.iloc[0]['trade_date']} ~ {df.iloc[-1]['trade_date']} ({len(df)}天)")

    # 1. MACD策略回测
    print(f"\n{'─'*80}")
    print("策略1: MACD激进策略（对照组）")
    print(f"{'─'*80}")

    result_macd = backtest_macd_simple(df.copy())

    print(f"总收益率: {result_macd['total_return_pct']:.2f}%")
    print(f"买入持有: {result_macd['buy_hold_return_pct']:.2f}%")
    print(f"交易次数: {result_macd['trades']}")
    print(f"胜率: {result_macd['win_rate']*100:.1f}%")
    print(f"平均买入: 布林带 {result_macd['avg_buy_bb_position']:.2f} | RSI {result_macd['avg_buy_rsi']:.1f}")
    print(f"平均卖出: 布林带 {result_macd['avg_sell_bb_position']:.2f}")

    # 2. 混合策略回测
    print(f"\n{'─'*80}")
    print("策略2: 混合策略（低买 + 趋势卖）")
    print(f"{'─'*80}")

    df_hybrid = generate_hybrid_signals(df.copy())
    result_hybrid = hybrid_backtest(df_hybrid, stop_loss=0.08, take_profit=0.20, trailing_stop=0.10)

    print(f"总收益率: {result_hybrid['total_return_pct']:.2f}%")
    print(f"买入持有: {result_hybrid['buy_hold_return_pct']:.2f}%")
    print(f"交易次数: {result_hybrid['trades']}")
    print(f"胜率: {result_hybrid['win_rate']*100:.1f}%")
    print(f"平均买入: 布林带 {result_hybrid['avg_buy_bb_position']:.2f} | RSI {result_hybrid['avg_buy_rsi']:.1f}")
    print(f"平均卖出: 布林带 {result_hybrid['avg_sell_bb_position']:.2f}")

    print(f"\n卖出原因分布:")
    for reason, count in result_hybrid['sell_reasons'].items():
        print(f"  {reason}: {count}次")

    # 3. 对比分析
    print(f"\n{'─'*80}")
    print("📊 策略对比")
    print(f"{'─'*80}")

    improvement = result_hybrid['total_return_pct'] - result_macd['total_return_pct']

    print(f"\n收益对比:")
    print(f"  MACD策略:    {result_macd['total_return_pct']:>8.2f}%")
    print(f"  混合策略:    {result_hybrid['total_return_pct']:>8.2f}%")
    print(f"  改善幅度:    {improvement:>8.2f}% {'✅' if improvement > 0 else '❌'}")

    print(f"\n胜率对比:")
    print(f"  MACD策略:    {result_macd['win_rate']*100:>6.1f}%")
    print(f"  混合策略:    {result_hybrid['win_rate']*100:>6.1f}%")

    return {
        'etf_code': etf_code,
        'etf_name': etf_name,
        'macd': result_macd,
        'hybrid': result_hybrid
    }


def main():
    """主函数"""
    print("\n" + "="*80)
    print(" "*20 + "混合策略回测对比（低买+趋势卖）")
    print("="*80)

    test_etfs = [
        ('562360.SH', '机器人ETF'),
        ('512480.SH', '半导体ETF'),
        ('159928.SZ', '消费ETF')
    ]

    results = []

    for etf_code, etf_name in test_etfs:
        result = run_comparison(etf_code, etf_name, start_date='20240101')
        if result:
            results.append(result)

    # 汇总
    print(f"\n\n{'='*80}")
    print(" "*30 + "📊 汇总对比")
    print(f"{'='*80}")

    print(f"\n{'ETF':<15} {'策略':<20} {'收益率':>10} {'胜率':>8} {'买入位置':>10} {'卖出位置':>10}")
    print(f"{'─'*15} {'─'*20} {'─'*10} {'─'*8} {'─'*10} {'─'*10}")

    for r in results:
        print(f"{r['etf_name']:<15} {'MACD激进':<20} {r['macd']['total_return_pct']:>9.2f}% {r['macd']['win_rate']*100:>7.1f}% {r['macd']['avg_buy_bb_position']:>9.2f} {r['macd']['avg_sell_bb_position']:>9.2f}")
        print(f"{'':<15} {'混合策略(低买+趋势卖)':<20} {r['hybrid']['total_return_pct']:>9.2f}% {r['hybrid']['win_rate']*100:>7.1f}% {r['hybrid']['avg_buy_bb_position']:>9.2f} {r['hybrid']['avg_sell_bb_position']:>9.2f}")
        improvement = r['hybrid']['total_return_pct'] - r['macd']['total_return_pct']
        print(f"{'':<15} {'改善':<20} {improvement:>9.2f}% {'✅' if improvement > 0 else '❌'}")
        print()

    # 平均
    avg_macd = np.mean([r['macd']['total_return_pct'] for r in results])
    avg_hybrid = np.mean([r['hybrid']['total_return_pct'] for r in results])
    avg_improvement = avg_hybrid - avg_macd

    print(f"\n{'平均收益':<15}")
    print(f"  MACD策略:    {avg_macd:>8.2f}%")
    print(f"  混合策略:    {avg_hybrid:>8.2f}%")
    print(f"  平均改善:    {avg_improvement:>8.2f}% {'✅' if avg_improvement > 0 else '❌'}")

    print(f"\n{'='*80}")
    print("✅ 回测完成！")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
