# Position Signal and Scheduler Decoupling Design

## Scope

This refactor targets two coupled areas that currently create inconsistent behavior:

1. Homepage position grid, strategy table, profit values, and Feishu operation reports should use the same ETF signal row data.
2. Settings for data update scheduling, Feishu notification scheduling, and MACD optimization scheduling should be read and written through one scheduler settings service.

This design does not change strategy rules, position formulas, UI layout, Docker deployment, or remote deployment behavior.

## Current Problems

`api/main.py` builds homepage ETF rows inside `/api/watchlist/batch-signals`. `core/feishu_report.py` independently repeats signal calculation, daily change calculation, operation reason generation, and daily profit calculation. This makes homepage and Feishu easy to drift apart.

Profit calculation has a shared backend module, but display and fallback logic still contain hardcoded assumptions such as one slot being 200 yuan. The backend should remain the source of truth for slot value and calculated profit fields.

Scheduler settings are spread across API route handlers, `core.data_update_scheduler`, `config.py`, settings page JavaScript, and stale homepage scheduler modal code. The route handlers repeat the same configure pattern for data updates, Feishu notifications, and MACD optimization.

## Approach

Use a medium-size service-layer refactor:

1. Add `core.position_signal_service`.
2. Add `core.scheduler_settings_service`.
3. Update API routes and Feishu report generation to call these services.
4. Remove or disable stale homepage scheduler configuration behavior so `/settings` is the only configuration surface.

This is preferred over a large rewrite because it directly addresses the inconsistent outputs without requiring a full `api/main.py` or frontend decomposition in one pass.

## Position Signal Service

Create `core/position_signal_service.py` with a public function that builds the ETF rows used by both homepage and Feishu:

```python
def build_position_signal_rows(
    refresh: bool = False,
    realtime: bool = False,
    include_cached: bool = True,
) -> dict:
    ...
```

The service owns:

- watchlist loading
- latest data date lookup
- cache read/write for batch signal rows
- 15:05 position-grid recompute whitelist
- realtime signal calculation per ETF
- daily change calculation
- previous actual position lookup
- daily profit and monthly profit calculation
- today operation and action reason generation
- row sorting-neutral output for callers

The returned payload should preserve the existing `/api/watchlist/batch-signals` response shape:

- `success`
- `data`
- `count`
- `cached`
- `data_date`

Each row should preserve existing frontend fields, including `code`, `name`, `remark`, `strategy`, `strategy_name`, `signal`, `signal_name`, `signal_strength`, `positions_used`, `total_positions`, `today_operation`, `today_action_count`, `action_reason`, `daily_change_pct`, `daily_profit`, `monthly_profit`, `macd`, `macd_params`, `kdj`, `price`, `latest_data`, and `data_date`.

The service should expose a smaller helper for Feishu if needed:

```python
def build_feishu_operation_rows() -> dict:
    ...
```

That helper should call the same row builder rather than recalculate signals.

## Profit Rules

`core.profit_calculator` remains the source of truth.

Rules:

- One slot value is `SLOT_VALUE = 200`.
- Daily profit is `previous_actual_positions * SLOT_VALUE * daily_change_pct / 100`.
- Monthly profit is calculated from historical daily rows and position snapshots.
- API responses should include calculated values; frontend code should not recreate formulas.
- Feishu report stats should use the same row `daily_profit` values and `SLOT_VALUE`.

## Scheduler Settings Service

Create `core/scheduler_settings_service.py` with focused functions:

```python
def get_scheduler_settings_status() -> dict:
    ...

def configure_data_update_schedule(enabled: bool, update_time: str) -> dict:
    ...

def configure_feishu_notification_schedule(enabled: bool, times: list[str]) -> dict:
    ...

def configure_macd_optimization_schedule(
    enabled: bool,
    opt_time: str,
    notify_feishu: bool,
) -> dict:
    ...
```

The service owns:

- scheduler instance lookup
- time validation through scheduler methods
- config persistence through `config.update_config`
- consistent return payloads for API routes

The API layer should only parse request JSON, call the service, and convert service errors into HTTP errors.

## Frontend Behavior

The settings page remains the only place where users configure:

- daily data update schedule
- Feishu notification schedule
- MACD optimization schedule
- whether MACD optimization completion sends Feishu notification

Homepage may show scheduler status, but it should not contain scheduler configuration controls or save scheduler settings. Stale homepage modal code should be removed once the settings service is wired.

## Error Handling

Service functions should return structured success data or raise explicit `ValueError` for validation failures.

API routes should map:

- validation failures to HTTP 400
- persistence or scheduler failures to HTTP 500

Feishu report generation should degrade by omitting failed ETF rows only when the shared row builder reports row-level failures. It should not silently use a separate fallback formula that can diverge from homepage output.

## Testing

Add or update tests for:

- homepage batch signal API and Feishu report use the same signal rows
- daily profit and total daily profit match shared `core.profit_calculator`
- cached position grid is not recomputed after 15:05
- scheduler settings service persists data update schedule
- scheduler settings service persists Feishu notification schedule
- scheduler settings service persists MACD optimization schedule and `notify_feishu`
- homepage no longer posts MACD optimization schedule from the old scheduler modal path

Existing tests for homepage daily profit, monthly profit, Feishu notifier, position grid freeze, and settings MACD optimization should continue to pass.

## Non-Goals

This refactor will not:

- change MACD histogram strategy rules
- change optimized parameter behavior
- change position slot count rules
- change visual card layout
- split all frontend files
- split all of `api/main.py`
- deploy local or remote Docker

## Acceptance Criteria

- `/api/watchlist/batch-signals` and Feishu operation reports are generated from the same row-building service.
- Daily profit and monthly profit fields use shared backend calculation helpers.
- Settings scheduler routes delegate to `core.scheduler_settings_service`.
- Homepage no longer contains active scheduler configuration save behavior.
- Relevant unit tests pass.
