"""Tests for the dashboard API endpoint."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestGetDashboard:
    """Tests for GET /api/dashboard."""

    async def test_dashboard_returns_aggregate_data(self, async_client):
        """Dashboard returns review count, activity, and courses."""
        mock_course = AsyncMock()
        mock_course.id = "course-001"
        mock_course.code = "CSIT302"
        mock_course.name = "Cybersecurity"
        mock_course.term = "2024-S1"
        mock_course.created_at = datetime(2024, 1, 1)
        mock_course.updated_at = datetime(2024, 1, 2)

        with (
            patch(
                "app.api.dashboard.review_service.count_pending_reviews",
                new_callable=AsyncMock,
                return_value=3,
            ),
            patch(
                "app.api.dashboard.pipeline_service.get_recent_activity",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "pipeline_run_id": "run-001",
                        "artifact_id": "art-001",
                        "filename": "lecture.pdf",
                        "stage": "ingest",
                        "status": "completed",
                        "started_at": "2024-01-01T00:00:00",
                        "completed_at": "2024-01-01T00:00:05",
                        "duration_ms": 5000,
                    }
                ],
            ),
            patch(
                "app.api.dashboard.course_service.list_courses",
                new_callable=AsyncMock,
                return_value=[mock_course],
            ),
            patch(
                "app.api.dashboard.course_service.get_course_weeks",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "week": 1,
                        "titles": ["Intro"],
                        "artifact_count": 2,
                        "summary_status": "generated",
                        "summary_id": "sum-001",
                        "flashcard_count": 5,
                        "quiz_count": 3,
                    }
                ],
            ),
        ):
            response = await async_client.get("/api/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["pending_review_count"] == 3
        assert len(data["recent_activity"]) == 1
        assert data["recent_activity"][0]["stage"] == "ingest"
        assert len(data["courses"]) == 1
        assert data["courses"][0]["code"] == "CSIT302"
        assert data["courses"][0]["weeks_covered"] == 1
        assert data["courses"][0]["total_artifacts"] == 2

    async def test_dashboard_empty_state(self, async_client):
        """Dashboard returns empty data when nothing exists."""
        with (
            patch(
                "app.api.dashboard.review_service.count_pending_reviews",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "app.api.dashboard.pipeline_service.get_recent_activity",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.api.dashboard.course_service.list_courses",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            response = await async_client.get("/api/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["pending_review_count"] == 0
        assert data["recent_activity"] == []
        assert data["courses"] == []
