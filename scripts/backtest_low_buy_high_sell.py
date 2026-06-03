#!/usr/bin/env python3
"""
低买高卖策略回测对比
测试布林带+MACD组合策略 vs 纯MACD策略
"""
import sys
sys.path.append('/home/landasika/etf-predict')

import pandas as pd
import numpy as np
from typing import Dict, List
from core.database import get_etf_daily_data
from strategies.indicators import MACDIndicators


def calculate_bollinger_position(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """计算布林带位置（0-1）

    0 = 下轨（超卖，低位）
    0.5 = 中轨（中性）
    1 = 上轨（超买，高位）
    """
    df = df.copy()

    # 计算布林带
    df['bb_middle'] = df['close'].rolling(window).mean()
    df['bb_std'] = df['close'].rolling(window).std()
    df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']

    # 计算位置（0=下轨，1=上轨）
    bb_range = df['bb_upper'] - df['bb_lower']
    df['bb_position'] = (df['close'] - df['bb_lower']) / bb_range.replace(0, np.nan)

    # 处理NaN和异常值
    df['bb_position'] = df['bb_position'].fillna(0.5)
    df['bb_position'] = df['bb_position'].clip(0, 1)

    return df


def calculate_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """计算RSI指标"""
    df = df.copy()

    # 计算价格变化
    delta = df['close'].diff()

    # 分离上涨和下跌
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()

    # 计算RS和RSI
    rs = gain / (loss + 1e-10)  # 避免除零
    df['rsi'] = 100 - (100 / (1 + rs))

    return df


def generate_low_buy_high_sell_signals(df: pd.DataFrame) -> pd.DataFrame:
    """生成低买高卖信号（布林带+MACD组合）"""
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
    df['sell_score'] = 0

    # ========== 买入信号评分 ==========

    # 1. 布林带位置（权重最高）
    bb_buy_score = np.where(df['bb_position'] < 0.2, 3,  # 深度超卖
                   np.where(df['bb_position'] < 0.3, 2,  # 偏低位
                   np.where(df['bb_position'] < 0.4, 1,  # 低位
                            0)))

    # 2. RSI超卖
    rsi_buy_score = np.where(df['rsi'] < 30, 3,  # 强超卖
                    np.where(df['rsi'] < 40, 2,  # 超卖
                             0))

    # 3. MACD信号
    macd_golden_cross = (df['macd_dif'].shift(1) <= df['macd_dea'].shift(1)) & (df['macd_dif'] > df['macd_dea'])
    macd_dif_positive = df['macd_dif'] > 0

    macd_buy_score = np.where(macd_golden_cross & macd_dif_positive, 3,  # 零轴上金叉
                     np.where(macd_golden_cross, 2,  # 普通金叉
                     np.where(macd_dif_positive, 1,  # DIF在零轴上
                              0)))

    # 4. KDJ低位金叉
    kdj_golden_cross = (df['kdj_k'].shift(1) <= df['kdj_d'].shift(1)) & (df['kdj_k'] > df['kdj_d'])
    kdj_low = df['kdj_j'] < 20

    kdj_buy_score = np.where(kdj_golden_cross & kdj_low, 2,  # 低位金叉
                    np.where(kdj_golden_cross, 1,  # 普通金叉
                             0))

    # 综合买入评分
    df['buy_score'] = bb_buy_score + rsi_buy_score + macd_buy_score + kdj_buy_score

    # ========== 卖出信号评分 ==========

    # 1. 布林带位置（权重最高）
    bb_sell_score = np.where(df['bb_position'] > 0.8, 3,  # 极度超买
                    np.where(df['bb_position'] > 0.7, 2,  # 偏高位
                    np.where(df['bb_position'] > 0.6, 1,  # 高位
                             0)))

    # 2. RSI超买
    rsi_sell_score = np.where(df['rsi'] > 70, 3,  # 强超买
                     np.where(df['rsi'] > 60, 2,  # 超买
                              0))

    # 3. MACD信号
    macd_death_cross = (df['macd_dif'].shift(1) >= df['macd_dea'].shift(1)) & (df['macd_dif'] < df['macd_dea'])
    macd_dif_negative = df['macd_dif'] < 0

    macd_sell_score = np.where(macd_death_cross & macd_dif_negative, 3,  # 零轴下死叉
                      np.where(macd_death_cross, 2,  # 普通死叉
                      np.where(macd_dif_negative, 1,  # DIF在零轴下
                               0)))

    # 4. KDJ高位死叉
    kdj_death_cross = (df['kdj_k'].shift(1) >= df['kdj_d'].shift(1)) & (df['kdj_k'] < df['kdj_d'])
    kdj_high = df['kdj_j'] > 80

    kdj_sell_score = np.where(kdj_death_cross & kdj_high, 2,  # 高位死叉
                     np.where(kdj_death_cross, 1,  # 普通死叉
                              0))

    # 综合卖出评分
    df['sell_score'] = bb_sell_score + rsi_sell_score + macd_sell_score + kdj_sell_score

    # ========== 生成最终信号 ==========

    # 买入信号（评分>=5）
    strong_buy = df['buy_score'] >= 7
    medium_buy = (df['buy_score'] >= 5) & (df['buy_score'] < 7)

    df.loc[strong_buy, 'signal'] = 2  # 强买入
    df.loc[strong_buy, 'signal_reason'] = '强买入(低位+多指标共振)'

    df.loc[medium_buy, 'signal'] = 1  # 买入
    df.loc[medium_buy, 'signal_reason'] = '买入(低位)'

    # 卖出信号（评分>=5）
    strong_sell = df['sell_score'] >= 7
    medium_sell = (df['sell_score'] >= 5) & (df['sell_score'] < 7)

    df.loc[strong_sell, 'signal'] = -2  # 强卖出
    df.loc[strong_sell, 'signal_reason'] = '强卖出(高位+多指标共振)'

    df.loc[medium_sell, 'signal'] = -1  # 卖出
    df.loc[medium_sell, 'signal_reason'] = '卖出(高位)'

    return df


def simple_backtest(df: pd.DataFrame, initial_capital: float = 10000,
                   stop_loss: float = 0.08) -> Dict:
    """简单回测引擎

    Args:
        df: 包含信号的数据
        initial_capital: 初始资金
        stop_loss: 止损比例
    """
    capital = initial_capital
    position = 0  # 持仓数量
    cost = 0  # 持仓成本

    trades = []
    equity_curve = []

    buy_positions = []  # 记录买入位置
    sell_positions = []  # 记录卖出位置

    for i in range(len(df)):
        row = df.iloc[i]
        price = row['close']
        signal = row['signal']

        # 计算当前权益
        current_value = capital + position * price
        equity_curve.append({
            'date': row['trade_date'],
            'equity': current_value,
            'price': price,
            'position': position
        })

        # 止损检查
        if position > 0:
            current_return = (price - cost) / cost
            if current_return < -stop_loss:
                # 止损卖出
                sell_value = position * price * 0.995  # 0.5%手续费
                capital += sell_value

                trades.append({
                    'date': row['trade_date'],
                    'type': 'SELL_STOP_LOSS',
                    'price': price,
                    'quantity': position,
                    'value': sell_value,
                    'pnl': sell_value - position * cost,
                    'return': current_return
                })

                sell_positions.append({
                    'date': row['trade_date'],
                    'price': price,
                    'bb_position': row['bb_position'],
                    'rsi': row.get('rsi', 50),
                    'sell_score': row.get('sell_score', 0)
                })

                position = 0
                cost = 0
                continue

        # 买入信号
        if signal > 0 and position == 0:
            # 全仓买入
            position = capital / price
            cost = price
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

        # 卖出信号
        elif signal < 0 and position > 0:
            # 全部卖出
            sell_value = position * price * 0.995  # 0.5%手续费
            pnl = sell_value - position * cost
            ret = pnl / (position * cost)

            capital += sell_value

            trades.append({
                'date': row['trade_date'],
                'type': 'SELL',
                'price': price,
                'quantity': position,
                'value': sell_value,
                'pnl': pnl,
                'return': ret,
                'signal_strength': signal,
                'reason': row['signal_reason']
            })

            sell_positions.append({
                'date': row['trade_date'],
                'price': price,
                'bb_position': row['bb_position'],
                'rsi': row['rsi'],
                'sell_score': row['sell_score']
            })

            position = 0
            cost = 0

    # 最终清算
    if position > 0:
        final_price = df.iloc[-1]['close']
        final_value = position * final_price * 0.995
        capital += final_value

    # 计算指标
    total_return = (capital - initial_capital) / initial_capital

    # 买入持有收益
    buy_hold_return = (df.iloc[-1]['close'] - df.iloc[0]['close']) / df.iloc[0]['close']

    # 计算平均买入/卖出位置
    avg_buy_bb = np.mean([p['bb_position'] for p in buy_positions]) if buy_positions else 0.5
    avg_sell_bb = np.mean([p['bb_position'] for p in sell_positions]) if sell_positions else 0.5

    avg_buy_rsi = np.mean([p['rsi'] for p in buy_positions]) if buy_positions else 50
    avg_sell_rsi = np.mean([p['rsi'] for p in sell_positions]) if sell_positions else 50

    # 胜率
    profitable_trades = [t for t in trades if t.get('pnl', 0) > 0]
    win_rate = len(profitable_trades) / len([t for t in trades if 'pnl' in t]) if trades else 0

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
        'avg_sell_rsi': avg_sell_rsi,
        'equity_curve': equity_curve,
        'trade_list': trades,
        'buy_positions': buy_positions,
        'sell_positions': sell_positions
    }


