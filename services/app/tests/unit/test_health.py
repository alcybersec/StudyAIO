"""Tests for health check endpoints."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Verify liveness and readiness probes."""

    async def test_health_returns_ok(self, async_client):
        """GET /health returns 200 with status ok."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_liveness_returns_ok(self, async_client):
        """GET /health/live returns 200 with status ok."""
        response = await async_client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_readiness_returns_ok_when_healthy(self, async_client):
        """GET /health/ready returns 200 when DB and Redis are reachable."""
        with (
            patch(
                "app.core.database.check_db_connectivity", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "app.core.cache.check_redis_connectivity", new_callable=AsyncMock, return_value=True
            ),
        ):
            response = await async_client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["redis"] == "ok"

    async def test_readiness_returns_503_when_db_down(self, async_client):
        """GET /health/ready returns 503 when database is unreachable."""
        with (
            patch(
                "app.core.database.check_db_connectivity",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.core.cache.check_redis_connectivity", new_callable=AsyncMock, return_value=True
            ),
        ):
            response = await async_client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "unavailable"
        assert data["checks"]["redis"] == "ok"

    async def test_readiness_returns_503_when_redis_down(self, async_client):
        """GET /health/ready returns 503 when Redis is unreachable."""
        with (
            patch(
                "app.core.database.check_db_connectivity", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "app.core.cache.check_redis_connectivity",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            response = await async_client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["redis"] == "unavailable"

    async def test_readiness_returns_503_when_both_down(self, async_client):
        """GET /health/ready returns 503 when both DB and Redis are unreachable."""
        with (
            patch(
                "app.core.database.check_db_connectivity",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.core.cache.check_redis_connectivity",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            response = await async_client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "unavailable"
        assert data["checks"]["redis"] == "unavailable"
