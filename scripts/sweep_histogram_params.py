"""
Test MACD histogram momentum strategy with different filter parameters.
Searches for the best deadzone, confirmation, and smoothing configuration.
"""
import sys, pandas as pd, numpy as np
sys.path.insert(0, '.')
from core.database import get_etf_daily_data
from strategies.indicators import MACDIndicators


class ConfigurableGenerator:
    def __init__(self, deadzone=0, confirm_days=1, smooth=1, max_change=10):
        self.deadzone = deadzone
        self.confirm_days = confirm_days
        self.smooth = smooth
        self.max_change = max_change

    def generate(self, df):
        df = df.copy()
        df = MACDIndicators.calculate_macd(df, fast=12, slow=26, signal=9)
        df['ma20'] = df['close'].rolling(20, min_periods=1).mean()
        df['ma20_slope'] = 'FLAT'
        df.loc[df['ma20'] > df['ma20'].shift(5), 'ma20_slope'] = 'UP'
        df.loc[df['ma20'] < df['ma20'].shift(5), 'ma20_slope'] = 'DOWN'

        if self.smooth > 1:
            df['macd_hist'] = df['macd_hist'].ewm(span=self.smooth, adjust=False).mean()

        h = df['macd_hist']
        ah = h.abs()
        df['dir'] = 'FLAT'
        df.loc[ah > ah.shift(1), 'dir'] = 'EXPANDING'
        df.loc[ah < ah.shift(1), 'dir'] = 'SHRINKING'

        # Raw state
        raw = pd.Series('STRONG_BEAR', index=df.index)
        ju = (h > 0) & (h.shift(1) <= 0)
        jd = (h < 0) & (h.shift(1) >= 0)
        raw[(h > 0) & (df['dir'] == 'EXPANDING') & ~ju] = 'STRONG_BULL'
        raw[(h > 0) & (df['dir'] == 'SHRINKING') & ~jd] = 'BULL_WEAKENING'
        raw[(h < 0) & (df['dir'] == 'SHRINKING') & ~ju] = 'BEAR_TO_BULL'
        raw[ju] = 'JUST_CROSSED_UP'
        raw[jd] = 'JUST_CROSSED_DOWN'

        # Deadzone + confirmation
        state = pd.Series('STRONG_BEAR', index=df.index)
        cur = 'STRONG_BEAR'
        pending = None
        count = 0
        for i in range(len(df)):
            rs = raw.iloc[i]
            if self.deadzone > 0 and abs(h.iloc[i]) < self.deadzone:
                rs = cur
            if self.confirm_days <= 1:
                cur = rs
            else:
                if rs == pending:
                    count += 1
                    if count >= self.confirm_days:
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
            # acceleration
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
            if self.max_change < 10:
                prev = df.at[df.index[i-1], 'target_position']
                target = max(prev - self.max_change, min(prev + self.max_change, target))
            df.at[df.index[i], 'target_position'] = target
        return df


