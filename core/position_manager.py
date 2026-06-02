"""
Position & Trade Manager

Database-backed position tracking and trade history.
Positions persist across strategy changes - new signals compare against DB state.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = Path("data/etf.db")


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_tables():
    """Create positions and trade_log tables if not exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS positions (
            etf_code TEXT PRIMARY KEY,
            current_positions INTEGER NOT NULL DEFAULT 0,
            avg_cost REAL DEFAULT 0,
            total_shares INTEGER DEFAULT 0,
            cash_used REAL DEFAULT 0,
            updated_at TEXT NOT NULL,
            position_date TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            etf_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            action TEXT NOT NULL,
            price REAL NOT NULL,
            shares INTEGER NOT NULL,
            positions_before INTEGER,
            positions_after INTEGER,
            strategy TEXT,
            reason TEXT,
            created_at TEXT NOT NULL
        );
    """)
    # Migration: add position_date column if missing
    try:
        conn.execute("ALTER TABLE positions ADD COLUMN position_date TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()


# Run on import
init_tables()


# ---- Position CRUD ----

def get_position(etf_code: str) -> Optional[Dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM positions WHERE etf_code = ?", (etf_code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_positions() -> List[Dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM positions ORDER BY etf_code").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_position(etf_code: str, current_positions: int, avg_cost: float = 0,
                    total_shares: int = 0, cash_used: float = 0,
                    position_date: str = ''):
    conn = _get_conn()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO positions (etf_code, current_positions, avg_cost, total_shares, cash_used, updated_at, position_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(etf_code) DO UPDATE SET
            current_positions=excluded.current_positions,
            avg_cost=excluded.avg_cost,
            total_shares=excluded.total_shares,
            cash_used=excluded.cash_used,
            updated_at=excluded.updated_at,
            position_date=excluded.position_date
    """, (etf_code, current_positions, avg_cost, total_shares, cash_used, now, position_date))
    conn.commit()
    conn.close()


# ---- Trade Log ----

def auto_sync_signal(etf_code: str, target_position: int, strategy: str = None,
                     price: float = 0, data_date: str = '') -> dict:
    """Compare signal target_position with DB position.
    Only record real trades AFTER market close (after 15:00), and only once per day.
    During trading hours (9:30-15:00), signals are only suggestions, not recorded as trades.
    Same data_date = recalculation, skip (strategy changed after close).
    """
    pos = get_position(etf_code)
    current = pos['current_positions'] if pos else 0
    locked_date = pos.get('position_date', '') if pos else ''
    today = data_date or datetime.now().strftime('%Y%m%d')

    if target_position == current:
        return {'action': 'HOLD', 'delta': 0}

    now = datetime.now()

    # 周末不交易
    if now.weekday() >= 5:
        return {'action': 'SKIPPED', 'delta': abs(target_position - current),
                'from': current, 'to': target_position,
                'reason': '周末，跳过自动同步'}

    # 盘中时段（9:30-15:00）：只显示信号，不记录交易
    is_trading_hours = (9 <= now.hour < 15) or (now.hour == 15 and now.minute == 0)
    if is_trading_hours:
        return {'action': 'SKIPPED', 'delta': abs(target_position - current),
                'from': current, 'to': target_position,
                'reason': '盘中时段，仅显示信号建议，不记录交易（收盘后才记录）'}

    # Same data date = 今天已经记录过交易了（盘后更新策略时不重复记录）
    if locked_date == today:
        return {'action': 'LOCKED', 'delta': abs(target_position - current),
                'from': current, 'to': target_position}

    # 收盘后（15:00之后）且今天还没记录过：记录交易

    action = 'BUY' if target_position > current else 'SELL'
    delta = abs(target_position - current)
    trade_date = datetime.now().strftime('%Y%m%d')
    reason = 'SIGNAL_UP' if action == 'BUY' else 'SIGNAL_DOWN'

    # Record trade (shares = delta positions, no actual stock shares)
    add_trade(
        etf_code=etf_code,
        trade_date=trade_date,
        action=action,
        price=price,
        shares=delta,  # position units, not stock shares
        positions_before=current,
        positions_after=target_position,
        strategy=strategy,
        reason=reason,
    )

    # Update position, preserve cost basis
    existing = get_position(etf_code)
    if existing:
        upsert_position(
            etf_code, current_positions=target_position,
            avg_cost=existing['avg_cost'],
            total_shares=existing['total_shares'],
            cash_used=existing['cash_used'],
            position_date=today,
        )
    else:
        upsert_position(etf_code, current_positions=target_position, position_date=today)

    return {'action': action, 'delta': delta, 'from': current, 'to': target_position}


