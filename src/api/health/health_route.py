from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="API Health Check")
async def get_health():
    """Basic health check endpoint."""

    return {
        "message": "Weather Bot API is running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }