"""Homepage position signal row generation."""
from datetime import datetime, time

import config
from core import database, position_manager, watchlist
from core.profit_calculator import (
    calculate_daily_profit,
    calculate_monthly_profit_from_rows,
    normalize_trade_date,
)


POSITION_GRID_LOCK_TIME = time(15, 5)


def _is_after_position_grid_lock_time(now=None) -> bool:
    now = now or datetime.now()
    return now.time() >= POSITION_GRID_LOCK_TIME


def _can_recompute_position_grid(
    refresh: bool = False,
    realtime: bool = False,
    cached: dict | None = None,
    now=None,
) -> bool:
    """Whitelist conditions that may change the homepage position grid."""
    if cached and _is_after_position_grid_lock_time(now):
        return False
    if realtime:
        return True
    if refresh:
        return True
    return cached is None


def _get_position_snapshots_for_profit(etf_code: str, data_date: str) -> dict:
    cutoff = normalize_trade_date(data_date)
    if not cutoff:
        return {}

    conn = position_manager._get_conn()
    rows = conn.execute(
        """
        SELECT trade_date, positions
        FROM position_snapshots
        WHERE etf_code = ? AND trade_date <= ?
        ORDER BY trade_date
        """,
        (etf_code, cutoff),
    ).fetchall()
    conn.close()
    return {row['trade_date']: row['positions'] for row in rows}


def calculate_monthly_profit(etf_code: str, data_date: str, fallback_positions: int = 0) -> float:
    try:
        daily_rows = database.get_etf_daily_data(etf_code)
        snapshots = _get_position_snapshots_for_profit(etf_code, data_date)
        return calculate_monthly_profit_from_rows(
            daily_rows=daily_rows,
            snapshot_positions=snapshots,
            fallback_positions=fallback_positions,
            data_date=data_date,
        )
    except Exception:
        return 0.0


def _get_signal_name(signal_type: str) -> str:
    signal_map = {
        'BUY': '买入',
        'SELL': '卖出',
        'HOLD': '持有',
    }
    return signal_map.get(signal_type, '持有')


def _get_kdj_status(k_value: float, j_value: float) -> str:
    if k_value > 85 or j_value > 110:
        return '严重超买'
    if k_value > 80 or j_value > 100:
        return '超买'
    if k_value < 20:
        return '超卖'
    return '正常'


def _get_macd_params_display(etf: dict) -> dict:
    optimized_params = etf.get('optimized_macd_params')
    if optimized_params:
        return {
            'fast': optimized_params.get('macd_fast', 8),
            'slow': optimized_params.get('macd_slow', 17),
            'signal': optimized_params.get('macd_signal', 5),
            'is_optimized': True,
        }
    return {
        'fast': 8,
        'slow': 17,
        'signal': 5,
        'is_optimized': False,
    }


def _cached_batch_signals_response(cached: dict, data_date: str) -> dict:
    db_positions = {p['etf_code']: p for p in position_manager.get_all_positions()}
    for row in cached.get('data', []):
        db = db_positions.get(row.get('code', ''), {})
        row['db_position'] = db.get('current_positions', 0)
        row['db_shares'] = db.get('total_shares', 0)
        row['db_avg_cost'] = db.get('avg_cost', 0)
        if 'monthly_profit' not in row:
            row['monthly_profit'] = calculate_monthly_profit(
                row.get('code', ''),
                row.get('data_date') or data_date,
                row['db_position'],
            )
    return {
        'success': True,
        'data': cached.get('data', []),
        'count': cached.get('count', 0),
        'cached': True,
        'data_date': data_date,
    }


def _calculate_daily_change_pct(etf_code: str) -> float:
    try:
        recent_data = database.get_etf_daily_data(etf_code)
        if recent_data and len(recent_data) >= 2:
            today_close = float(recent_data[-1].get('close', 0))
            yesterday_close = float(recent_data[-2].get('close', 0))
            if yesterday_close > 0:
                return ((today_close - yesterday_close) / yesterday_close) * 100
    except Exception:
        pass
    return 0.0


