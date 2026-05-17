# Data Service API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a token-protected read-only data-service router under `/api/data-service/*` that exposes ETF daily bars and the latest trade date from the existing FastAPI service.

**Architecture:** Keep the feature inside the current FastAPI app. Authenticate `/api/data-service/*` in `AuthMiddleware` using `X-API-Key` mapped to `config.AUTH_KEY`, and place route handlers in a new `api/data_service.py` module that reuses focused read helpers from `core/database.py`.

**Tech Stack:** FastAPI, Starlette middleware, SQLite via `sqlite3`, pytest, FastAPI `TestClient`

---

## File Structure

- Create: `api/data_service.py`
  Owns the `/api/data-service/*` router, API key helper, request validation helpers, and success response shaping.
- Modify: `api/main.py`
  Owns middleware behavior and FastAPI router registration.
- Modify: `core/database.py`
  Owns the minimal read helpers for recent bars and exact-date bars.
- Create: `tests/test_data_service_api.py`
  Owns end-to-end API tests for auth, daily bars, batch bars, and latest-date responses.

## Task 1: Add Router Skeleton and API Key Authentication

**Files:**
- Create: `api/data_service.py`
- Modify: `api/main.py`
- Test: `tests/test_data_service_api.py`

- [ ] **Step 1: Write the failing auth and health tests**

```python
from fastapi.testclient import TestClient

import config
from api.main import app

client = TestClient(app)


def _api_headers(api_key="test-auth-key"):
    return {"X-API-Key": api_key}


def test_data_service_health_returns_service_status_with_api_key(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")

    response = client.get("/api/data-service/health", headers=_api_headers())

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "data-service",
        },
    }


def test_data_service_health_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")

    response = client.get("/api/data-service/health")

    assert response.status_code == 401
    assert response.json() == {
        "error": "未认证",
        "message": "无效的 API Key",
        "code": "UNAUTHORIZED",
    }
```

- [ ] **Step 2: Run the targeted tests and verify they fail for the right reason**

Run: `pytest tests/test_data_service_api.py::test_data_service_health_returns_service_status_with_api_key tests/test_data_service_api.py::test_data_service_health_rejects_missing_api_key -v`

Expected: FAIL. The first test should show `assert 401 == 200` because `/api/*` is still gated by session auth, and the second should fail because the current 401 payload says `请先登录系统` instead of `无效的 API Key`.

- [ ] **Step 3: Write the minimal router and middleware changes**

Add `api/data_service.py`:

```python
from typing import Optional

from fastapi import APIRouter

import config

router = APIRouter(prefix="/api/data-service")


def has_valid_data_service_api_key(api_key: Optional[str]) -> bool:
    return bool(api_key) and api_key == config.AUTH_KEY


@router.get("/health")
async def data_service_health():
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "data-service",
        },
    }
```

Update `api/main.py` imports and middleware:

```python
from api.data_service import router as data_service_router, has_valid_data_service_api_key
```

```python
        # 3. 数据服务路由 - 跳过 session 认证，改为 API Key 鉴权
        if path.startswith("/api/data-service/"):
            api_key = request.headers.get("X-API-Key")
            if not has_valid_data_service_api_key(api_key):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "未认证",
                        "message": "无效的 API Key",
                        "code": "UNAUTHORIZED"
                    }
                )
            return await call_next(request)

        # 4. 检查session是否可用
```

Register the router in `api/main.py` next to the other routers:

```python
app.include_router(auth_router, tags=["认证"])
app.include_router(data_service_router, tags=["数据服务"])
```

- [ ] **Step 4: Run the targeted tests and verify they pass**

Run: `pytest tests/test_data_service_api.py::test_data_service_health_returns_service_status_with_api_key tests/test_data_service_api.py::test_data_service_health_rejects_missing_api_key -v`

Expected: PASS for both tests.

- [ ] **Step 5: Commit the skeleton and auth wiring**

```bash
git add api/data_service.py api/main.py tests/test_data_service_api.py
git commit -m "feat: add data service auth and health endpoint"
```

## Task 2: Add the Single-Symbol Daily Endpoint

**Files:**
- Modify: `api/data_service.py`
- Modify: `core/database.py`
- Test: `tests/test_data_service_api.py`

- [ ] **Step 1: Write the failing tests for `/api/data-service/daily`**

Add to `tests/test_data_service_api.py`:

