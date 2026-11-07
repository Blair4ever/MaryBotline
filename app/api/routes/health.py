import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint verifying:
    - Service liveness
    - Database connectivity (executing SELECT 1)
    - System UTC and local (Asia/Bangkok) timestamps
    - LINE Messaging API configuration status
    """
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(settings.tz)

    db_healthy = False
    db_error = None
    try:
        result = await db.execute(text("SELECT 1"))
        db_healthy = result.scalar() == 1
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        db_error = str(exc)

    return {
        "status": "healthy" if db_healthy else "degraded",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "timezone": settings.timezone,
        "timestamp_utc": now_utc.isoformat(),
        "timestamp_local": now_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "line_configured": settings.is_line_configured,
        "database_connected": db_healthy,
        "database_backend": "postgresql" if "postgresql" in settings.database_url else "sqlite",
        "error": db_error,
    }
