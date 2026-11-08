import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

TEST_DB_PATH = Path("./test_mary.db").resolve()
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"

os.environ["APP_ENV"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["LINE_CHANNEL_SECRET"] = "test-secret-key-12345"
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "test-access-token-token"

# Re-import settings and engine to ensure they pick up test environment
from app.config import get_settings
get_settings.cache_clear()

from app.database.base import Base
import app.models  # Ensure all model tables are registered with Base.metadata
from app.database import session as session_module
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Configure shared test engine
test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
session_module.engine = test_engine
session_module.AsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def setup_test_db():
    """Create all tables before tests and remove database file afterwards."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass


@pytest_asyncio.fixture(loop_scope="session")
async def db_session():
    """Yields a database session for test operations."""
    async with session_module.AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(loop_scope="session")
async def async_client():
    """Provides an async test client for the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
