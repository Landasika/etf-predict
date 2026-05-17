# Data Service API Design

## Summary

Add a dedicated read-only data service router to the existing FastAPI app so external programs can read ETF daily bar data from `etf.db` without using the session-login flow. The router will live under `/api/data-service/*`, use `X-API-Key` token authentication, and reuse the existing database access layer in `core/database.py`.

This replaces the idea of a separate `python3 data_server.py --port 8001` process. The project will keep a single FastAPI service on the existing port and expose the data endpoints inside that app.

## Context

The project already has:

- a FastAPI application in `api/main.py`
- session-based authentication for most `/api/*` routes
- SQLite access helpers in `core/database.py`
- partially overlapping endpoints for K-line data and latest trade date

The requested feature is different from the existing UI-oriented endpoints:

- it should serve external callers directly
- it should not require browser login sessions
- it should expose a simpler data-service contract for single-symbol and batch daily-bar reads

## Goals

- Expose ETF daily bar data through the existing FastAPI service
- Keep the implementation read-only
- Reuse `AUTH_KEY` as the API token
- Keep the new API isolated from session authentication
- Return responses in the project’s existing `success/data/message` style
- Keep the endpoint contract simple for scripts and external services

## Non-Goals

- No separate HTTP process on port `8001`
- No database schema changes
- No write endpoints
- No caching layer
- No support for multiple API tokens in this change
- No change to existing watchlist or UI endpoints unless required for integration

## Chosen Approach

Use a new router module mounted into the current FastAPI app.

### Why this approach

- It fits the current application architecture
- It avoids adding a second deployment unit
- It keeps data-service code isolated from the already large `api/main.py`
- It allows OpenAPI docs, shared logging, and shared config without duplication

### Rejected alternatives

1. Add the endpoints directly into `api/main.py`

This is the fastest short-term option but makes an already large file harder to maintain.

2. Run a separate lightweight HTTP server

This matches the original standalone script, but adds another deployment path, another process model, and duplicated database access code without enough benefit.

## API Surface

All endpoints are mounted under `/api/data-service`.

### `GET /api/data-service/health`

Purpose:

- confirm the data-service router is reachable

