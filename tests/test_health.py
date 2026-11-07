import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_200(async_client: AsyncClient):
    """Verify that the health check endpoint returns 200, healthy status, and verified DB connection."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "MARY"
    assert data["database_connected"] is True
    assert "timestamp_utc" in data
    assert "timestamp_local" in data
