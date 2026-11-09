from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.router import api_router
from app.config import get_settings
from app.core.logging import setup_logging
from app.core.scheduler import start_scheduler, stop_scheduler
from app.database.session import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    settings = get_settings()
    setup_logging(debug=settings.debug)

    # Database initialization
    await init_db()

    # Scheduler startup
    start_scheduler()

    yield

    # Clean shutdown
    stop_scheduler()
    await close_db()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="MARY: Autonomous Group AI Agent for LINE",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(api_router)

    @app.get("/")
    async def root():
        return {
            "status": "ok",
            "app": settings.app_name,
            "message": "MARY Botline Service is running.",
            "health": "/health",
            "webhook": "/webhooks/line",
        }

    return app


app = create_app()

