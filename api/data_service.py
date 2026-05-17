import hmac

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

import config


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