Response:

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "service": "data-service"
  }
}
```

### `GET /api/data-service/daily`

Query parameters:

- `symbol` required, ETF code such as `562360.SH`
- `days` optional, default `60`, valid range `1..1000`

Behavior:

- returns the latest `days` daily bars for one ETF
- bars are ordered from newest to oldest to match the originally proposed service behavior

Response shape:

```json
{
  "success": true,
  "data": {
    "symbol": "562360.SH",
    "count": 60,
    "bars": [
      {
        "trade_date": "20260515",
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.05,
        "volume": 123456
      }
    ]
  }
}
```

### `GET /api/data-service/daily/batch`

Query parameters:

- `symbols` required, comma-separated ETF codes
- `date` optional, exact trade date in `YYYYMMDD`
- `days` optional, default `5`, valid range `1..1000`

Behavior:

- if `date` is provided, return bars for that exact date per symbol
- otherwise return the latest `days` bars per symbol
- if both `date` and `days` are provided, `date` takes precedence

Response shape:

```json
{
  "success": true,
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
          "volume": 123456
        }
      ],
      "515790.SH": []
    }
  }
}
```

### `GET /api/data-service/latest-date`

Purpose:

- return the latest trade date available in `etf_daily`

Response:

```json
{
  "success": true,
  "data": {
    "latest_date": "20260515"
  }
}
```

If the table has no data, `latest_date` returns `null`.

## Authentication Design

The router will use token-based authentication instead of session-based browser authentication.

### Token source

- reuse the existing `AUTH_KEY`
- do not add a new config entry in this change

### Request format

- callers must send `X-API-Key: <AUTH_KEY>`

### Enforcement model

- requests under `/api/data-service/` bypass session-login checks
- those same requests are still protected by token validation
- missing or invalid token returns HTTP `401`

### Rationale

- external scripts should not need login cookies
- reusing `AUTH_KEY` avoids expanding configuration surface
- a dedicated branch keeps the data-service behavior explicit instead of mixing it into page-auth logic

## Validation Rules

### `symbol`

- required for `/daily`
- must be a non-empty string after trimming

### `symbols`

- required for `/daily/batch`
- split on commas
- trim whitespace
- drop empty entries
- if the final symbol list is empty, return HTTP `400`

### `days`

- `/daily` default `60`
- `/daily/batch` default `5`
- must satisfy `1 <= days <= 1000`
- invalid values return HTTP `400`

### `date`

- optional
- if present, must be an 8-digit `YYYYMMDD` string
- invalid values return HTTP `400`

## Data Access Design

Extend `core/database.py` with focused read helpers rather than embedding SQL in the route handlers.

Planned helper responsibilities:

- fetch latest N daily bars for one symbol
- fetch daily bars for one symbol on an exact trade date
- fetch latest trade date

Implementation notes:

- reuse the existing SQLite connection helper
- keep the service read-only
- map `vol` to `volume` in API responses
- keep SQL and response shaping separate where practical

For batch reads, the initial implementation may query per symbol for clarity. If performance becomes an issue later, it can be optimized to a grouped query without changing the API contract.

## Integration Points

### New module

- `api/data_service.py`

Responsibilities:

- define the router
- define token-auth dependency or helper
- define the four endpoints
- perform request validation and response shaping

### Existing app wiring

- update `api/main.py` to include the new router
- update the auth middleware in `api/main.py` so `/api/data-service/*` skips session enforcement and relies on token auth

### Database module

- extend `core/database.py` with the minimal query helpers needed by the router

## Error Handling

### Authentication errors

- missing token: HTTP `401`
- invalid token: HTTP `401`

### Request validation errors

- missing `symbol` or `symbols`: HTTP `400`
- invalid `days`: HTTP `400`
- invalid `date`: HTTP `400`

### Data and runtime behavior

- symbol not found or no matching rows: return success with an empty `bars` array
- partial no-data in batch mode: preserve every requested symbol key and return empty arrays where needed
- database unavailable or unexpected runtime failure: HTTP `500` with a clear message

This keeps the API easy to consume for machine clients because “no rows” is not treated as an exceptional condition.

## Testing Strategy

Add a dedicated API test module:

- `tests/test_data_service_api.py`

### Test style

- use `FastAPI TestClient`
- use `monkeypatch` to override `AUTH_KEY` checks where needed
- mock or patch database helper functions so tests do not depend on a real `data/etf.db`

### Required coverage

1. health endpoint succeeds with a valid token
2. any endpoint returns `401` when the token is missing
3. `/daily` returns `400` when `symbol` is missing
4. `/daily` returns normalized success structure with bar data
5. `/daily/batch` works in latest-bars mode
6. `/daily/batch` works in exact-date mode
7. `/latest-date` returns the expected structure
8. empty query results still return `success: true`

### TDD execution

- write failing API tests first
- verify failure reason is correct
- implement the router and database helpers
- rerun targeted tests, then broader relevant tests

## Rollout Notes

- no deployment topology change is required
- no environment variable changes are required
- external callers only need the existing service base URL and `AUTH_KEY`

Example request:

```bash
curl -H "X-API-Key: admin123" \
  "http://127.0.0.1:8000/api/data-service/daily?symbol=562360.SH&days=5"
```

## Risks and Mitigations

### Risk: `AUTH_KEY` reuse couples UI admin auth and data-service auth

Mitigation:

- acceptable for this change because it keeps config simple
- can be split later into a dedicated `DATA_API_TOKEN` without changing endpoint paths

### Risk: `api/main.py` auth middleware becomes more complex

Mitigation:

- keep the new branch narrow and path-scoped to `/api/data-service/`
- keep token validation logic centralized and explicit

### Risk: batch endpoint performs repeated symbol queries

Mitigation:

- acceptable for initial scope
- optimize only if real usage shows a bottleneck

## Implementation Outline

1. Add failing API tests for the new router behavior
2. Add database helper functions for daily bars and latest date
3. Add `api/data_service.py`
4. Wire the router into `api/main.py`
5. Update middleware behavior for `/api/data-service/*`
6. Run targeted tests and relevant regression checks
