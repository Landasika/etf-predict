import hmac
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

import config
from core.database import (
    get_daily_bars_by_exact_date,
    get_latest_daily_bars,
    get_latest_data_date,
)


UNAUTHORIZED_RESPONSE = {
    "error": "未认证",
    "message": "无效的 API Key",
    "code": "UNAUTHORIZED",
}
DATABASE_UNAVAILABLE_DETAIL = "database unavailable"


class DataServiceAuthError(Exception):
    pass


def is_valid_api_key(api_key: str | None) -> bool:
    server_key = config.AUTH_KEY
    if not server_key or not api_key:
        return False
    return hmac.compare_digest(api_key, server_key)


def require_data_service_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    if not is_valid_api_key(x_api_key):
        raise DataServiceAuthError


async def data_service_auth_exception_handler(request, exc):
    return JSONResponse(status_code=401, content=UNAUTHORIZED_RESPONSE)


def _normalize_daily_symbol(symbol: str | None) -> str:
    normalized_symbol = symbol.strip() if symbol else ""
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    return normalized_symbol


def _normalize_daily_symbols(symbols: str | None) -> list[str]:
    raw_symbols = [
        symbol.strip()
        for symbol in (symbols or "").split(",")
        if symbol.strip()
    ]
    if not raw_symbols:
        raise HTTPException(status_code=400, detail="symbols is required")

    normalized_symbols = []
    seen_symbols = set()
    for symbol in raw_symbols:
        if symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        normalized_symbols.append(symbol)

    return normalized_symbols


def _parse_daily_days(days: str | None, default_days: int = 60) -> int:
    if days is None:
        normalized_days = default_days
    else:
        try:
            normalized_days = int(days)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="days must be between 1 and 1000",
            )

    if normalized_days < 1 or normalized_days > 1000:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 1000",
        )

    return normalized_days


def _parse_daily_date(date: str | None) -> str | None:
    if date is None:
        return None

    normalized_date = date.strip()
    try:
        datetime.strptime(normalized_date, "%Y%m%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="date must be in YYYYMMDD format",
        )

    return normalized_date


def _serialize_daily_bar(bar: dict) -> dict:
    return {
        "trade_date": bar["trade_date"],
        "open": bar["open"],
        "high": bar["high"],
        "low": bar["low"],
        "close": bar["close"],
        "volume": bar["vol"],
    }


def _serialize_daily_bars(bars: list[dict]) -> list[dict]:
    return [_serialize_daily_bar(bar) for bar in bars]


def _get_daily_bars(symbol: str, days: int, trade_date: str | None) -> list[dict] | None:
    if trade_date is not None:
        return get_daily_bars_by_exact_date(symbol, trade_date)
    return get_latest_daily_bars(symbol, days)


router = APIRouter(
    prefix="/api/data-service",
    dependencies=[Depends(require_data_service_api_key)],
)


@router.get("/health")
async def health_check():
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "data-service",
        },
    }


@router.get("/latest-date")
async def latest_date():
    return {
        "success": True,
        "data": {
            "latest_date": get_latest_data_date(),
        },
    }


@router.get("/daily")
async def get_daily_data(
    symbol: str | None = Query(default=None),
    days: str | None = Query(default=None),
):
    normalized_symbol = _normalize_daily_symbol(symbol)
    normalized_days = _parse_daily_days(days)

    try:
        bars = get_latest_daily_bars(normalized_symbol, normalized_days)
    except sqlite3.Error:
        raise HTTPException(status_code=500, detail=DATABASE_UNAVAILABLE_DETAIL)

    if bars is None:
        raise HTTPException(status_code=500, detail=DATABASE_UNAVAILABLE_DETAIL)

    return {
        "success": True,
        "data": {
            "symbol": normalized_symbol,
            "count": len(bars),
            "bars": _serialize_daily_bars(bars),
        },
    }


@router.get("/daily/batch")
async def get_daily_batch_data(
    symbols: str | None = Query(default=None),
    date: str | None = Query(default=None),
    days: str | None = Query(default=None),
):
    normalized_symbols = _normalize_daily_symbols(symbols)
    normalized_date = _parse_daily_date(date)
    normalized_days = (
        5 if normalized_date is not None else _parse_daily_days(days, default_days=5)
    )
    bars_by_symbol = {}

    for symbol in normalized_symbols:
        try:
            bars = _get_daily_bars(symbol, normalized_days, normalized_date)
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail=DATABASE_UNAVAILABLE_DETAIL)

        if bars is None:
            raise HTTPException(status_code=500, detail=DATABASE_UNAVAILABLE_DETAIL)

        bars_by_symbol[symbol] = _serialize_daily_bars(bars)

    return {
        "success": True,
        "data": {
            "count": len(normalized_symbols),
            "bars": bars_by_symbol,
        },
    }