def backtest(df, capital=2000, positions=10, fee=0.005, stop_loss=0.10):
    ps = capital / positions
    cash, shares, used, avg_cost = capital, 0, 0, 0
    trades, pvs = [], []

    for i, row in df.iterrows():
        price, target = row['close'], int(row['target_position'])
        pnl = (price - avg_cost) / avg_cost if shares > 0 and avg_cost > 0 else 0

        if shares > 0 and pnl <= -stop_loss:
            cash += shares * price * (1 - fee)
            trades.append({'t': 'SELL', 'p': price, 'r': 'STOP', 's': shares})
            shares = used = avg_cost = 0
            pvs.append(cash)
            continue

        if target > used:
            to_add = target - used
            invest = to_add * ps
            if cash >= invest and price > 0:
                s = int(invest // price)
                if s > 0:
                    cost = s * price; cash -= cost
                    avg_cost = (avg_cost * shares + cost) / (shares + s) if shares + s > 0 else 0
                    shares += s; used += to_add
                    trades.append({'t': 'BUY', 'p': price, 'r': 'SIG', 's': s})
        elif target < used:
            to_close = used - target
            s = int(shares * (to_close / used))
            if s > 0:
                cash += s * price * (1 - fee)
                shares -= s; used -= to_close
                trades.append({'t': 'SELL', 'p': price, 'r': 'SIG', 's': s})
                if used == 0: avg_cost = 0
        pvs.append(cash + shares * price)

    fv = pvs[-1] if pvs else capital
    ret = (fv - capital) / capital * 100
    bh = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100
    churn = int(df['target_position'].diff().abs().sum())
    buys = [t for t in trades if t['t'] == 'BUY']
    sells = [t for t in trades if t['t'] == 'SELL']

    wins, total = 0, 0
    bp = [(t['p'], i) for i, t in enumerate(trades) if t['t'] == 'BUY']
    sp = [(t['p'], i) for i, t in enumerate(trades) if t['t'] == 'SELL']
    for sp_price, si in sp:
        prev = [bp_price for bp_price, bi in bp if bi < si]
        if prev and sp_price * (1 - fee) > prev[-1]:
            wins += 1
        total += 1
    wr = wins / total * 100 if total else 0

    return {'return': ret, 'bh': bh, 'trades': len(trades), 'buys': len(buys),
            'sells': len(sells), 'churn': churn, 'win_rate': wr}


print("MACD量能柱动量策略 - 参数扫描")
print("=" * 80)

# Load data
data = get_etf_daily_data('510330.SH', start_date='20200101')
df = pd.DataFrame(data)
print(f"数据: {len(df)}行, {df['trade_date'].iloc[0]} ~ {df['trade_date'].iloc[-1]}")

# Original baseline
from strategies.macd_histogram_momentum import MACDHistogramMomentumSignalGenerator
og = MACDHistogramMomentumSignalGenerator()
dfo = og.generate_signals(df.copy())
dfo = dfo.rename(columns={'trade_date': 'trade_date'})
br = backtest(dfo)
print(f"\nORIGINAL: return={br['return']:.2f}% bh={br['bh']:.2f}% trades={br['trades']} churn={br['churn']} win={br['win_rate']:.1f}%")

# Parameter sweep
grid = [
    (0.000, 1, 1, 10),  # baseline equivalent
    (0.005, 1, 1, 10), (0.010, 1, 1, 10), (0.015, 1, 1, 10), (0.020, 1, 1, 10), (0.030, 1, 1, 10),
    (0.005, 2, 1, 10), (0.010, 2, 1, 10), (0.015, 2, 1, 10), (0.020, 2, 1, 10),
    (0.010, 3, 1, 10), (0.015, 3, 1, 10), (0.020, 3, 1, 10),
    (0.010, 1, 2, 10), (0.015, 1, 2, 10), (0.010, 2, 2, 10), (0.015, 2, 2, 10),
    (0.015, 1, 1, 5), (0.015, 1, 1, 3), (0.015, 2, 1, 5), (0.015, 2, 1, 3),
    (0.020, 1, 1, 5), (0.020, 2, 1, 5), (0.020, 2, 1, 3),
]

results = []
for dz, cd, sw, mc in grid:
    gen = ConfigurableGenerator(deadzone=dz, confirm_days=cd, smooth=sw, max_change=mc)
    df_test = gen.generate(df.copy())
    r = backtest(df_test)
    r['dz'] = dz; r['cd'] = cd; r['sw'] = sw; r['mc'] = mc
    results.append(r)

results.sort(key=lambda x: x['return'], reverse=True)

print(f"\n{'Rank':<5} {'DZ':<8} {'CD':<6} {'SW':<6} {'MC':<6} {'Return%':<10} {'BH%':<10} {'vsBH':<8} {'Trades':<8} {'Churn':<8} {'Win%':<8}")
print("-" * 90)

for rank, r in enumerate(results[:25]):
    vs = r['return'] - r['bh']
    print(f"{rank+1:<5} {r['dz']:<8.3f} {r['cd']:<6} {r['sw']:<6} {r['mc']:<6} {r['return']:<10.2f} {r['bh']:<10.2f} {vs:<8.2f} {r['trades']:<8} {r['churn']:<8} {r['win_rate']:<8.1f}")

# Best by win rate
print(f"\n--- Best win rate ---")
by_wr = sorted(results, key=lambda x: x['win_rate'], reverse=True)
for r in by_wr[:5]:
    print(f"  win={r['win_rate']:.1f}% ret={r['return']:.2f}% dz={r['dz']:.3f} cd={r['cd']} sw={r['sw']} mc={r['mc']}")

# Best by fewest trades with positive return
print(f"\n--- Fewest trades (ret > 0) ---")
ft = sorted([r for r in results if r['return'] > 0], key=lambda x: x['trades'])
for r in ft[:5]:
    print(f"  trades={r['trades']} ret={r['return']:.2f}% win={r['win_rate']:.1f}% dz={r['dz']:.3f} cd={r['cd']} sw={r['sw']} mc={r['mc']}")

print(f"\n数据区间: 2020-01 ~ 2026-02 (完整牛熊周期)")
