"""
Regression tests for backtester performance snapshots.
"""
import pandas as pd

from strategies.backtester import MACDBacktester


def test_stop_loss_day_is_kept_in_performance():
    """止损卖出当天也必须保留仓位快照。"""
    backtester = MACDBacktester(initial_capital=2000, num_positions=10, stop_loss_pct=0.10)
    data = pd.DataFrame([
        {'date': '20260302', 'close': 100.0, 'vol': 1000, 'signal_strength': 6},
        {'date': '20260303', 'close': 90.0, 'vol': 1000, 'signal_strength': 0},
    ])

    trades, performance = backtester._execute_trades(data)

    assert [trade['type'] for trade in trades] == ['BUY', 'SELL']
    assert performance['date'].tolist() == ['20260302', '20260303']
    assert performance.iloc[-1]['positions_used'] == 0


def test_take_profit_level_two_day_is_kept_in_performance():
    """二级止盈当天不能从 performance 序列里消失。"""
    backtester = MACDBacktester(initial_capital=2000, num_positions=10)
    data = pd.DataFrame([
        {'date': '20260302', 'close': 100.0, 'vol': 1000, 'signal_strength': 10},
        {'date': '20260303', 'close': 130.0, 'vol': 1000, 'signal_strength': 0},
    ])

    trades, performance = backtester._execute_trades(data)

    assert [trade['type'] for trade in trades] == ['BUY', 'SELL']
    assert trades[-1]['reason'] == 'TAKE_PROFIT_2'
    assert performance['date'].tolist() == ['20260302', '20260303']
    assert performance.iloc[-1]['positions_used'] == 7
