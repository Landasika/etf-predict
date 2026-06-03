"""Shared P&L calculations.

One position slot is treated as a fixed amount of cash. Daily P&L always uses
the position held before that day's price move.
"""

SLOT_VALUE = 200


def normalize_trade_date(value) -> str:
    return str(value or '').replace('-', '')[:8]


def calculate_daily_profit(positions: int, daily_change_pct: float, slot_value: int = SLOT_VALUE) -> float:
    return int(positions or 0) * slot_value * (float(daily_change_pct or 0) / 100)


def calculate_slot_profit_series(
    daily_rows,
    snapshot_positions,
    fallback_positions: int = 0,
    start_date: str = '',
    slot_value: int = SLOT_VALUE,
) -> list:
    start = normalize_trade_date(start_date)
    normalized_snapshots = {
        normalize_trade_date(date): int(positions or 0)
        for date, positions in (snapshot_positions or {}).items()
        if normalize_trade_date(date)
    }

    def row_date(row):
        return normalize_trade_date(row.get('trade_date') or row.get('date'))

    rows = sorted(
        [
            row for row in (daily_rows or [])
            if row_date(row) and (not start or row_date(row) >= start)
        ],
        key=row_date,
    )

    series = []
    previous_close = None
    latest_prior_positions = None

    for row in rows:
        current_date = row_date(row)
        close = float(row.get('close') or 0)
        positions_for_profit = latest_prior_positions
        if positions_for_profit is None:
            positions_for_profit = int(fallback_positions or 0)

        daily_profit = 0.0
        if previous_close and previous_close > 0:
            daily_change_pct = ((close - previous_close) / previous_close) * 100
            daily_profit = calculate_daily_profit(positions_for_profit, daily_change_pct, slot_value)

        if current_date in normalized_snapshots:
            latest_prior_positions = normalized_snapshots[current_date]

        display_positions = latest_prior_positions
        if display_positions is None:
            display_positions = positions_for_profit

        series.append({
            'date': current_date,
            'close': close,
            'daily_profit': daily_profit,
            'positions': int(display_positions or 0),
        })
        previous_close = close

    return series


def calculate_monthly_profit_from_rows(
    daily_rows,
    snapshot_positions,
    fallback_positions: int = 0,
    data_date: str = '',
    slot_value: int = SLOT_VALUE,
) -> float:
    cutoff = normalize_trade_date(data_date)
    if not cutoff:
        return 0.0

    month_prefix = cutoff[:6]
    series = calculate_slot_profit_series(
        daily_rows=daily_rows,
        snapshot_positions=snapshot_positions,
        fallback_positions=fallback_positions,
        start_date=month_prefix + '01',
        slot_value=slot_value,
    )
    return sum(
        item['daily_profit']
        for item in series
        if item['date'].startswith(month_prefix) and item['date'] <= cutoff
    )