def _get_current_db_positions(etf_code: str) -> int:
    try:
        pos = position_manager.get_position(etf_code)
        if pos:
            return pos.get('current_positions', 0)
    except Exception:
        pass
    return 0


def _get_action_reason(today_action: int, latest_data: dict, current_positions: int) -> str:
    if today_action > 0:
        if latest_data.get('signal_type') == 'BUY':
            strength = latest_data.get('signal_strength', 0)
            if strength >= 10:
                return '回踩MA60未破+MACD金叉，最强买入信号'
            if strength >= 9:
                return '正鸭嘴形态，强烈看多'
            if strength >= 8:
                return '零轴上方金叉，上升趋势明确'
            return 'MACD金叉买入'
        return '加仓买入'

    if today_action < 0:
        macd_dif = latest_data.get('macd_dif', 0)
        macd_dea = latest_data.get('macd_dea', 0)
        kdj_k = latest_data.get('kdj_k', 0)
        kdj_status = '严重超买' if kdj_k > 80 else ('超买' if kdj_k > 70 else '正常')

        if kdj_status == '严重超买':
            return f'KDJ{kdj_status}，止盈减仓'
        if macd_dif < macd_dea:
            return 'MACD死叉，减仓避险'
        if current_positions > 7:
            return '涨幅较大，分批止盈'
        return '信号转弱，减仓保住利润'

    return '保持现有仓位'


def _get_today_operation(today_action: int) -> str:
    if today_action > 0:
        return f'买入{today_action}仓'
    if today_action < 0:
        return f'卖出{abs(today_action)}仓'
    return '持有'


def _merge_db_positions(rows: list[dict]) -> None:
    db_positions = {p['etf_code']: p for p in position_manager.get_all_positions()}
    for row in rows:
        db = db_positions.get(row['code'], {})
        row['db_position'] = db.get('current_positions', 0)
        row['db_shares'] = db.get('total_shares', 0)
        row['db_avg_cost'] = db.get('avg_cost', 0)