def run_auto_sync_all(start_date: str = '20250101'):
    """Calculate signals for all watchlist ETFs and auto-sync positions.
    Called by scheduler after daily data update. Not triggered by page visits.
    """
    import json
    from pathlib import Path
    from core.watchlist import calculate_realtime_signal

    watchlist_file = Path('data/watchlist_etfs.json')
    if not watchlist_file.exists():
        return {'success': False, 'message': 'watchlist not found'}

    with open(watchlist_file) as f:
        wl = json.load(f)

    results = []
    for etf in wl.get('etfs', []):
        code = etf['code']
        strategy = etf.get('strategy', 'macd_aggressive')
        try:
            signal = calculate_realtime_signal(code, start_date, strategy)
            if signal['success']:
                data = signal['data']
                target = data.get('positions_used', 0)
                price = data.get('latest_data', {}).get('close', 0)
                data_date = signal['data'].get('latest_date', '')
                r = auto_sync_signal(code, target, strategy=strategy,
                                     price=price, data_date=data_date)
                results.append({'code': code, **r})
        except Exception as e:
            results.append({'code': code, 'action': 'ERROR', 'error': str(e)})

    trades = [r for r in results if r.get('action') in ('BUY', 'SELL')]
    locked = [r for r in results if r.get('action') == 'LOCKED']
    skipped = [r for r in results if r.get('action') == 'SKIPPED']
    return {
        'success': True,
        'total': len(results),
        'trades': len(trades),
        'locked': len(locked),
        'skipped': len(skipped),
        'details': results,
    }


