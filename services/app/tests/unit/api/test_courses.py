"""Tests for the courses API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestListCourses:
    """Tests for GET /api/courses."""

    async def test_list_courses_returns_courses_with_stats(self, async_client):
        """List courses returns courses with aggregate data."""
        with patch(
            "app.api.courses.course_service.list_courses_with_stats",
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
                    "total_artifacts": 1,
                    "last_updated": datetime(2024, 1, 2),
                }
            ],
        ):
            response = await async_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "CSIT302"
        assert data[0]["weeks_covered"] == 1
        assert data[0]["total_artifacts"] == 1

    async def test_list_courses_empty(self, async_client):
        """List courses returns empty list when no courses exist."""
        with patch(
            "app.api.courses.course_service.list_courses_with_stats",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get("/api/courses")

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
class TestGetCourseDetail:
    """Tests for GET /api/courses/{course_code}."""

    async def test_get_course_detail_success(self, async_client):
        """Get course detail returns course with per-week breakdown."""
        mock_course = AsyncMock()
        mock_course.id = "course-001"
        mock_course.code = "CSIT302"
        mock_course.name = "Cybersecurity"
        mock_course.term = "2024-S1"
        mock_course.created_at = datetime(2024, 1, 1)
        mock_course.updated_at = datetime(2024, 1, 2)

        with (
            patch(
                "app.api.courses.course_service.get_course_by_code",
                new_callable=AsyncMock,
                return_value=mock_course,
            ),
            patch(
                "app.api.courses.course_service.get_course_weeks",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "week": 1,
                        "titles": ["Intro"],
                        "artifact_count": 2,
                        "summary_status": "generated",
                        "summary_id": "sum-001",
                        "flashcard_count": 10,
                        "quiz_count": 5,
                    },
                    {
                        "week": 2,
                        "titles": ["Networks"],
                        "artifact_count": 1,
                        "summary_status": "pending",
                        "summary_id": None,
                        "flashcard_count": 0,
                        "quiz_count": 0,
                    },
                ],
            ),
        ):
            response = await async_client.get("/api/courses/CSIT302")

        assert response.status_code == 200
        data = response.json()
        assert data["course"]["code"] == "CSIT302"
        assert len(data["weeks"]) == 2
        assert data["weeks"][0]["week"] == 1
        assert data["weeks"][0]["summary_status"] == "generated"

    async def test_get_course_detail_not_found(self, async_client):
        """Get course detail returns 404 for unknown course."""
        with patch(
            "app.api.courses.course_service.get_course_by_code",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get("/api/courses/UNKNOWN")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestGetWeekDetail:
    """Tests for GET /api/courses/{course_code}/weeks/{week}."""

    async def test_get_week_detail_success(self, async_client):
        """Get week detail returns course, summary, and artifacts."""
        mock_course = AsyncMock()
        mock_course.id = "course-001"
        mock_course.code = "CSIT302"
        mock_course.name = "Cybersecurity"
        mock_course.term = "2024-S1"
        mock_course.created_at = datetime(2024, 1, 1)
        mock_course.updated_at = datetime(2024, 1, 2)

        mock_artifact = AsyncMock()
        mock_artifact.id = "art-001"
        mock_artifact.course_id = "course-001"
        mock_artifact.week = 5
        mock_artifact.title = "Network Security"
        mock_artifact.original_filename = "CSIT302_Week5.pdf"
        mock_artifact.file_type = "pdf"
        mock_artifact.sha256 = "a" * 64
        mock_artifact.file_size_bytes = 1024
        mock_artifact.status = "summarized"
        mock_artifact.created_at = datetime(2024, 1, 1)

        with (
            patch(
                "app.api.courses.course_service.get_course_by_code",
                new_callable=AsyncMock,
                return_value=mock_course,
            ),
            patch(
                "app.api.courses.artifact_service.list_artifacts",
                new_callable=AsyncMock,
                return_value=[mock_artifact],
            ),
            patch(
                "app.api.courses.summary_service.get_summary_for_week",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            response = await async_client.get("/api/courses/CSIT302/weeks/5")

        assert response.status_code == 200
        data = response.json()
        assert data["course"]["code"] == "CSIT302"
        assert data["week"] == 5
        assert data["summary"] is None
        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["original_filename"] == "CSIT302_Week5.pdf"

    async def test_get_week_detail_course_not_found(self, async_client):
        """Get week detail returns 404 for unknown course."""
        with patch(
            "app.api.courses.course_service.get_course_by_code",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get("/api/courses/UNKNOWN/weeks/1")

        assert response.status_code == 404
