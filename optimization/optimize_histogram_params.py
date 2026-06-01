"""
Differential evolution optimizer for MACD Histogram Momentum strategy.
Optimizes per-ETF: MACD params + deadzone + confirmation + smoothing + max_change.
Uses scipy.optimize.differential_evolution for global optimization.
"""
import sys
sys.path.insert(0, '.')
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from scipy.optimize import differential_evolution

from core.database import get_etf_daily_data
from strategies.indicators import MACDIndicators
from strategies.macd_histogram_momentum_backtester import MACDHistogramMomentumBacktester


class HistogramParamOptimizer:
    """Differential evolution optimizer for histogram momentum strategy parameters."""

    def __init__(self, etf_code: str, start_date: str = '20250101',
                 population_size: int = 30, max_iter: int = 30):
        self.etf_code = etf_code
        self.start_date = start_date
        self.population_size = population_size
        self.max_iter = max_iter

        # Use data/ dir (writable) since optimized_weights/ may be root-owned from Docker
        self.output_dir = Path(f"data/optimized_histogram/{etf_code}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Bounds: [macd_fast, macd_slow, macd_signal, deadzone, confirm_days, smooth, max_change]
        self.bounds = [
            (5, 26),      # macd_fast
            (13, 55),     # macd_slow
            (3, 13),      # macd_signal
            (0.0, 0.05),  # deadzone
            (1, 5),       # confirm_days
            (1, 3),       # smooth
            (2, 10),      # max_change
        ]

    def _load_data(self) -> pd.DataFrame:
        data = get_etf_daily_data(self.etf_code, start_date=self.start_date)
        if not data or len(data) < 100:
            raise ValueError(f"数据不足: {len(data) if data else 0}天")
        return pd.DataFrame(data)

    def _decode_params(self, x: np.ndarray) -> dict:
        return {
            'macd_fast': int(round(x[0])),
            'macd_slow': int(round(x[1])),
            'macd_signal': int(round(x[2])),
            'deadzone': float(x[3]),
            'confirm_days': int(round(x[4])),
            'smooth': int(round(x[5])),
            'max_change': int(round(x[6])),
        }

    def _ensure_valid(self, params: dict) -> dict:
        if params['macd_fast'] >= params['macd_slow']:
            params['macd_slow'] = params['macd_fast'] + 5
        if params['macd_signal'] >= params['macd_slow']:
            params['macd_signal'] = max(3, params['macd_slow'] - 3)
        params['deadzone'] = max(0, min(0.05, params['deadzone']))
        params['confirm_days'] = max(1, min(5, params['confirm_days']))
        params['smooth'] = max(1, min(3, params['smooth']))
        params['max_change'] = max(2, min(10, params['max_change']))
        return params

    def _generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        fast = params['macd_fast']
        slow = params['macd_slow']
        sig = params['macd_signal']
        deadzone = params['deadzone']
        confirm_days = params['confirm_days']
        smooth = params['smooth']
        max_change = params['max_change']

        df = MACDIndicators.calculate_macd(df, fast=fast, slow=slow, signal=sig)
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

    def _evaluate_params(self, params: dict, df: pd.DataFrame) -> Tuple[float, dict]:
        df_signals = self._generate_signals(df, params)
        if 'trade_date' in df_signals.columns:
            df_signals = df_signals.rename(columns={'trade_date': 'date'})
        df_signals['target_position'] = df_signals['target_position'].shift(1).fillna(0).astype(int)

        bt = MACDHistogramMomentumBacktester(
            initial_capital=2000, num_positions=10, sell_fee=0.005,
            stop_loss_pct=0.05, take_profit_pct1=0.10, take_profit_pct2=0.20,
        )
        trades, perf = bt._execute_trades(df_signals)
        metrics = bt._calculate_metrics(trades, perf, df_signals)

        ret = metrics['total_return_pct']
        sharpe = metrics['sharpe_ratio']
        trades_count = metrics['total_trades']

        if trades_count < 5:
            trade_penalty = 50
        elif trades_count > 200:
            trade_penalty = (trades_count - 200) * 0.1
        else:
            trade_penalty = 0

        # Minimize negative fitness (scipy minimizes)
        fitness = -(ret + sharpe * 5 - trade_penalty)
        return fitness, metrics

    def _update_watchlist(self, params: dict, metrics: dict):
        """Write optimized params back to watchlist_etfs.json."""
        watchlist_file = Path('data/watchlist_etfs.json')
        if not watchlist_file.exists():
            print("⚠️ watchlist文件不存在，跳过更新")
            return

        with open(watchlist_file, 'r') as f:
            wl = json.load(f)

        updated = False
        for etf in wl.get('etfs', []):
            if etf['code'] == self.etf_code:
                etf['optimized_histogram_params'] = params
                etf['_histogram_metrics'] = {
                    'total_return_pct': metrics['total_return_pct'],
                    'sharpe_ratio': metrics['sharpe_ratio'],
                    'win_rate_pct': metrics['win_rate_pct'],
                    'total_trades': metrics['total_trades'],
                }
                updated = True
                break

        if updated:
            with open(watchlist_file, 'w') as f:
                json.dump(wl, f, indent=2, ensure_ascii=False)
            print(f"✅ 已更新 watchlist: {self.etf_code} optimized_histogram_params")

    def optimize(self) -> Dict:
        print(f"\n{'='*70}")
        print(f"柱动量策略差分进化优化: {self.etf_code}")
        print(f"{'='*70}")
        print(f"种群: {self.population_size}, 迭代: {self.max_iter}")

        df = self._load_data()
        print(f"数据: {len(df)}行, {df['trade_date'].iloc[0]} ~ {df['trade_date'].iloc[-1]}")

        # Track the best result seen across all evaluations
        self._best_score = float('inf')
        self._best_params = None
        self._eval_count = 0

        def objective(x):
            params = self._decode_params(x)
            params = self._ensure_valid(params)
            fitness, metrics = self._evaluate_params(params, df)
            self._eval_count += 1
            if fitness < self._best_score:
                self._best_score = fitness
                self._best_params = params
                if self._eval_count % 10 == 0:
                    print(f"  评估#{self._eval_count}: 收益={metrics['total_return_pct']:.2f}% "
                          f"夏普={metrics['sharpe_ratio']:.2f} 交易={metrics['total_trades']} "
                          f"参数={params}")
            return fitness

        print(f"\n开始差分进化...")
        result = differential_evolution(
            objective,
            bounds=self.bounds,
            strategy='best1bin',
            maxiter=self.max_iter,
            popsize=self.population_size,
            mutation=(0.5, 1.5),
            recombination=0.7,
            seed=42,
            tol=0.01,
            polish=False,
        )

        best_params = self._decode_params(result.x)
        best_params = self._ensure_valid(best_params)

        # Final evaluation on full data
        print(f"\n{'='*70}")
        print(f"最终评估")
        print(f"{'='*70}")

        _, final_metrics = self._evaluate_params(best_params, df)

        print(f"总评估次数: {self._eval_count}")
        print(f"最优参数: {best_params}")
        print(f"总收益: {final_metrics['total_return_pct']:.2f}%")
        print(f"买入持有: {final_metrics['buy_hold_return_pct']:.2f}%")
        print(f"夏普: {final_metrics['sharpe_ratio']:.2f}")
        print(f"交易次数: {final_metrics['total_trades']}")
        print(f"胜率: {final_metrics['win_rate_pct']:.1f}%")
        print(f"最大回撤: {final_metrics['max_drawdown_pct']:.2f}%")

        result_data = {
            'etf_code': self.etf_code,
            'optimization_date': datetime.now().isoformat(),
            'params': best_params,
            'metrics': final_metrics,
            'evaluations': self._eval_count,
        }

        self._save_result(result_data)
        return result_data

    def _save_result(self, result: Dict):
        params_file = self.output_dir / "best_params.json"
        report_file = self.output_dir / "optimization_report.json"

        m = result['metrics']
        output = {
            'etf_code': result['etf_code'],
            'optimization_date': result['optimization_date'],
            'params': result['params'],
            'metrics': {
                'total_return_pct': m['total_return_pct'],
                'buy_hold_return_pct': m['buy_hold_return_pct'],
                'sharpe_ratio': m['sharpe_ratio'],
                'win_rate_pct': m['win_rate_pct'],
                'max_drawdown_pct': m['max_drawdown_pct'],
                'total_trades': m['total_trades'],
                'stop_loss_count': m['stop_loss_count'],
                'take_profit_count': m['take_profit_count'],
            },
            'evaluations': result['evaluations'],
        }

        with open(params_file, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        with open(report_file, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        print(f"\n结果已保存: {params_file}")

        # Write back to watchlist
        self._update_watchlist(result['params'], output['metrics'])


def optimize_single(etf_code: str, start_date: str = '20250101',
                    pop_size: int = 30, max_iter: int = 30):
    opt = HistogramParamOptimizer(etf_code, start_date, pop_size, max_iter)
    return opt.optimize()


def batch_optimize(etf_codes: List[str] = None, start_date: str = '20250101',
                   pop_size: int = 25, max_iter: int = 25):
    if etf_codes is None:
        with open('data/watchlist_etfs.json') as f:
            wl = json.load(f)
        etf_codes = [e['code'] for e in wl.get('etfs', [])]

    results = {}
    for i, code in enumerate(etf_codes):
        print(f"\n{'#'*70}")
        print(f"[{i+1}/{len(etf_codes)}] 优化 {code}")
        print(f"{'#'*70}")
        try:
            result = optimize_single(code, start_date, pop_size, max_iter)
            results[code] = result
        except Exception as e:
            print(f"X {code} 优化失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*70}")
    print(f"批量优化总结")
    print(f"{'='*70}")
    print(f"{'ETF':<15} {'收益%':<10} {'夏普':<8} {'胜率%':<8} {'交易':<8} {'MACD参数':<22} {'DZ':<8}")
    print("-" * 90)
    for code, r in results.items():
        p = r['params']
        m = r['metrics']
        macd_str = f"{p['macd_fast']}/{p['macd_slow']}/{p['macd_signal']}"
        print(f"{code:<15} {m['total_return_pct']:<10.2f} {m['sharpe_ratio']:<8.2f} "
              f"{m['win_rate_pct']:<8.1f} {m['total_trades']:<8} {macd_str:<22} {p['deadzone']:<8.4f}")

    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='柱动量策略差分进化参数优化')
    parser.add_argument('--etf', type=str, default=None,
                       help='ETF code. If omitted, batch optimize all.')
    parser.add_argument('--start', type=str, default='20250101')
    parser.add_argument('--pop', type=int, default=25)
    parser.add_argument('--iter', type=int, default=25)
    args = parser.parse_args()

    if args.etf:
        optimize_single(args.etf, args.start, args.pop, args.iter)
    else:
        batch_optimize(start_date=args.start, pop_size=args.pop, max_iter=args.iter)
