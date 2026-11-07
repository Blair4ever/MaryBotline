import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from app.config import get_settings

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Return the singleton instance of the AsyncIOScheduler."""
    global scheduler
    if scheduler is None:
        settings = get_settings()
        jobstores = {
            "default": MemoryJobStore()
        }
        scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone=settings.tz,
        )
    return scheduler


def start_scheduler() -> None:
    """Start the scheduler if not already running."""
    s = get_scheduler()
    if not s.running:
        s.start()
        logger.info("APScheduler started successfully.")


def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
        scheduler = None

