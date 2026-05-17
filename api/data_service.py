import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

import config
from core.database import get_latest_daily_bars


UNAUTHORIZED_RESPONSE = {
    "error": "未认证",
    "message": "无效的 API Key",
    "code": "UNAUTHORIZED",
}


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
    days: int = Query(default=60),
):
    normalized_symbol = symbol.strip() if symbol else ""
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    if days < 1 or days > 1000:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 1000",
        )

    bars = get_latest_daily_bars(normalized_symbol, days)
    if bars is None:
        raise HTTPException(status_code=500, detail="database unavailable")

    response_bars = [
        {
            "trade_date": bar["trade_date"],
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar["vol"],
        }
        for bar in bars
    ]

    return {
        "success": True,
        "data": {
            "symbol": normalized_symbol,
            "count": len(response_bars),
            "bars": response_bars,
        },
    }
