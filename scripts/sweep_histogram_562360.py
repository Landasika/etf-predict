"""
Sweep MACD histogram momentum params on 562360.SH using the real backtester.
Matches web system conditions: 5% stop loss, 10%/20% take profit, 2025-01-01 start.
"""
import sys
import pandas as pd
import numpy as np
sys.path.insert(0, '.')
from core.database import get_etf_daily_data
from strategies.macd_histogram_momentum import MACDHistogramMomentumSignalGenerator
from strategies.macd_histogram_momentum_backtester import MACDHistogramMomentumBacktester


def run_backtest(etf_code, start_date, macd_fast, macd_slow, macd_signal,
                 deadzone=0, confirm_days=1, smooth=1, max_change=10):
    """Run a single backtest with given params."""
    data = get_etf_daily_data(etf_code, start_date=start_date)
    if not data or len(data) < 60:
        return None
    df = pd.DataFrame(data)
    df = df.rename(columns={'trade_date': 'date'})

    # Generate signals with custom params
    gen = MACDHistogramMomentumSignalGenerator(params={
        'macd_fast': macd_fast, 'macd_slow': macd_slow, 'macd_signal': macd_signal,
        'deadzone': deadzone, 'confirm_days': confirm_days, 'smooth': smooth,
        'max_change': max_change,
    })

    # We need to modify the generator to accept these params
    # For now, manually apply the logic
    df = _generate_with_params(df, macd_fast, macd_slow, macd_signal,
                                deadzone, confirm_days, smooth, max_change)

    # Shift target_position to avoid look-ahead
    df['target_position'] = df['target_position'].shift(1).fillna(0).astype(int)

    bt = MACDHistogramMomentumBacktester(
        initial_capital=2000, num_positions=10, sell_fee=0.005,
        stop_loss_pct=0.05, take_profit_pct1=0.10, take_profit_pct2=0.20,
    )
    trades, perf = bt._execute_trades(df)
    metrics = bt._calculate_metrics(trades, perf, df)
    return metrics


def _generate_with_params(df, macd_fast, macd_slow, macd_signal,
                          deadzone, confirm_days, smooth, max_change):
    """Generate signals with tunable params (mirrors ConfigurableGenerator logic)."""
    from strategies.indicators import MACDIndicators

    df = df.copy()
    df = MACDIndicators.calculate_macd(df, fast=macd_fast, slow=macd_slow, signal=macd_signal)
    df['ma20'] = df['close'].rolling(20, min_periods=1).mean()
    df['ma20_slope'] = 'FLAT'
    df.loc[df['ma20'] > df['ma20'].shift(5), 'ma20_slope'] = 'UP'
    df.loc[df['ma20'] < df['ma20'].shift(5), 'ma20_slope'] = 'DOWN'

    if smooth > 1:
        df['macd_hist'] = df['macd_hist'].ewm(span=smooth, adjust=False).mean()

    h = df['macd_hist']
    ah = h.abs()
    df['dir'] = 'FLAT'
    df.loc[ah > ah.shift(1), 'dir'] = 'EXPANDING'
    df.loc[ah < ah.shift(1), 'dir'] = 'SHRINKING'

    raw = pd.Series('STRONG_BEAR', index=df.index)
    ju = (h > 0) & (h.shift(1) <= 0)
    jd = (h < 0) & (h.shift(1) >= 0)
    raw[(h > 0) & (df['dir'] == 'EXPANDING') & ~ju] = 'STRONG_BULL'
    raw[(h > 0) & (df['dir'] == 'SHRINKING') & ~jd] = 'BULL_WEAKENING'
    raw[(h < 0) & (df['dir'] == 'SHRINKING') & ~ju] = 'BEAR_TO_BULL'
    raw[ju] = 'JUST_CROSSED_UP'
    raw[jd] = 'JUST_CROSSED_DOWN'

    state = pd.Series('STRONG_BEAR', index=df.index)
    cur = 'STRONG_BEAR'
    pending = None
    count = 0
    for i in range(len(df)):
        rs = raw.iloc[i]
        if deadzone > 0 and abs(h.iloc[i]) < deadzone:
            rs = cur
        if confirm_days <= 1:
            cur = rs
        else:
            if rs == pending:
                count += 1
                if count >= confirm_days:
                    cur = rs; pending = None; count = 0
            else:
                pending = rs; count = 1
        state.iloc[i] = cur
    df['hist_state'] = state

    BASE = {'STRONG_BULL': 9, 'BULL_WEAKENING': 4, 'BEAR_TO_BULL': 2,
            'STRONG_BEAR': 0, 'JUST_CROSSED_UP': 6, 'JUST_CROSSED_DOWN': 1}

    df['target_position'] = 0
    for i in range(35, len(df)):
        row = df.iloc[i]
        base = BASE.get(row['hist_state'], 0)
        accel = 0
        if i >= 2:
            d1 = ah.iloc[i] - ah.iloc[i-1]
            d2 = ah.iloc[i-1] - ah.iloc[i-2]
            if d1 > 0 and d2 > 0 and d1 > d2: accel = 2
            elif d1 < 0 and d2 < 0 and d1 < d2: accel = -2
        pre = base + accel
        if row['close'] < row['ma20']:
            pre = min(pre, 5)
        adj = 0
        if row['close'] > row['ma20']: adj += 1
        if row['ma20_slope'] == 'UP': adj += 1
        elif row['ma20_slope'] == 'DOWN': adj -= 1
        target = max(0, min(10, int(round(pre + adj))))
        if max_change < 10:
            prev = df.at[df.index[i-1], 'target_position']
            target = max(prev - max_change, min(prev + max_change, target))
        df.at[df.index[i], 'target_position'] = target
    return df


