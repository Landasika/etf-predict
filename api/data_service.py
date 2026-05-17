from fastapi import APIRouter


router = APIRouter(prefix="/api/data-service")


@router.get("/health")
async def health_check():
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "service": "data-service",
        },
    }