def build_position_signal_rows(
    refresh: bool = False,
    realtime: bool = False,
    include_cached: bool = True,
) -> dict:
    """Build homepage position signal rows for all watchlist ETFs."""
    data_date = database.get_latest_data_date()
    if not data_date:
        return {
            'success': False,
            'message': '无法获取数据日期',
        }

    start_date_str = config.DEFAULT_START_DATE
    cache_data_date = f"{data_date}_{start_date_str}"
    cached = database.get_batch_cache('signals', cache_data_date) if include_cached else None

    if include_cached and not _can_recompute_position_grid(
        refresh=refresh,
        realtime=realtime,
        cached=cached,
    ):
        return _cached_batch_signals_response(cached, data_date)

    if realtime:
        database.clear_batch_cache()

    watchlist_data = watchlist.load_watchlist()
    results = []

    for etf in watchlist_data.get('etfs', []):
        etf_code = etf['code']
        strategy = etf.get('strategy', 'macd_aggressive')

        etf_info = database.get_etf_info(etf_code)
        if not etf_info:
            continue

        signal_result = watchlist.calculate_realtime_signal(etf_code, start_date_str, strategy)
        if not signal_result['success']:
            continue

        signal_data = signal_result['data']
        latest_data = signal_data.get('latest_data', {})
        backtest_summary = signal_data.get('backtest_summary', {})

        daily_change_pct = _calculate_daily_change_pct(etf_code)
        previous_positions = _get_current_db_positions(etf_code)
        daily_profit = calculate_daily_profit(previous_positions, daily_change_pct)
        monthly_profit = calculate_monthly_profit(
            etf_code,
            signal_data.get('latest_date', data_date),
            previous_positions,
        )

        kdj_k = latest_data.get('kdj_k', 0)
        kdj_d = latest_data.get('kdj_d', 0)
        kdj_j = latest_data.get('kdj_j', 0)
        kdj_data = {
            'k': kdj_k,
            'd': kdj_d,
            'j': kdj_j,
            'status': _get_kdj_status(kdj_k, kdj_j),
            'fusion_level': latest_data.get('fusion_level', 0),
            'position_cap': latest_data.get('kdj_position_cap', 10),
        }

        current_positions = signal_data.get('positions_used', 0)
        today_action = current_positions - previous_positions
        action_reason = _get_action_reason(today_action, latest_data, current_positions)
        today_operation = _get_today_operation(today_action)

        results.append({
            'code': etf_code,
            'name': etf_info.get('extname', etf_code),
            'strategy': strategy,
            'strategy_name': etf.get('strategy_name', strategy),
            'signal': latest_data.get('signal_type', 'HOLD'),
            'signal_name': _get_signal_name(latest_data.get('signal_type', 'HOLD')),
            'signal_strength': latest_data.get('signal_strength', 0),
            'today_operation': today_operation,
            'today_action_count': today_action,
            'action_reason': action_reason,
            'profit_value': signal_data.get('profit', 0),
            'profit_pct': signal_data.get('profit_pct', 0),
            'benchmark_return': backtest_summary.get('buy_hold_return_pct', 0) or 0,
            'positions_used': signal_data.get('positions_used', 0),
            'total_positions': etf.get('total_positions', 10),
            'next_action': signal_data.get('next_action', '--'),
            'macd': {
                'dif': latest_data.get('macd_dif', 0),
                'dea': latest_data.get('macd_dea', 0),
                'hist': latest_data.get('macd_hist', 0),
            },
            'macd_params': _get_macd_params_display(etf),
            'kdj': kdj_data,
            'price': latest_data.get('close', 0),
            'daily_change_pct': daily_change_pct,
            'daily_profit': daily_profit,
            'monthly_profit': monthly_profit,
            'latest_data': latest_data,
            'position_value': etf.get('position_value', 0),
            'data_date': signal_data.get('latest_date', data_date),
            'remark': etf.get('remark', ''),
        })

    if not realtime:
        database.set_batch_cache('signals', cache_data_date, {
            'data': results,
            'count': len(results),
        })

    _merge_db_positions(results)
    return {
        'success': True,
        'data': results,
        'count': len(results),
        'cached': False,
        'data_date': data_date,
    }


def build_feishu_operation_rows() -> dict:
    """Build operation rows shaped for Feishu operation reports."""
    result = build_position_signal_rows(refresh=False, realtime=False, include_cached=True)
    if not result.get('success'):
        return result

    rows = []
    for row in result.get('data', []):
        latest_data = row.get('latest_data', {})
        rows.append({
            'code': row.get('code', ''),
            'name': row.get('name', row.get('code', '')),
            'close': row.get('price', 0),
            'pct_chg': row.get('daily_change_pct', 0),
            'previous_positions_used': row.get('db_position', 0),
            'positions_used': row.get('positions_used', 0),
            'daily_profit': row.get('daily_profit', 0),
            'monthly_profit': row.get('monthly_profit', 0),
            'today_action_count': row.get('today_action_count', 0),
            'today_operation': row.get('today_operation', '持有'),
            'action_reason': row.get('action_reason', ''),
            'next_action': row.get('next_action', '--'),
            'signal_type': row.get('signal', latest_data.get('signal_type', 'HOLD')),
            'signal_strength': row.get('signal_strength', 0),
            'total_positions': row.get('total_positions', 10),
            'data_date': row.get('data_date', result.get('data_date', '')),
            'remark': row.get('remark', ''),
        })

    return {
        'success': True,
        'data': rows,
        'count': len(rows),
        'cached': result.get('cached', False),
        'data_date': result.get('data_date', ''),
    }
