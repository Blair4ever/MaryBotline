from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint to verify service status."""
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(settings.tz)

    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "timezone": settings.timezone,
        "timestamp_utc": now_utc.isoformat(),
        "timestamp_local": now_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "line_configured": settings.is_line_configured,
    }