```python
import api.data_service as data_service
```

```python
def test_data_service_daily_requires_symbol(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")

    response = client.get("/api/data-service/daily", headers=_api_headers())

    assert response.status_code == 400
    assert response.json() == {"detail": "symbol is required"}


def test_data_service_daily_rejects_invalid_days(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")

    response = client.get(
        "/api/data-service/daily?symbol=562360.SH&days=0",
        headers=_api_headers(),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "days must be between 1 and 1000"}


def test_data_service_daily_returns_latest_bars(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")
    monkeypatch.setattr(
        data_service.database,
        "get_recent_etf_daily_bars",
        lambda symbol, days: [
            {
                "trade_date": "20260515",
                "open": 1.0,
                "high": 1.1,
                "low": 0.9,
                "close": 1.05,
                "vol": 123456,
            },
            {
                "trade_date": "20260514",
                "open": 0.98,
                "high": 1.02,
                "low": 0.95,
                "close": 1.0,
                "vol": 120000,
            },
        ],
    )

    response = client.get(
        "/api/data-service/daily?symbol=562360.SH&days=2",
        headers=_api_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "symbol": "562360.SH",
            "count": 2,
            "bars": [
                {
                    "trade_date": "20260515",
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.05,
                    "volume": 123456,
                },
                {
                    "trade_date": "20260514",
                    "open": 0.98,
                    "high": 1.02,
                    "low": 0.95,
                    "close": 1.0,
                    "volume": 120000,
                },
            ],
        },
    }


def test_data_service_daily_returns_empty_bars_when_symbol_has_no_rows(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")
    monkeypatch.setattr(
        data_service.database,
        "get_recent_etf_daily_bars",
        lambda symbol, days: [],
    )

    response = client.get(
        "/api/data-service/daily?symbol=000000.SH&days=5",
        headers=_api_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "symbol": "000000.SH",
            "count": 0,
            "bars": [],
        },
    }
```

- [ ] **Step 2: Run the daily endpoint tests and verify they fail**

Run: `pytest tests/test_data_service_api.py::test_data_service_daily_requires_symbol tests/test_data_service_api.py::test_data_service_daily_rejects_invalid_days tests/test_data_service_api.py::test_data_service_daily_returns_latest_bars tests/test_data_service_api.py::test_data_service_daily_returns_empty_bars_when_symbol_has_no_rows -v`

Expected: FAIL. `/api/data-service/daily` does not exist yet, so the tests should fail with `404` where `400` or `200` is expected.

- [ ] **Step 3: Add the database helper and daily endpoint**

Add to `core/database.py`:

```python
def get_recent_etf_daily_bars(ts_code: str, days: int) -> Optional[List[Dict]]:
    """Get the latest N daily bars for one ETF in descending trade_date order."""
    conn = get_etf_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT trade_date, open, high, low, close, vol
        FROM etf_daily
        WHERE ts_code = ?
        ORDER BY trade_date DESC
        LIMIT ?
        ''',
        (ts_code, days),
    )
    results = cursor.fetchall()
    conn.close()
    return [dict(r) for r in results]
```

Update `api/data_service.py`:

```python
from fastapi import APIRouter, HTTPException, Query

from core import database
```

```python
def _serialize_bar(row: dict) -> dict:
    return {
        "trade_date": row["trade_date"],
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "volume": row["vol"],
    }


def _validate_days(days: int) -> int:
    if days < 1 or days > 1000:
        raise HTTPException(status_code=400, detail="days must be between 1 and 1000")
    return days


@router.get("/daily")
async def get_daily_data(
    symbol: str = Query(...),
    days: int = Query(60),
):
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    normalized_days = _validate_days(days)
    rows = database.get_recent_etf_daily_bars(normalized_symbol, normalized_days)
    if rows is None:
        raise HTTPException(status_code=500, detail="database unavailable")

    return {
        "success": True,
        "data": {
            "symbol": normalized_symbol,
            "count": len(rows),
            "bars": [_serialize_bar(row) for row in rows],
        },
    }
```

- [ ] **Step 4: Run the daily endpoint tests and verify they pass**

Run: `pytest tests/test_data_service_api.py::test_data_service_daily_requires_symbol tests/test_data_service_api.py::test_data_service_daily_rejects_invalid_days tests/test_data_service_api.py::test_data_service_daily_returns_latest_bars tests/test_data_service_api.py::test_data_service_daily_returns_empty_bars_when_symbol_has_no_rows -v`

Expected: PASS for all three tests.

- [ ] **Step 5: Commit the single-symbol endpoint**

```bash
git add api/data_service.py core/database.py tests/test_data_service_api.py
git commit -m "feat: add single-symbol data service endpoint"
```

## Task 3: Add the Batch Daily Endpoint

**Files:**
- Modify: `api/data_service.py`
- Modify: `core/database.py`
- Test: `tests/test_data_service_api.py`

- [ ] **Step 1: Write the failing tests for `/api/data-service/daily/batch`**

Add to `tests/test_data_service_api.py`:

```python
def test_data_service_daily_batch_returns_latest_bars_per_symbol(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")

    def fake_recent(symbol, days):
        assert days == 2
        dataset = {
            "562360.SH": [
                {
                    "trade_date": "20260515",
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.05,
                    "vol": 123456,
                }
            ],
            "515790.SH": [],
        }
        return dataset[symbol]

    monkeypatch.setattr(
        data_service.database,
        "get_recent_etf_daily_bars",
        fake_recent,
    )

    response = client.get(
        "/api/data-service/daily/batch?symbols=562360.SH,515790.SH&days=2",
        headers=_api_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "count": 2,
            "bars": {
                "562360.SH": [
                    {
                        "trade_date": "20260515",
                        "open": 1.0,
                        "high": 1.1,
                        "low": 0.9,
                        "close": 1.05,
                        "volume": 123456,
                    }
                ],
                "515790.SH": [],
            },
        },
    }


def test_data_service_daily_batch_requires_symbols(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")

    response = client.get(
        "/api/data-service/daily/batch?symbols= , , ",
        headers=_api_headers(),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "symbols is required"}


def test_data_service_daily_batch_uses_exact_date_when_provided(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")

    def fake_by_date(symbol, trade_date):
        assert trade_date == "20260515"
        dataset = {
            "562360.SH": [
                {
                    "trade_date": "20260515",
                    "open": 1.0,
                    "high": 1.1,
                    "low": 0.9,
                    "close": 1.05,
                    "vol": 123456,
                }
            ],
            "515790.SH": [],
        }
        return dataset[symbol]

    monkeypatch.setattr(
        data_service.database,
        "get_etf_daily_bars_by_date",
        fake_by_date,
    )

    response = client.get(
        "/api/data-service/daily/batch?symbols=562360.SH,515790.SH&date=20260515&days=99",
        headers=_api_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "count": 2,
            "bars": {
                "562360.SH": [
                    {
                        "trade_date": "20260515",
                        "open": 1.0,
                        "high": 1.1,
                        "low": 0.9,
                        "close": 1.05,
                        "volume": 123456,
                    }
                ],
                "515790.SH": [],
            },
        },
    }


def test_data_service_daily_batch_rejects_invalid_date(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")

    response = client.get(
        "/api/data-service/daily/batch?symbols=562360.SH&date=2026-05-15",
        headers=_api_headers(),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "date must be in YYYYMMDD format"}
```

- [ ] **Step 2: Run the batch tests and verify they fail**

Run: `pytest tests/test_data_service_api.py::test_data_service_daily_batch_returns_latest_bars_per_symbol tests/test_data_service_api.py::test_data_service_daily_batch_requires_symbols tests/test_data_service_api.py::test_data_service_daily_batch_uses_exact_date_when_provided tests/test_data_service_api.py::test_data_service_daily_batch_rejects_invalid_date -v`

Expected: FAIL. `/api/data-service/daily/batch` does not exist yet, so the tests should fail with `404` where `200` or `400` is expected.

- [ ] **Step 3: Add the batch query helper and route**

Add to `core/database.py`:

```python
def get_etf_daily_bars_by_date(ts_code: str, trade_date: str) -> Optional[List[Dict]]:
    """Get exact-date daily bars for one ETF."""
    conn = get_etf_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT trade_date, open, high, low, close, vol
        FROM etf_daily
        WHERE ts_code = ? AND trade_date = ?
        ORDER BY trade_date DESC
        ''',
        (ts_code, trade_date),
    )
    results = cursor.fetchall()
    conn.close()
    return [dict(r) for r in results]
```

Update `api/data_service.py` imports:

