# Position Signal Scheduler Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make homepage position-grid/table data, Feishu operation reports, profit fields, and scheduler settings use shared backend services instead of duplicated logic.

**Architecture:** Add two focused service modules: `core.position_signal_service` owns ETF row generation for homepage and Feishu, and `core.scheduler_settings_service` owns scheduler configuration reads/writes. Keep API routes thin, keep `core.profit_calculator` as the single profit formula source, and remove active homepage scheduler configuration behavior so `/settings` is the only configuration surface.

**Tech Stack:** Python 3, FastAPI route handlers, pytest, existing SQLite/database helpers, existing vanilla JavaScript frontend.

---

## File Structure

- Create `core/position_signal_service.py`
  - Builds `/api/watchlist/batch-signals` payloads.
  - Owns cache/freeze rules for the homepage position grid.
  - Owns per-ETF row construction used by homepage and Feishu.
  - Uses `core.profit_calculator` for daily and monthly profit fields.

- Create `core/scheduler_settings_service.py`
  - Owns scheduler status reads and config writes.
  - Wraps `core.data_update_scheduler.get_scheduler()` and `config.update_config()`.
  - Raises `ValueError` for invalid time input.
  - Raises `RuntimeError` for failed persistence.

- Modify `api/main.py`
  - Replace batch-signals row-building code with `build_position_signal_rows()`.
  - Replace scheduler configure route bodies with `core.scheduler_settings_service`.
  - Keep route response shapes unchanged.
  - Remove controller-level helper duplication that moved into services.

- Modify `core/feishu_report.py`
  - Load operation rows from `core.position_signal_service`.
  - Stop recalculating realtime signals, daily change, action reason, and daily profit independently.
  - Use `SLOT_VALUE` from `core.profit_calculator` for stats display.

- Modify `templates/index.html`
  - Remove or disable the homepage scheduler settings modal and scheduler settings button.
  - Keep scheduler status display only if it is still passive.

- Modify `static/js/home.js`
  - Remove active scheduler save/load modal behavior.
  - Keep passive `loadSchedulerStatus()` only if the template still renders the status banner.

- Test files:
  - Create `tests/test_position_signal_service.py`.
  - Create `tests/test_scheduler_settings_service.py`.
  - Update `tests/test_position_grid_freeze.py`.
  - Update `tests/test_feishu_notifier.py` or add a focused Feishu report test if the existing file is too broad.
  - Update `tests/test_settings_macd_optimization.py`.
  - Update `tests/test_home_daily_profit_frontend.py`.

---

### Task 1: Extract Position Signal Service With Tests

**Files:**
- Create: `core/position_signal_service.py`
- Create: `tests/test_position_signal_service.py`
- Modify: `api/main.py`

- [ ] **Step 1: Write failing tests for service-level row generation**

Create `tests/test_position_signal_service.py`:

```python
import pytest


def test_build_position_signal_rows_uses_shared_profit_and_expected_shape(monkeypatch):
    from core import position_signal_service as service

    monkeypatch.setattr(service, "get_latest_data_date", lambda: "20260604")
    monkeypatch.setattr(service, "get_batch_cache", lambda cache_type, data_date: None)
    captured_cache = {}
    monkeypatch.setattr(
        service,
        "set_batch_cache",
        lambda cache_type, data_date, payload: captured_cache.update({
            "cache_type": cache_type,
            "data_date": data_date,
            "payload": payload,
        }),
    )
    monkeypatch.setattr(service, "load_watchlist", lambda: {
        "etfs": [{
            "code": "510300.SH",
            "strategy": "macd_histogram_momentum",
            "strategy_name": "量能柱",
            "total_positions": 10,
            "remark": "沪深300",
            "optimized_histogram_params": {"fast": 12, "slow": 26, "signal": 9},
        }]
    })
    monkeypatch.setattr(service, "get_etf_info", lambda code: {"extname": "沪深300ETF"})
    monkeypatch.setattr(service, "get_etf_daily_data", lambda code: [
        {"trade_date": "20260603", "close": 100},
        {"trade_date": "20260604", "close": 102},
    ])
    monkeypatch.setattr(service, "get_position", lambda code: {"current_positions": 3})
    monkeypatch.setattr(service, "calculate_monthly_profit", lambda code, date, fallback: 18.5)
    monkeypatch.setattr(service, "calculate_realtime_signal", lambda code, start_date, strategy: {
        "success": True,
        "data": {
            "latest_date": "20260604",
            "positions_used": 5,
            "profit": 11,
            "profit_pct": 1.1,
            "next_action": "买入2仓",
            "backtest_summary": {"buy_hold_return_pct": 0.8},
            "latest_data": {
                "close": 102,
                "signal_type": "BUY",
                "signal_strength": 5,
                "macd_dif": 0.1,
                "macd_dea": 0.05,
                "macd_hist": 0.05,
                "kdj_k": 45,
                "kdj_d": 40,
                "kdj_j": 55,
            },
        },
    })

    result = service.build_position_signal_rows(refresh=False, realtime=False)

    assert result["success"] is True
    assert result["cached"] is False
    assert result["data_date"] == "20260604"
    assert result["count"] == 1
    row = result["data"][0]
    assert row["code"] == "510300.SH"
    assert row["name"] == "沪深300ETF"
    assert row["remark"] == "沪深300"
    assert row["positions_used"] == 5
    assert row["db_position"] == 3
    assert row["today_action_count"] == 2
    assert row["today_operation"] == "买入2仓"
    assert row["daily_change_pct"] == pytest.approx(2.0)
    assert row["daily_profit"] == pytest.approx(12.0)
    assert row["monthly_profit"] == pytest.approx(18.5)
    assert captured_cache["cache_type"] == "signals"
    assert captured_cache["payload"]["count"] == 1
```

- [ ] **Step 2: Write failing test for after-close cache freeze**

Append to `tests/test_position_signal_service.py`:

```python
def test_build_position_signal_rows_uses_cache_after_lock_even_with_refresh(monkeypatch):
    from core import position_signal_service as service

    monkeypatch.setattr(service, "_is_after_position_grid_lock_time", lambda now=None: True)
    monkeypatch.setattr(service, "get_latest_data_date", lambda: "20260604")
    monkeypatch.setattr(service, "get_all_positions", lambda: [{
        "etf_code": "510300.SH",
        "current_positions": 4,
        "total_shares": 800,
        "avg_cost": 1.2,
    }])
    monkeypatch.setattr(service, "calculate_monthly_profit", lambda code, date, fallback: 20)
    monkeypatch.setattr(service, "get_batch_cache", lambda cache_type, data_date: {
        "data": [{"code": "510300.SH", "data_date": "20260604"}],
        "count": 1,
    })

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("signals should not be recomputed after lock")

    monkeypatch.setattr(service, "calculate_realtime_signal", fail_if_recomputed)

    result = service.build_position_signal_rows(refresh=True, realtime=False)

    assert result["success"] is True
    assert result["cached"] is True
    assert result["data"][0]["db_position"] == 4
    assert result["data"][0]["monthly_profit"] == 20
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
pytest tests/test_position_signal_service.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'core.position_signal_service'`.

- [ ] **Step 4: Implement `core.position_signal_service`**

Create `core/position_signal_service.py`:

```python
from datetime import datetime, time
from typing import Optional

import config
from core.database import (
    get_batch_cache,
    get_etf_daily_data,
    get_etf_info,
    get_latest_data_date,
    set_batch_cache,
    clear_batch_cache,
)
from core.position_manager import get_all_positions, get_position
from core.profit_calculator import calculate_daily_profit
from core.watchlist import load_watchlist, calculate_realtime_signal


POSITION_GRID_LOCK_TIME = time(15, 5)


def _is_after_position_grid_lock_time(now=None) -> bool:
    now = now or datetime.now()
    return now.time() >= POSITION_GRID_LOCK_TIME


def _can_recompute_position_grid(
    refresh: bool = False,
    realtime: bool = False,
    cached: Optional[dict] = None,
    now=None,
) -> bool:
    if cached and _is_after_position_grid_lock_time(now):
        return False
    if realtime:
        return True
    if refresh:
        return True
    return cached is None


def get_signal_name(signal_type: str) -> str:
    signal_map = {
        "BUY": "买入",
        "SELL": "卖出",
        "HOLD": "持有",
        "WAIT": "等待",
    }
    return signal_map.get(signal_type, "持有")


def get_kdj_status(k: float, j: float) -> str:
    if k > 80 or j > 100:
        return "超买"
    if k < 20 or j < 0:
        return "超卖"
    return "正常"


def _get_macd_params_display(etf: dict) -> str:
    params = (
        etf.get("optimized_histogram_params")
        or etf.get("optimized_macd_params")
        or etf.get("optimized_params")
        or {}
    )
    if not params:
        return "--"
    fast = params.get("fast") or params.get("macd_fast")
    slow = params.get("slow") or params.get("macd_slow")
    signal = params.get("signal") or params.get("macd_signal")
    if fast and slow and signal:
        return f"{fast}/{slow}/{signal}"
    return ", ".join(f"{key}={value}" for key, value in sorted(params.items())[:3])


def _calculate_daily_change_pct(etf_code: str) -> float:
    try:
        recent_data = get_etf_daily_data(etf_code)
        if recent_data and len(recent_data) >= 2:
            today_close = float(recent_data[-1].get("close", 0))
            yesterday_close = float(recent_data[-2].get("close", 0))
            if yesterday_close > 0:
                return ((today_close - yesterday_close) / yesterday_close) * 100
    except Exception:
        return 0.0
    return 0.0


def _build_action_reason(today_action: int, latest_data: dict, current_positions: int) -> str:
    if today_action > 0:
        if latest_data.get("signal_type") == "BUY":
            strength = latest_data.get("signal_strength", 0)
            if strength >= 10:
                return "回踩MA60未破+MACD金叉，最强买入信号"
            if strength >= 9:
                return "正鸭嘴形态，强烈看多"
            if strength >= 8:
                return "零轴上方金叉，上升趋势明确"
            return "MACD金叉买入"
        return "加仓买入"
    if today_action < 0:
        macd_dif = latest_data.get("macd_dif", 0)
        macd_dea = latest_data.get("macd_dea", 0)
        kdj_k = latest_data.get("kdj_k", 0)
        kdj_status = "严重超买" if kdj_k > 80 else ("超买" if kdj_k > 70 else "正常")
        if kdj_status == "严重超买":
            return f"KDJ{kdj_status}，止盈减仓"
        if macd_dif < macd_dea:
            return "MACD死叉，减仓避险"
        if current_positions > 7:
            return "涨幅较大，分批止盈"
        return "信号转弱，减仓保住利润"
    return "保持现有仓位"


def _format_today_operation(today_action: int) -> str:
    if today_action > 0:
        return f"买入{today_action}仓"
    if today_action < 0:
        return f"卖出{abs(today_action)}仓"
    return "持有"


def calculate_monthly_profit(etf_code: str, data_date: str, fallback_positions: int = 0) -> float:
    from api.main import calculate_monthly_profit as api_calculate_monthly_profit

    return api_calculate_monthly_profit(etf_code, data_date, fallback_positions)


def _cached_batch_signals_response(cached: dict, data_date: str) -> dict:
    db_positions = {p["etf_code"]: p for p in get_all_positions()}
    for row in cached.get("data", []):
        db = db_positions.get(row.get("code", ""), {})
        row["db_position"] = db.get("current_positions", 0)
        row["db_shares"] = db.get("total_shares", 0)
        row["db_avg_cost"] = db.get("avg_cost", 0)
        if "monthly_profit" not in row:
            row["monthly_profit"] = calculate_monthly_profit(
                row.get("code", ""),
                row.get("data_date") or data_date,
                row["db_position"],
            )
    return {
        "success": True,
        "data": cached.get("data", []),
        "count": cached.get("count", 0),
        "cached": True,
        "data_date": data_date,
    }


def _build_row(etf: dict, data_date: str, start_date: str) -> Optional[dict]:
    etf_code = etf["code"]
    strategy = etf.get("strategy", "macd_aggressive")
    etf_info = get_etf_info(etf_code)
    if not etf_info:
        return None

    signal_result = calculate_realtime_signal(etf_code, start_date, strategy)
    if not signal_result.get("success"):
        return None

    signal_data = signal_result["data"]
    latest_data = signal_data.get("latest_data", {})
    backtest_summary = signal_data.get("backtest_summary", {})
    daily_change_pct = _calculate_daily_change_pct(etf_code)

    position = get_position(etf_code)
    previous_positions = position.get("current_positions", 0) if position else 0
    current_positions = signal_data.get("positions_used", 0)
    today_action = current_positions - previous_positions
    daily_profit = calculate_daily_profit(previous_positions, daily_change_pct)
    monthly_profit = calculate_monthly_profit(
        etf_code,
        signal_data.get("latest_date", data_date),
        previous_positions,
    )

    kdj_k = latest_data.get("kdj_k", 0)
    kdj_d = latest_data.get("kdj_d", 0)
    kdj_j = latest_data.get("kdj_j", 0)

    return {
        "code": etf_code,
        "name": etf_info.get("extname", etf_code),
        "strategy": strategy,
        "strategy_name": etf.get("strategy_name", strategy),
        "signal": latest_data.get("signal_type", "HOLD"),
        "signal_name": get_signal_name(latest_data.get("signal_type", "HOLD")),
        "signal_strength": latest_data.get("signal_strength", 0),
        "today_operation": _format_today_operation(today_action),
        "today_action_count": today_action,
        "action_reason": _build_action_reason(today_action, latest_data, current_positions),
        "profit_value": signal_data.get("profit", 0),
        "profit_pct": signal_data.get("profit_pct", 0),
        "benchmark_return": backtest_summary.get("buy_hold_return_pct", 0) or 0,
        "positions_used": current_positions,
        "db_position": previous_positions,
        "total_positions": etf.get("total_positions", 10),
        "next_action": signal_data.get("next_action", "--"),
        "macd": {
            "dif": latest_data.get("macd_dif", 0),
            "dea": latest_data.get("macd_dea", 0),
            "hist": latest_data.get("macd_hist", 0),
        },
        "macd_params": _get_macd_params_display(etf),
        "kdj": {
            "k": kdj_k,
            "d": kdj_d,
            "j": kdj_j,
            "status": get_kdj_status(kdj_k, kdj_j),
            "fusion_level": latest_data.get("fusion_level", 0),
            "position_cap": latest_data.get("kdj_position_cap", 10),
        },
        "price": latest_data.get("close", 0),
        "daily_change_pct": daily_change_pct,
        "daily_profit": daily_profit,
        "monthly_profit": monthly_profit,
        "latest_data": latest_data,
        "position_value": etf.get("position_value", 0),
        "data_date": signal_data.get("latest_date", data_date),
        "remark": etf.get("remark", ""),
    }


def build_position_signal_rows(refresh: bool = False, realtime: bool = False, include_cached: bool = True) -> dict:
    data_date = get_latest_data_date()
    if not data_date:
        return {"success": False, "message": "无法获取数据日期"}

    start_date = config.DEFAULT_START_DATE
    cache_data_date = f"{data_date}_{start_date}"
    cached = get_batch_cache("signals", cache_data_date) if include_cached else None

    if cached and not _can_recompute_position_grid(refresh=refresh, realtime=realtime, cached=cached):
        return _cached_batch_signals_response(cached, data_date)

    if realtime:
        clear_batch_cache()

    watchlist = load_watchlist()
    rows = []
    for etf in watchlist.get("etfs", []):
        row = _build_row(etf, data_date, start_date)
        if row:
            rows.append(row)

    if not realtime:
        set_batch_cache("signals", cache_data_date, {"data": rows, "count": len(rows)})

    return {
        "success": True,
        "data": rows,
        "count": len(rows),
        "cached": False,
        "data_date": data_date,
    }


def build_feishu_operation_rows() -> dict:
    return build_position_signal_rows(refresh=False, realtime=False)
```

- [ ] **Step 5: Update `/api/watchlist/batch-signals` to delegate to service**

In `api/main.py`, replace the body of `get_batch_signals()` with:

```python
@app.get("/api/watchlist/batch-signals")
async def get_batch_signals(refresh: bool = False, realtime: bool = False):
    from core.position_signal_service import build_position_signal_rows

    return build_position_signal_rows(refresh=refresh, realtime=realtime)
```

Keep old helper functions temporarily if other tests still import them. Remove them only after all imports are migrated.

- [ ] **Step 6: Run focused tests**

Run:

```bash
pytest tests/test_position_signal_service.py tests/test_position_grid_freeze.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add core/position_signal_service.py api/main.py tests/test_position_signal_service.py tests/test_position_grid_freeze.py
git commit -m "refactor: extract position signal service"
```

---

### Task 2: Make Feishu Report Use Shared Position Rows

**Files:**
- Modify: `core/feishu_report.py`
- Test: `tests/test_feishu_report_shared_rows.py`

- [ ] **Step 1: Write failing test for Feishu using shared rows**

Create `tests/test_feishu_report_shared_rows.py`:

```python
def test_feishu_report_loads_shared_position_signal_rows(monkeypatch):
    from core import feishu_report

    shared_payload = {
        "success": True,
        "data": [{
            "code": "510300.SH",
            "name": "沪深300ETF",
            "price": 1.02,
            "daily_change_pct": 2.0,
            "db_position": 3,
            "positions_used": 5,
            "daily_profit": 12.0,
            "today_action_count": 2,
            "today_operation": "买入2仓",
            "action_reason": "MACD金叉买入",
            "next_action": "买入2仓",
            "signal": "BUY",
            "signal_strength": 5,
            "total_positions": 10,
        }],
    }

    monkeypatch.setattr(feishu_report, "load_watchlist", lambda: {
        "etfs": [{"code": "510300.SH", "name": "沪深300ETF"}]
    })
    monkeypatch.setattr(
        feishu_report,
        "build_feishu_operation_rows",
        lambda: shared_payload,
    )

    report = feishu_report.ETFOperationReport()

    assert report.load_data() is True
    assert report.etf_data["510300.SH"]["daily_profit"] == 12.0
    assert report.etf_data["510300.SH"]["positions_used"] == 5
    assert report.etf_data["510300.SH"]["previous_positions_used"] == 3
    assert report.etf_data["510300.SH"]["today_operation"] == "买入2仓"
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
pytest tests/test_feishu_report_shared_rows.py -q
```

