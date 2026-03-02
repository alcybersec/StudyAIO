"""Tests for the dashboard API endpoint."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.services.srs_service import StudyStats


@pytest.mark.asyncio
class TestGetDashboard:
    """Tests for GET /api/dashboard."""

    async def test_dashboard_returns_aggregate_data(self, async_client):
        """Dashboard returns review count, activity, courses, and study stats."""
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
                "app.api.dashboard.course_service.list_courses_with_stats",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "id": "course-001",
                        "code": "CSIT302",
                        "name": "Cybersecurity",
                        "term": "2024-S1",
                        "created_at": datetime(2024, 1, 1),
                        "updated_at": datetime(2024, 1, 2),
                        "weeks_covered": 1,
                        "total_artifacts": 2,
                        "last_updated": datetime(2024, 1, 2),
                    }
                ],
            ),
            patch(
                "app.api.dashboard.srs_service.get_global_study_stats",
                new_callable=AsyncMock,
                return_value=StudyStats(total=20, due_today=5, mastered=8, learning=7, new=5),
            ),
            patch(
                "app.api.dashboard.srs_service.get_per_course_due_counts",
                new_callable=AsyncMock,
                return_value=[{"course_code": "CSIT302", "due_count": 5}],
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
        # Study stats
        assert data["study_stats"]["total"] == 20
        assert data["study_stats"]["due_today"] == 5
        assert data["study_stats"]["mastered"] == 8
        assert len(data["study_stats"]["per_course"]) == 1
        assert data["study_stats"]["per_course"][0]["course_code"] == "CSIT302"

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
                "app.api.dashboard.course_service.list_courses_with_stats",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.api.dashboard.srs_service.get_global_study_stats",
                new_callable=AsyncMock,
                return_value=StudyStats(total=0, due_today=0, mastered=0, learning=0, new=0),
            ),
            patch(
                "app.api.dashboard.srs_service.get_per_course_due_counts",
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
        assert data["study_stats"]["total"] == 0
        assert data["study_stats"]["per_course"] == []

    async def test_dashboard_graceful_study_stats_failure(self, async_client):
        """Dashboard still works if study stats fail."""
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
                "app.api.dashboard.course_service.list_courses_with_stats",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.api.dashboard.srs_service.get_global_study_stats",
                new_callable=AsyncMock,
                side_effect=Exception("DB error"),
            ),
        ):
            response = await async_client.get("/api/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["study_stats"] is None