print("MACD柱动量策略 - 562360.SH 参数扫描 (web系统同等条件)")
print("=" * 90)
print("条件: 2025-01-01起, 5%止损, 10%/20%分批止盈, 2000初始资金")
print()

# Baseline: MACD aggressive on 562360.SH (for comparison)
print("--- 基准: MACD激进策略 (优化参数 20/38/11) ---")
from strategies.backtester import MACDBacktester
from strategies.strategies import get_strategy_params
params_agg = get_strategy_params('aggressive')
params_agg.update({'macd_fast': 20, 'macd_slow': 38, 'macd_signal': 11})
bt_agg = MACDBacktester(initial_capital=2000, num_positions=10, sell_fee=0.005,
                         stop_loss_pct=0.05, take_profit_pct1=0.10, take_profit_pct2=0.20)
r_agg = bt_agg.run_backtest('562360.SH', strategy_params=params_agg, start_date='20250101')
m_agg = r_agg['metrics']
print(f"MACD激进: return={m_agg['total_return_pct']:.2f}% bh={m_agg['buy_hold_return_pct']:.2f}% "
      f"trades={m_agg['total_trades']} win={m_agg['win_rate']*100:.1f}% sharpe={m_agg['sharpe_ratio']:.2f}")
print()

# Step 1: Sweep MACD params with default histogram settings
print("--- Step 1: MACD参数扫描 (柱动量默认设置) ---")
macd_grid = [
    (8, 17, 5), (12, 26, 9), (14, 30, 9), (16, 32, 9),
    (18, 35, 9), (20, 38, 11), (22, 44, 11), (24, 50, 11),
    (10, 20, 5), (6, 13, 5), (26, 52, 11),
]
results_macd = []
for fast, slow, sig in macd_grid:
    m = run_backtest('562360.SH', '20250101', fast, slow, sig)
    if m:
        results_macd.append((fast, slow, sig, m['total_return_pct'], m['total_trades'],
                             m['win_rate_pct'], m['sharpe_ratio'], m['max_drawdown_pct']))

results_macd.sort(key=lambda x: x[3], reverse=True)
print(f"{'Fast':<6} {'Slow':<6} {'Sig':<6} {'Return%':<10} {'Trades':<8} {'Win%':<8} {'Sharpe':<8} {'MDD%':<8}")
print("-" * 70)
for r in results_macd:
    print(f"{r[0]:<6} {r[1]:<6} {r[2]:<6} {r[3]:<10.2f} {r[4]:<8} {r[5]:<8.1f} {r[6]:<8.2f} {r[7]:<8.2f}")

best_macd = results_macd[0]
print(f"\n最佳MACD: ({best_macd[0]}, {best_macd[1]}, {best_macd[2]}) -> {best_macd[3]:.2f}%")

# Step 2: With best MACD, sweep histogram params
print(f"\n--- Step 2: 柱状态参数扫描 (MACD={best_macd[0]}/{best_macd[1]}/{best_macd[2]}) ---")
bf, bs, bsg = best_macd[0], best_macd[1], best_macd[2]

hist_grid = [
    (0.000, 1, 1, 10),
    (0.005, 1, 1, 10), (0.010, 1, 1, 10), (0.015, 1, 1, 10),
    (0.020, 1, 1, 10), (0.030, 1, 1, 10), (0.040, 1, 1, 10),
    (0.010, 2, 1, 10), (0.015, 2, 1, 10), (0.020, 2, 1, 10), (0.030, 2, 1, 10),
    (0.010, 3, 1, 10), (0.015, 3, 1, 10), (0.020, 3, 1, 10), (0.030, 3, 1, 10),
    (0.015, 1, 1, 5), (0.015, 1, 1, 3),
    (0.020, 1, 1, 5), (0.020, 2, 1, 5),
    (0.020, 2, 2, 10), (0.020, 3, 2, 10),
    (0.030, 2, 2, 10), (0.030, 3, 2, 10),
]

results_hist = []
for dz, cd, sw, mc in hist_grid:
    m = run_backtest('562360.SH', '20250101', bf, bs, bsg, dz, cd, sw, mc)
    if m:
        results_hist.append((dz, cd, sw, mc, m['total_return_pct'], m['total_trades'],
                             m['win_rate_pct'], m['sharpe_ratio'], m['max_drawdown_pct']))

results_hist.sort(key=lambda x: x[4], reverse=True)
print(f"{'DZ':<8} {'CD':<6} {'SW':<6} {'MC':<6} {'Return%':<10} {'Trades':<8} {'Win%':<8} {'Sharpe':<8} {'MDD%':<8}")
print("-" * 80)
for r in results_hist[:20]:
    print(f"{r[0]:<8.3f} {r[1]:<6} {r[2]:<6} {r[3]:<6} {r[4]:<10.2f} {r[5]:<8} {r[6]:<8.1f} {r[7]:<8.2f} {r[8]:<8.2f}")

best = results_hist[0]
print(f"\n=== 最优配置 ===")
print(f"MACD: ({bf}, {bs}, {bsg})")
print(f"死区={best[0]:.3f} 确认={best[1]} 平滑={best[2]} 仓位限制={best[3]}")
print(f"收益={best[4]:.2f}% 交易={best[5]} 胜率={best[6]:.1f}% 夏普={best[7]:.2f} 最大回撤={best[8]:.2f}%")
print(f"vs MACD激进={m_agg['total_return_pct']:.2f}%")