def add_trade(etf_code: str, trade_date: str, action: str, price: float,
              shares: int, positions_before: int, positions_after: int,
              strategy: str = None, reason: str = None) -> int:
    conn = _get_conn()
    now = datetime.now().isoformat()
    cursor = conn.execute("""
        INSERT INTO trade_log (etf_code, trade_date, action, price, shares,
                              positions_before, positions_after, strategy, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (etf_code, trade_date, action, price, shares,
          positions_before, positions_after, strategy, reason, now))
    conn.commit()
    trade_id = cursor.lastrowid
    conn.close()
    return trade_id


def get_trades(etf_code: str = None, start_date: str = None, end_date: str = None,
               limit: int = 200) -> List[Dict]:
    conn = _get_conn()
    query = "SELECT * FROM trade_log WHERE 1=1"
    params = []
    if etf_code:
        query += " AND etf_code = ?"
        params.append(etf_code)
    if start_date:
        query += " AND trade_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND trade_date <= ?"
        params.append(end_date)
    query += " ORDER BY trade_date DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---- PnL Calculation ----

def calculate_pnl(etf_code: str) -> Dict:
    """Calculate realized P&L from trade_log for an ETF."""
    trades = get_trades(etf_code, limit=1000)
    if not trades:
        return {'etf_code': etf_code, 'total_pnl': 0, 'total_trades': 0,
                'win_trades': 0, 'lose_trades': 0, 'win_rate': 0}

    trades.reverse()  # chronological order

    realized_pnl = 0
    win_count = 0
    lose_count = 0
    buy_queue = []  # FIFO: (price, shares)

    for t in trades:
        if t['action'] == 'BUY':
            buy_queue.append((t['price'], t['shares']))
        elif t['action'] == 'SELL':
            sell_shares = t['shares']
            sell_price = t['price']
            while sell_shares > 0 and buy_queue:
                buy_price, buy_shares = buy_queue[0]
                matched = min(sell_shares, buy_shares)
                pnl = (sell_price - buy_price) * matched
                realized_pnl += pnl
                if pnl > 0:
                    win_count += 1
                elif pnl < 0:
                    lose_count += 1
                sell_shares -= matched
                if matched >= buy_shares:
                    buy_queue.pop(0)
                else:
                    buy_queue[0] = (buy_price, buy_shares - matched)

    total = win_count + lose_count
    return {
        'etf_code': etf_code,
        'realized_pnl': round(realized_pnl, 2),
        'total_trades': len(trades),
        'win_trades': win_count,
        'lose_trades': lose_count,
        'win_rate': round(win_count / total * 100, 1) if total > 0 else 0,
    }


# ---- Signal → Suggestion ----

def get_position_suggestion(etf_code: str, target_position: int,
                             latest_price: float = None) -> Dict:
    """
    Compare target_position from signal against current DB position.
    Returns action suggestion.
    """
    pos = get_position(etf_code)
    current = pos['current_positions'] if pos else 0

    if target_position > current:
        action = 'BUY'
        delta = target_position - current
    elif target_position < current:
        action = 'SELL'
        delta = current - target_position
    else:
        action = 'HOLD'
        delta = 0

    return {
        'etf_code': etf_code,
        'action': action,
        'current_positions': current,
        'target_positions': target_position,
        'delta': delta,
        'current_avg_cost': pos['avg_cost'] if pos else 0,
        'current_shares': pos['total_shares'] if pos else 0,
        'price': latest_price,
    }


# ---- Execute Trade ----

def execute_position_change(etf_code: str, action: str, price: float,
                            positions_before: int, positions_after: int,
                            total_capital: float = 2000,
                            strategy: str = None) -> Dict:
    """
    Execute a position change: calculate shares, record trade, update position.

    Args:
        etf_code: ETF code
        action: BUY or SELL
        price: execution price
        positions_before: position level before change (0-10)
        positions_after: position level after change (0-10)
        total_capital: total capital for position sizing
        strategy: strategy name used for this trade

    Returns:
        Dict with trade details
    """
    position_size = total_capital / 10  # each position = 200
    delta = abs(positions_after - positions_before)
    trade_amount = delta * position_size
    shares = int(trade_amount // price) if price > 0 else 0

    if shares == 0:
        return {'success': False, 'message': '交易份额为0，无需操作'}

    pos = get_position(etf_code)
    old_avg_cost = pos['avg_cost'] if pos else 0
    old_shares = pos['total_shares'] if pos else 0
    old_cash_used = pos['cash_used'] if pos else 0

    trade_date = datetime.now().strftime('%Y%m%d')

    if action == 'BUY':
        cost = shares * price
        new_shares = old_shares + shares
        new_cash_used = old_cash_used + cost
        new_avg_cost = new_cash_used / new_shares if new_shares > 0 else 0
    else:  # SELL
        sell_ratio = delta / positions_before if positions_before > 0 else 0
        shares_to_sell = int(old_shares * sell_ratio) if old_shares > 0 else shares
        if shares_to_sell == 0:
            shares_to_sell = shares
        # Cap at actual shares only if we have real holdings
        actual_shares = min(shares_to_sell, old_shares) if old_shares > 0 else shares_to_sell
        proceeds = actual_shares * price
        new_shares = max(0, old_shares - actual_shares)
        new_cash_used = max(0, old_cash_used - (actual_shares * old_avg_cost)) if old_avg_cost > 0 else 0
        new_avg_cost = old_avg_cost if new_shares > 0 else 0
        shares = actual_shares

    upsert_position(etf_code, positions_after, new_avg_cost, new_shares, new_cash_used)

    trade_id = add_trade(
        etf_code=etf_code,
        trade_date=trade_date,
        action=action,
        price=price,
        shares=shares,
        positions_before=positions_before,
        positions_after=positions_after,
        strategy=strategy,
        reason='TARGET_UP' if action == 'BUY' else 'TARGET_DOWN',
    )

    return {
        'success': True,
        'trade_id': trade_id,
        'action': action,
        'shares': shares,
        'price': price,
        'amount': shares * price,
        'positions_before': positions_before,
        'positions_after': positions_after,
        'new_avg_cost': round(new_avg_cost, 4),
        'new_shares': new_shares,
    }