```python
import re
from typing import List, Optional
```

Add to `api/data_service.py`:

```python
def _parse_symbols(symbols: str) -> List[str]:
    parsed = [item.strip() for item in symbols.split(",") if item.strip()]
    if not parsed:
        raise HTTPException(status_code=400, detail="symbols is required")
    return parsed


def _validate_trade_date(trade_date: str) -> str:
    if not re.fullmatch(r"\d{8}", trade_date):
        raise HTTPException(status_code=400, detail="date must be in YYYYMMDD format")
    return trade_date


@router.get("/daily/batch")
async def get_daily_batch_data(
    symbols: str = Query(...),
    date: Optional[str] = Query(None),
    days: int = Query(5),
):
    parsed_symbols = _parse_symbols(symbols)
    bars = {}

    if date is not None:
        trade_date = _validate_trade_date(date)
        for symbol in parsed_symbols:
            rows = database.get_etf_daily_bars_by_date(symbol, trade_date)
            if rows is None:
                raise HTTPException(status_code=500, detail="database unavailable")
            bars[symbol] = [_serialize_bar(row) for row in rows]
    else:
        normalized_days = _validate_days(days)
        for symbol in parsed_symbols:
            rows = database.get_recent_etf_daily_bars(symbol, normalized_days)
            if rows is None:
                raise HTTPException(status_code=500, detail="database unavailable")
            bars[symbol] = [_serialize_bar(row) for row in rows]

    return {
        "success": True,
        "data": {
            "count": len(parsed_symbols),
            "bars": bars,
        },
    }
```

- [ ] **Step 4: Run the batch tests and verify they pass**

Run: `pytest tests/test_data_service_api.py::test_data_service_daily_batch_returns_latest_bars_per_symbol tests/test_data_service_api.py::test_data_service_daily_batch_requires_symbols tests/test_data_service_api.py::test_data_service_daily_batch_uses_exact_date_when_provided tests/test_data_service_api.py::test_data_service_daily_batch_rejects_invalid_date -v`

Expected: PASS for all three tests.

- [ ] **Step 5: Commit the batch endpoint**

```bash
git add api/data_service.py core/database.py tests/test_data_service_api.py
git commit -m "feat: add batch data service endpoint"
```

## Task 4: Add the Latest-Date Endpoint and Run Final Verification

**Files:**
- Modify: `api/data_service.py`
- Test: `tests/test_data_service_api.py`

- [ ] **Step 1: Write the failing tests for `/api/data-service/latest-date`**

Add to `tests/test_data_service_api.py`:

```python
def test_data_service_latest_date_returns_success_structure(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")
    monkeypatch.setattr(
        data_service.database,
        "get_latest_data_date",
        lambda: "20260515",
    )

    response = client.get("/api/data-service/latest-date", headers=_api_headers())

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "latest_date": "20260515",
        },
    }


def test_data_service_latest_date_returns_null_when_no_rows_exist(monkeypatch):
    monkeypatch.setattr(config, "AUTH_KEY", "test-auth-key")
    monkeypatch.setattr(
        data_service.database,
        "get_latest_data_date",
        lambda: None,
    )

    response = client.get("/api/data-service/latest-date", headers=_api_headers())

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "latest_date": None,
        },
    }
```

- [ ] **Step 2: Run the latest-date tests and verify they fail**

Run: `pytest tests/test_data_service_api.py::test_data_service_latest_date_returns_success_structure tests/test_data_service_api.py::test_data_service_latest_date_returns_null_when_no_rows_exist -v`

Expected: FAIL. `/api/data-service/latest-date` does not exist yet, so the tests should fail with `404` where `200` is expected.

- [ ] **Step 3: Add the latest-date route**

Add to `api/data_service.py`:

```python
@router.get("/latest-date")
async def get_latest_trade_date():
    return {
        "success": True,
        "data": {
            "latest_date": database.get_latest_data_date(),
        },
    }
```

- [ ] **Step 4: Run the new API test file and verify the full feature passes**

Run: `pytest tests/test_data_service_api.py -v`

Expected: PASS for the full file, covering auth, single-symbol reads, batch reads, empty result handling, and latest-date responses.

- [ ] **Step 5: Commit the final endpoint and verification state**

```bash
git add api/data_service.py tests/test_data_service_api.py
git commit -m "feat: add latest-date data service endpoint"
```