def backtest_macd_simple(df: pd.DataFrame, initial_capital: float = 10000) -> Dict:
    """MACD简单策略回测（用于对比）"""
    df = df.copy()
    df = MACDIndicators.calculate_macd(df)

    # 生成简单的金叉死叉信号
    df['signal'] = 0

    golden_cross = (df['macd_dif'].shift(1) <= df['macd_dea'].shift(1)) & (df['macd_dif'] > df['macd_dea'])
    death_cross = (df['macd_dif'].shift(1) >= df['macd_dea'].shift(1)) & (df['macd_dif'] < df['macd_dea'])

    df.loc[golden_cross, 'signal'] = 1
    df.loc[death_cross, 'signal'] = -1
    df['signal_reason'] = ''
    df.loc[golden_cross, 'signal_reason'] = 'MACD金叉'
    df.loc[death_cross, 'signal_reason'] = 'MACD死叉'

    # 添加布林带位置（用于统计）
    df = calculate_bollinger_position(df)
    df = calculate_rsi(df)
    df['buy_score'] = 0
    df['sell_score'] = 0

    return simple_backtest(df, initial_capital)


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
    print(f"平均买入位置: 布林带 {result_macd['avg_buy_bb_position']:.2f} | RSI {result_macd['avg_buy_rsi']:.1f}")
    print(f"平均卖出位置: 布林带 {result_macd['avg_sell_bb_position']:.2f} | RSI {result_macd['avg_sell_rsi']:.1f}")

    # 2. 低买高卖策略回测
    print(f"\n{'─'*80}")
    print("策略2: 低买高卖策略（布林带+MACD+RSI+KDJ）")
    print(f"{'─'*80}")

    df_lbhs = generate_low_buy_high_sell_signals(df.copy())
    result_lbhs = simple_backtest(df_lbhs)

    print(f"总收益率: {result_lbhs['total_return_pct']:.2f}%")
    print(f"买入持有: {result_lbhs['buy_hold_return_pct']:.2f}%")
    print(f"交易次数: {result_lbhs['trades']}")
    print(f"胜率: {result_lbhs['win_rate']*100:.1f}%")
    print(f"平均买入位置: 布林带 {result_lbhs['avg_buy_bb_position']:.2f} | RSI {result_lbhs['avg_buy_rsi']:.1f}")
    print(f"平均卖出位置: 布林带 {result_lbhs['avg_sell_bb_position']:.2f} | RSI {result_lbhs['avg_sell_rsi']:.1f}")

    # 3. 对比分析
    print(f"\n{'─'*80}")
    print("📊 策略对比分析")
    print(f"{'─'*80}")

    improvement = result_lbhs['total_return_pct'] - result_macd['total_return_pct']

    print(f"\n收益对比:")
    print(f"  MACD策略:    {result_macd['total_return_pct']:>8.2f}%")
    print(f"  低买高卖:    {result_lbhs['total_return_pct']:>8.2f}%")
    print(f"  改善幅度:    {improvement:>8.2f}% {'✅' if improvement > 0 else '❌'}")

    print(f"\n买卖位置对比（布林带0-1，越小越低）:")
    print(f"  {'策略':<15} {'平均买入位置':>12} {'平均卖出位置':>12} {'是否低买高卖':>12}")
    print(f"  {'─'*15} {'─'*12} {'─'*12} {'─'*12}")
    print(f"  {'MACD策略':<15} {result_macd['avg_buy_bb_position']:>12.2f} {result_macd['avg_sell_bb_position']:>12.2f} {'❌ 否' if result_macd['avg_buy_bb_position'] > result_macd['avg_sell_bb_position'] else '✅ 是':>12}")
    print(f"  {'低买高卖':<15} {result_lbhs['avg_buy_bb_position']:>12.2f} {result_lbhs['avg_sell_bb_position']:>12.2f} {'❌ 否' if result_lbhs['avg_buy_bb_position'] > result_lbhs['avg_sell_bb_position'] else '✅ 是':>12}")

    print(f"\nRSI位置对比（0-100，<30超卖，>70超买）:")
    print(f"  {'策略':<15} {'平均买入RSI':>12} {'平均卖出RSI':>12}")
    print(f"  {'─'*15} {'─'*12} {'─'*12}")
    print(f"  {'MACD策略':<15} {result_macd['avg_buy_rsi']:>12.1f} {result_macd['avg_sell_rsi']:>12.1f}")
    print(f"  {'低买高卖':<15} {result_lbhs['avg_buy_rsi']:>12.1f} {result_lbhs['avg_sell_rsi']:>12.1f}")

    print(f"\n胜率对比:")
    print(f"  MACD策略:    {result_macd['win_rate']*100:>6.1f}%")
    print(f"  低买高卖:    {result_lbhs['win_rate']*100:>6.1f}%")

    # 展示几个典型交易案例
    print(f"\n{'─'*80}")
    print("💡 典型交易案例（低买高卖策略）")
    print(f"{'─'*80}")

    if result_lbhs['buy_positions']:
        print(f"\n最低位买入（前3笔）:")
        sorted_buys = sorted(result_lbhs['buy_positions'], key=lambda x: x['bb_position'])[:3]
        for i, buy in enumerate(sorted_buys, 1):
            print(f"  {i}. {buy['date']} 价格:{buy['price']:.3f} 布林带位置:{buy['bb_position']:.2f} RSI:{buy['rsi']:.1f} 评分:{buy['buy_score']}")

    if result_lbhs['sell_positions']:
        print(f"\n最高位卖出（前3笔）:")
        sorted_sells = sorted(result_lbhs['sell_positions'], key=lambda x: x['bb_position'], reverse=True)[:3]
        for i, sell in enumerate(sorted_sells, 1):
            print(f"  {i}. {sell['date']} 价格:{sell['price']:.3f} 布林带位置:{sell['bb_position']:.2f} RSI:{sell['rsi']:.1f} 评分:{sell['sell_score']}")

    return {
        'etf_code': etf_code,
        'etf_name': etf_name,
        'macd': result_macd,
        'low_buy_high_sell': result_lbhs
    }