Expected: fail because `core.feishu_report` does not import or use `build_feishu_operation_rows`.

- [ ] **Step 3: Update imports in `core/feishu_report.py`**

Replace:

```python
from core.profit_calculator import calculate_daily_profit
```

With:

```python
from core.position_signal_service import build_feishu_operation_rows
from core.profit_calculator import SLOT_VALUE, calculate_daily_profit
```

- [ ] **Step 4: Replace `ETFOperationReport.load_data()` shared-row path**

At the start of `ETFOperationReport.load_data()`, after watchlist load succeeds, add:

```python
        try:
            payload = build_feishu_operation_rows()
            if payload.get("success") and payload.get("data"):
                for row in payload["data"]:
                    code = row["code"]
                    self.etf_data[code] = {
                        "name": row.get("name", code),
                        "close": row.get("price", 0),
                        "pct_chg": row.get("daily_change_pct", 0),
                        "previous_positions_used": row.get("db_position", 0),
                        "positions_used": row.get("positions_used", 0),
                        "daily_profit": row.get("daily_profit", 0),
                        "today_action_count": row.get("today_action_count", 0),
                        "today_operation": row.get("today_operation", "持有"),
                        "action_reason": row.get("action_reason", ""),
                        "next_action": row.get("next_action", "--"),
                        "signal_type": row.get("signal", "HOLD"),
                        "signal_strength": row.get("signal_strength", 0),
                        "total_positions": row.get("total_positions", 10),
                    }
                return True
        except Exception as e:
            print(f"⚠️  共享信号行加载失败: {e}")
```

Then remove the duplicated realtime-signal loop from `load_data()` once the test passes. Keep the existing database fallback only if needed for no-signal emergency output, but do not let it run when the shared payload succeeds.

- [ ] **Step 5: Update stats slot value**

In `_calculate_stats()`, replace:

```python
investment = previous_positions_used * 200
```

With:

```python
investment = previous_positions_used * SLOT_VALUE
```

- [ ] **Step 6: Run Feishu tests**

Run:

```bash
pytest tests/test_feishu_report_shared_rows.py tests/test_feishu_notifier.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add core/feishu_report.py tests/test_feishu_report_shared_rows.py
git commit -m "refactor: share position rows with feishu report"
```

