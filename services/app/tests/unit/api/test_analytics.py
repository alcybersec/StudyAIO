"""Tests for the analytics API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestGetOverview:
    """Tests for GET /api/analytics/overview."""

    async def test_get_overview(self, async_client):
        """Returns overview stats."""
        with patch(
            "app.api.analytics.analytics_service.get_overview",
            new_callable=AsyncMock,
            return_value={
                "total_study_hours": 12.5,
                "total_cards_reviewed": 250,
                "total_sessions": 30,
                "mastery_pct": 42.5,
                "total_flashcards": 80,
                "mastered_flashcards": 34,
                "active_courses": 4,
            },
        ):
            response = await async_client.get("/api/analytics/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["total_study_hours"] == 12.5
        assert data["total_cards_reviewed"] == 250
        assert data["mastery_pct"] == 42.5
        assert data["active_courses"] == 4


@pytest.mark.asyncio
class TestGetHeatmap:
    """Tests for GET /api/analytics/heatmap."""

    async def test_get_heatmap(self, async_client):
        """Returns heatmap data."""
        with patch(
            "app.api.analytics.analytics_service.get_study_heatmap",
            new_callable=AsyncMock,
            return_value=[
                {"date": "2026-03-01", "minutes": 45.0, "cards": 20, "sessions": 2},
                {"date": "2026-03-02", "minutes": 0, "cards": 0, "sessions": 0},
            ],
        ):
            response = await async_client.get("/api/analytics/heatmap")

        assert response.status_code == 200
        data = response.json()
        assert len(data["days"]) == 2
        assert data["days"][0]["minutes"] == 45.0

    async def test_get_heatmap_custom_days(self, async_client):
        """Accepts custom days parameter."""
        with patch(
            "app.api.analytics.analytics_service.get_study_heatmap",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_heatmap:
            response = await async_client.get("/api/analytics/heatmap?days=30")

        assert response.status_code == 200
        # Verify the days parameter was passed through
        mock_heatmap.assert_called_once()
        call_kwargs = mock_heatmap.call_args
        assert call_kwargs.kwargs["days"] == 30


@pytest.mark.asyncio
class TestGetRetention:
    """Tests for GET /api/analytics/retention."""

    async def test_get_retention(self, async_client):
        """Returns retention curve data."""
        with patch(
            "app.api.analytics.analytics_service.get_retention_data",
            new_callable=AsyncMock,
            return_value=[
                {"interval_bucket": 1, "retention_pct": 95.0, "card_count": 15},
                {"interval_bucket": 7, "retention_pct": 80.0, "card_count": 30},
                {"interval_bucket": 30, "retention_pct": 65.0, "card_count": 10},
            ],
        ):
            response = await async_client.get("/api/analytics/retention")

        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) == 3
        assert data["points"][0]["retention_pct"] == 95.0

    async def test_get_retention_by_course(self, async_client):
        """Filters retention data by course_code."""
        with patch(
            "app.api.analytics.analytics_service.get_retention_data",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_retention:
            response = await async_client.get("/api/analytics/retention?course_code=CSIT302")

        assert response.status_code == 200
        mock_retention.assert_called_once()
        call_kwargs = mock_retention.call_args
        assert call_kwargs.kwargs["course_code"] == "CSIT302"


@pytest.mark.asyncio
class TestGetMastery:
    """Tests for GET /api/analytics/mastery."""

    async def test_get_mastery(self, async_client):
        """Returns mastery breakdown data."""
        with patch(
            "app.api.analytics.analytics_service.get_mastery_breakdown",
            new_callable=AsyncMock,
            return_value=[
                {
                    "course_code": "CSIT302",
                    "week": 1,
                    "total": 10,
                    "mastered": 5,
                    "learning": 3,
                    "new": 2,
                    "mastery_pct": 50.0,
                },
            ],
        ):
            response = await async_client.get("/api/analytics/mastery")

        assert response.status_code == 200
        data = response.json()
        assert len(data["weeks"]) == 1
        assert data["weeks"][0]["mastery_pct"] == 50.0
        assert data["weeks"][0]["new"] == 2

    async def test_get_mastery_by_course(self, async_client):
        """Filters mastery by course_code."""
        with patch(
            "app.api.analytics.analytics_service.get_mastery_breakdown",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_mastery:
            response = await async_client.get("/api/analytics/mastery?course_code=CSIT302")

        assert response.status_code == 200
        mock_mastery.assert_called_once()
        call_kwargs = mock_mastery.call_args
        assert call_kwargs.kwargs["course_code"] == "CSIT302"


@pytest.mark.asyncio
class TestGetReadiness:
    """Tests for GET /api/analytics/readiness/{exam_id}."""

    async def test_get_readiness_not_found(self, async_client):
        """Returns 404 when exam not found."""
        with patch(
            "app.api.analytics.analytics_service.get_exam_readiness",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get("/api/analytics/readiness/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