def main():
    """主函数"""
    print("\n" + "="*80)
    print(" "*25 + "低买高卖策略回测对比")
    print("="*80)

    # 测试3个ETF
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

    # 汇总对比
    print(f"\n\n{'='*80}")
    print(" "*30 + "📊 汇总对比")
    print(f"{'='*80}")

    print(f"\n{'ETF':<15} {'策略':<20} {'收益率':>10} {'买入位置':>10} {'卖出位置':>10} {'胜率':>8}")
    print(f"{'─'*15} {'─'*20} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")

    for r in results:
        print(f"{r['etf_name']:<15} {'MACD激进':<20} {r['macd']['total_return_pct']:>9.2f}% {r['macd']['avg_buy_bb_position']:>9.2f} {r['macd']['avg_sell_bb_position']:>9.2f} {r['macd']['win_rate']*100:>7.1f}%")
        print(f"{'':<15} {'低买高卖':<20} {r['low_buy_high_sell']['total_return_pct']:>9.2f}% {r['low_buy_high_sell']['avg_buy_bb_position']:>9.2f} {r['low_buy_high_sell']['avg_sell_bb_position']:>9.2f} {r['low_buy_high_sell']['win_rate']*100:>7.1f}%")
        improvement = r['low_buy_high_sell']['total_return_pct'] - r['macd']['total_return_pct']
        print(f"{'':<15} {'改善':<20} {improvement:>9.2f}% {'✅' if improvement > 0 else '❌'}")
        print()

    # 平均改善
    avg_macd = np.mean([r['macd']['total_return_pct'] for r in results])
    avg_lbhs = np.mean([r['low_buy_high_sell']['total_return_pct'] for r in results])
    avg_improvement = avg_lbhs - avg_macd

    print(f"\n{'平均收益':<15}")
    print(f"  MACD策略:    {avg_macd:>8.2f}%")
    print(f"  低买高卖:    {avg_lbhs:>8.2f}%")
    print(f"  平均改善:    {avg_improvement:>8.2f}% {'✅' if avg_improvement > 0 else '❌'}")

    print(f"\n{'='*80}")
    print("✅ 回测完成！")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
