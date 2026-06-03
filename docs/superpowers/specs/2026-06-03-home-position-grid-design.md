# Home Position Grid Design

## Goal

Replace the homepage standalone "今日收益" panel with a lightweight ETF position-card wall that makes strategy holdings and rebalance suggestions visible at a glance.

The implementation stays scoped to the existing homepage `/`. It preserves the current FastAPI/Jinja/static-JS frontend architecture and keeps the existing strategy summary table below the new card wall.

## Chosen Approach

Use the lightweight homepage enhancement approach:

- Modify the existing homepage template, JavaScript, and CSS.
- Reuse `/api/watchlist/batch-signals` data.
- Do not introduce React/Vite.
- Do not copy code from the neighboring `money` project; only reuse the visual idea of slot cards.
- Do not change `/positions`, position database semantics, automatic sync, or strategy calculation logic.

## Page Structure

The homepage layout remains mostly intact:

1. Header, top stats, navigation.
2. Existing action bar.
3. New position grid panel.
4. Existing strategy summary table.
5. Existing modals and other lower-page controls.

The current `dailyProfitPanel` no longer appears as the main panel. The new position grid takes that visual slot. Daily profit can remain available in the detailed table data, but it is no longer a standalone homepage section.

## Position Grid Panel

The panel has two parts:

1. Summary strip:
   - Yesterday strategy total slots.
   - Today strategy target total slots.
   - Suggested add slots.
   - Suggested reduce slots.

2. ETF card wall:
   - Shows every watchlist ETF.
   - Cards with strategy slot changes are visually stronger.
   - Cards with no change are muted but still present.

The panel copy should make the data source explicit:

> 昨日策略仓位 -> 今日策略仓位，默认按策略建议执行

## Card Data Semantics

Each card uses strategy-derived slot movement, not database actual holding movement.

- Previous slots: `item.latest_data.previous_positions_used`.
- Current target slots: `item.positions_used`.
- Total slots: `item.total_positions`, defaulting to `10` when missing.
- Delta: `current target slots - previous slots`.

Do not use `item.today_action_count` for the card delta because the existing API path may compute it from database positions. The table can continue using its existing fields.

## Card Content

Each ETF card displays:

- ETF name.
- ETF code.
- Main slot transition, such as `2 -> 5`.
- Delta badge, such as `+3 格`, `-2 格`, or `不变`.
- Slot bar:
  - Green: retained slots.
  - Red: newly added slots.
  - Orange: reduced slots.
  - Light gray: empty slots.
- Signal type.
- Signal strength.
- Daily percentage change.
- MACD/KDJ concise status when available.
- One short reason line.

Reason line priority:

1. `item.action_reason`.
2. `item.latest_data.signal_reason`.
3. `item.next_action`.
4. Fallback text based on delta: `策略建议加仓`, `策略建议减仓`, or `保持现有策略仓位`.

## Sorting

The card wall displays all watchlist ETFs sorted as follows:

1. Add-position cards first, highest positive delta first.
2. Reduce-position cards next, most negative delta first by absolute size.
3. Hold cards last, current target slots high to low.
4. Stable tie-breaker by ETF code.

This ordering emphasizes the largest strategy changes while keeping unchanged holdings visible.

## Visual Rules

Use a dense, utilitarian dashboard style consistent with the existing app:

- Card border radius: `8px` or less.
- Summary cards and ETF cards use white or near-white surfaces.
- Add cards use a red left border and red delta badge.
- Reduce cards use an orange left border and orange delta badge.
- Hold cards are muted with lower contrast.
- Slot bars use fixed-height grid segments so the layout does not shift.
- The card wall uses responsive CSS grid:
  - Desktop: auto-fill cards with a practical minimum width.
  - Mobile: one or two columns depending on available width.

The color meaning is specific to slots:

- Red means newly added strategy slots.
- Orange means strategy slots to remove.
- Green means retained strategy slots.

## Data Flow

`loadBatchSignals()` remains the homepage data entry point.

On success:

1. Store `strategyData`.
2. Render the new position grid.
3. Render the existing strategy table.
4. Update existing header stats.
5. Update last-updated timestamp.

`updateDailyProfit(data)` is removed from the homepage success path or made inert for the standalone panel.

Expected frontend helper functions:

- `renderPositionGrid(data)`
- `sortPositionGridItems(data)`
- `getStrategySlotMovement(item)`
- `renderSlotSegments(previousSlots, targetSlots, totalSlots)`
- `getPositionGridReason(item, delta)`

## Error And Empty States

If the watchlist data is empty:

- Show an empty state inside the position grid panel.
- Keep the strategy table's existing empty state behavior.

If a single ETF is missing position fields:

- Treat missing previous slots as `0`.
- Treat missing target slots as `0`.
- Treat missing total slots as `10`.
- Render a neutral card instead of blocking the full grid.

If `/api/watchlist/batch-signals` fails:

- Keep existing homepage error behavior.
- Do not introduce a second independent fetch path.

## Testing

Add focused frontend tests matching the existing style in `tests/`.

Required coverage:

- Homepage JavaScript contains the new position grid renderer.
- The card delta is computed from `latest_data.previous_positions_used` and `positions_used`, not from `today_action_count`.
- The old standalone daily profit panel is no longer rendered as the main homepage panel.
- Sorting logic prioritizes add, reduce, and hold cards as specified.
- Slot rendering distinguishes retained, added, reduced, and empty slots.

Run the relevant pytest tests after implementation. If practical, also run the full test suite.

## Out Of Scope

- Rebuilding the frontend in React/Vite.
- Changing `/positions`.
- Adding accept/reject/custom action controls.
- Changing trading execution behavior.
- Changing database position semantics.
- Changing strategy calculation behavior.
- Removing the existing strategy summary table.