---

### Task 3: Extract Scheduler Settings Service

**Files:**
- Create: `core/scheduler_settings_service.py`
- Create: `tests/test_scheduler_settings_service.py`
- Modify: `api/main.py`

- [ ] **Step 1: Write failing tests for scheduler settings service**

Create `tests/test_scheduler_settings_service.py`:

```python
import pytest


class FakeScheduler:
    def __init__(self):
        self.enabled = False
        self.update_time = "15:05"
        self.feishu_notification_times = ["09:40"]
        self.macd_notify = False

    def get_status(self):
        return {
            "enabled": self.enabled,
            "update_time": self.update_time,
            "feishu_notification": {
                "enabled": False,
                "times": self.feishu_notification_times,
            },
            "macd_optimization": {
                "enabled": False,
                "time": "23:00",
                "notify_feishu": self.macd_notify,
            },
        }

    def set_update_time(self, value):
        if value == "bad":
            return False
        self.update_time = value
        return True

    def set_enabled(self, value):
        self.enabled = value

    def set_feishu_notification_times(self, value):
        if value == ["bad"]:
            return False
        self.feishu_notification_times = value
        return True

    def set_feishu_notification_enabled(self, value):
        self.feishu_enabled = value

    def set_macd_optimization_time(self, value):
        if value == "bad":
            return False
        self.macd_time = value
        return True

    def set_macd_optimization_enabled(self, value):
        self.macd_enabled = value

    def set_macd_optimization_notify_feishu(self, value):
        self.macd_notify = value


def test_configure_data_update_schedule_persists(monkeypatch):
    from core import scheduler_settings_service as service

    fake = FakeScheduler()
    saved = {}
    monkeypatch.setattr(service, "get_scheduler", lambda: fake)
    monkeypatch.setattr(service.config, "update_config", lambda payload: saved.update(payload) or True)

    result = service.configure_data_update_schedule(True, "15:10")

    assert result["success"] is True
    assert saved["update_schedule"] == {"enabled": True, "time": "15:10"}
    assert result["data"]["enabled"] is True


def test_configure_data_update_schedule_rejects_bad_time(monkeypatch):
    from core import scheduler_settings_service as service

    monkeypatch.setattr(service, "get_scheduler", lambda: FakeScheduler())

    with pytest.raises(ValueError, match="无效的时间格式"):
        service.configure_data_update_schedule(True, "bad")


def test_configure_feishu_notification_schedule_persists(monkeypatch):
    from core import scheduler_settings_service as service

    fake = FakeScheduler()
    saved = {}
    monkeypatch.setattr(service, "get_scheduler", lambda: fake)
    monkeypatch.setattr(service.config, "update_config", lambda payload: saved.update(payload) or True)

    result = service.configure_feishu_notification_schedule(True, ["09:40", "14:40"])

    assert result["success"] is True
    assert saved["feishu_notification_schedule"] == {
        "enabled": True,
        "times": "09:40,14:40",
    }


def test_configure_macd_optimization_schedule_persists_notify_feishu(monkeypatch):
    from core import scheduler_settings_service as service

    fake = FakeScheduler()
    saved = {}
    monkeypatch.setattr(service, "get_scheduler", lambda: fake)
    monkeypatch.setattr(service.config, "update_config", lambda payload: saved.update(payload) or True)

    result = service.configure_macd_optimization_schedule(True, "23:00", True)

    assert result["success"] is True
    assert saved["macd_optimization_schedule"] == {
        "enabled": True,
        "time": "23:00",
        "lookback_days": 365,
        "notify_feishu": True,
    }
    assert result["data"]["macd_optimization"]["notify_feishu"] is True
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_scheduler_settings_service.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'core.scheduler_settings_service'`.

- [ ] **Step 3: Implement scheduler settings service**

Create `core/scheduler_settings_service.py`:

```python
import config
from core.data_update_scheduler import get_scheduler


def get_scheduler_settings_status() -> dict:
    scheduler = get_scheduler()
    return {"success": True, "data": scheduler.get_status()}


def configure_data_update_schedule(enabled: bool, update_time: str) -> dict:
    scheduler = get_scheduler()
    if not scheduler.set_update_time(update_time):
        raise ValueError("无效的时间格式，请使用 HH:MM 格式")
    scheduler.set_enabled(enabled)
    if not config.update_config({
        "update_schedule": {
            "enabled": enabled,
            "time": update_time,
        }
    }):
        raise RuntimeError("保存调度器配置失败")
    return {
        "success": True,
        "message": f"调度器已{'启用' if enabled else '禁用'}，更新时间: {update_time}",
        "data": scheduler.get_status(),
    }


def configure_feishu_notification_schedule(enabled: bool, times: list[str]) -> dict:
    scheduler = get_scheduler()
    if not scheduler.set_feishu_notification_times(times):
        raise ValueError("无效的时间格式，请使用 HH:MM 格式")
    scheduler.set_feishu_notification_enabled(enabled)
    if not config.update_config({
        "feishu_notification_schedule": {
            "enabled": enabled,
            "times": ",".join(scheduler.feishu_notification_times),
        }
    }):
        raise RuntimeError("保存飞书定时发送配置失败")
    return {
        "success": True,
        "message": "飞书消息定时发送配置已更新",
        "data": scheduler.get_status(),
    }


def configure_macd_optimization_schedule(enabled: bool, opt_time: str, notify_feishu: bool) -> dict:
    scheduler = get_scheduler()
    if not scheduler.set_macd_optimization_time(opt_time):
        raise ValueError("无效的时间格式，请使用 HH:MM 格式")
    scheduler.set_macd_optimization_enabled(enabled)
    scheduler.set_macd_optimization_notify_feishu(bool(notify_feishu))
    if not config.update_config({
        "macd_optimization_schedule": {
            "enabled": enabled,
            "time": opt_time,
            "lookback_days": 365,
            "notify_feishu": bool(notify_feishu),
        }
    }):
        raise RuntimeError("保存MACD优化调度配置失败")
    return {
        "success": True,
        "message": f"MACD参数优化定时任务已{'启用' if enabled else '禁用'}，执行时间: {opt_time}",
        "data": scheduler.get_status(),
    }
```

- [ ] **Step 4: Update scheduler API routes**

In `api/main.py`, update `get_scheduler_status()`:

```python
@app.get("/api/data-update/scheduler/status")
async def get_scheduler_status():
    try:
        from core.scheduler_settings_service import get_scheduler_settings_status

        return get_scheduler_settings_status()
    except Exception as e:
        return {
            "success": True,
            "data": {
                "enabled": False,
                "is_running": False,
                "update_time": "15:05",
                "next_run": None,
                "update_status": {
                    "is_updating": False,
                    "message": f"调度器初始化失败: {str(e)}",
                },
                "error": str(e),
            },
        }
```

In `configure_scheduler()` body:

```python
    try:
        from core.scheduler_settings_service import configure_data_update_schedule

        data = await request.json()
        return configure_data_update_schedule(
            enabled=data.get("enabled", False),
            update_time=data.get("update_time", "15:05"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

In `configure_feishu_notification()` body:

```python
    try:
        from core.scheduler_settings_service import configure_feishu_notification_schedule

        data = await request.json()
        return configure_feishu_notification_schedule(
            enabled=data.get("enabled", False),
            times=data.get("times", ["09:40", "10:40", "11:40", "13:40", "14:40"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

In `configure_macd_optimization_schedule()` body:

```python
    try:
        from core.scheduler_settings_service import configure_macd_optimization_schedule as configure_schedule

        data = await request.json()
        return configure_schedule(
            enabled=data.get("enabled", False),
            opt_time=data.get("time", "23:00"),
            notify_feishu=data.get("notify_feishu", False),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 5: Run scheduler tests**

Run:

```bash
pytest tests/test_scheduler_settings_service.py tests/test_settings_macd_optimization.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add core/scheduler_settings_service.py api/main.py tests/test_scheduler_settings_service.py tests/test_settings_macd_optimization.py
git commit -m "refactor: extract scheduler settings service"
```

---

### Task 4: Remove Active Homepage Scheduler Configuration

**Files:**
- Modify: `templates/index.html`
- Modify: `static/js/home.js`
- Modify: `static/css/home.css`
- Modify: `tests/test_home_daily_profit_frontend.py`

- [ ] **Step 1: Add failing frontend source test**

Append to `tests/test_home_daily_profit_frontend.py`:

```python
def test_homepage_does_not_expose_scheduler_configuration_modal():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = HOME_JS.read_text(encoding="utf-8")

    assert "schedulerSettingsModal" not in html
    assert "schedulerSettingsBtn" not in html
    assert "saveSchedulerSettings" not in source
    assert "/api/macd/optimization/schedule/configure" not in source
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
pytest tests/test_home_daily_profit_frontend.py::test_homepage_does_not_expose_scheduler_configuration_modal -q
```

Expected: fail because homepage still contains scheduler modal/save logic.

- [ ] **Step 3: Remove scheduler settings button and modal from `templates/index.html`**

Remove the button with `id="schedulerSettingsBtn"`.

Remove the entire block:

```html
<div id="schedulerSettingsModal" class="modal">
    ...
</div>
```

Keep `schedulerStatusBanner` only if passive status display remains.

- [ ] **Step 4: Remove active scheduler configuration functions from `static/js/home.js`**

Delete these functions and event hookups:

```javascript
showSchedulerSettings
hideSchedulerSettings
loadSchedulerSettings
saveSchedulerSettings
```

Delete the fetch call to:

```javascript
/api/macd/optimization/schedule/configure
```

Keep this passive call if current homepage still renders the status banner:

```javascript
loadSchedulerStatus();
```

- [ ] **Step 5: Remove unused scheduler modal CSS**

In `static/css/home.css`, remove selectors that only support the deleted modal:

```css
.btn-scheduler
.scheduler-modal
.scheduler-current-status
.scheduler-next-run-info
.modal-actions
```

Keep passive `.scheduler-status-banner` styles if the status banner remains.

- [ ] **Step 6: Run frontend source tests**

Run:

```bash
pytest tests/test_home_daily_profit_frontend.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add templates/index.html static/js/home.js static/css/home.css tests/test_home_daily_profit_frontend.py
git commit -m "refactor: keep scheduler settings on settings page"
```

---

### Task 5: Final Integration Verification

**Files:**
- Modify only if tests expose a real integration issue.

- [ ] **Step 1: Run focused integration tests**

Run:

```bash
pytest \
  tests/test_position_signal_service.py \
  tests/test_position_grid_freeze.py \
  tests/test_feishu_report_shared_rows.py \
  tests/test_feishu_notifier.py \
  tests/test_scheduler_settings_service.py \
  tests/test_settings_macd_optimization.py \
  tests/test_home_daily_profit_frontend.py \
  tests/test_monthly_profit_calculation.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Inspect remaining duplication**

Run:

```bash
rg -n "和API相同的逻辑|每仓200元|\\* 200|schedulerSettingsModal|saveSchedulerSettings|/api/macd/optimization/schedule/configure" core api static templates tests
```

Expected:

- No active duplicate Feishu/API row generation comments.
- No `* 200` in production P&L logic outside `core.profit_calculator`.
- No homepage scheduler settings modal or save function.
- Settings page may still reference `/api/macd/optimization/schedule/configure`.

- [ ] **Step 4: Commit any test-driven cleanup**

Only if Step 1-3 required edits, run:

```bash
git add <changed-files>
git commit -m "test: verify signal and scheduler decoupling"
```

- [ ] **Step 5: Push**

Use the configured remote or one-time token push:

```bash
git push origin main
```

Expected: push succeeds and `git status --short --branch` shows only intentionally untracked local artifacts, such as `.superpowers/`.

---

## Self-Review Notes

- Spec coverage: Task 1 covers shared homepage rows, cache/freeze, and profit fields. Task 2 covers Feishu shared rows. Task 3 covers scheduler services. Task 4 covers settings-only frontend behavior. Task 5 covers verification.
- Placeholder scan: no planned step depends on an undefined later function without showing the signature and expected behavior.
- Type consistency: service functions use the signatures from the spec: `build_position_signal_rows`, `build_feishu_operation_rows`, `get_scheduler_settings_status`, `configure_data_update_schedule`, `configure_feishu_notification_schedule`, and `configure_macd_optimization_schedule`.
