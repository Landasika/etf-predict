import hmac
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

import config
from core.database import get_latest_daily_bars


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


def _parse_daily_days(days: str | None) -> int:
    if days is None:
        normalized_days = 60
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


def _serialize_daily_bar(bar: dict) -> dict:
    return {
        "trade_date": bar["trade_date"],
        "open": bar["open"],
        "high": bar["high"],
        "low": bar["low"],
        "close": bar["close"],
        "volume": bar["vol"],
    }


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
            "bars": [_serialize_daily_bar(bar) for bar in bars],
        },
    }
