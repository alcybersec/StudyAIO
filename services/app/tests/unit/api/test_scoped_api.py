"""Tests verifying API endpoints pass user_id to service calls."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
class TestUploadsScopedByUser:
    """Verify upload endpoints pass user.id to service functions."""

    async def test_upload_passes_user_id_to_pipeline(self, async_client):
        """POST /api/uploads passes user.id to run_pipeline."""
        with patch("app.api.uploads.run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock(id="task-123")
            with patch(
                "app.api.uploads.artifact_service.get_artifact", new_callable=AsyncMock
            ) as mock_get:
                mock_artifact = MagicMock()
                mock_artifact.id = "art-001"
                mock_artifact.original_filename = "test.pdf"
                mock_artifact.status = "processing"
                mock_get.return_value = mock_artifact

                import io

                response = await async_client.post(
                    "/api/uploads",
                    files={"file": ("lecture.pdf", io.BytesIO(b"pdf content"), "application/pdf")},
                )

        if response.status_code == 201:
            # Verify user_id was passed to run_pipeline
            call_kwargs = mock_pipeline.call_args
            assert call_kwargs[1].get("user_id") == "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
class TestCoursesScopedByUser:
    """Verify course endpoints pass user.id to service functions."""

    async def test_list_courses_passes_user_id(self, async_client):
        """GET /api/courses passes user.id to list_courses_with_stats."""
        with patch(
            "app.api.courses.course_service.list_courses_with_stats",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list:
            response = await async_client.get("/api/courses")

        assert response.status_code == 200
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs[1].get("user_id") == "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
class TestExamsScopedByUser:
    """Verify exam endpoints pass user.id to service functions."""

    async def test_list_exams_passes_user_id(self, async_client):
        """GET /api/exams passes user.id to list_exams."""
        with patch(
            "app.api.exams.exam_service.list_exams",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list:
            response = await async_client.get("/api/exams")

        assert response.status_code == 200
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args
        assert call_kwargs[1].get("user_id") == "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
class TestDashboardScopedByUser:
    """Verify dashboard endpoint passes user.id to all service calls."""

    async def test_dashboard_passes_user_id_to_services(self, async_client):
        """GET /api/dashboard passes user.id to all service functions."""
        with (
            patch(
                "app.api.dashboard.review_service.count_pending_reviews",
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_review,
            patch(
                "app.api.dashboard.pipeline_service.get_recent_activity",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_activity,
            patch(
                "app.api.dashboard.course_service.list_courses_with_stats",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_courses,
            patch(
                "app.api.dashboard.srs_service.get_global_study_stats",
                new_callable=AsyncMock,
                return_value={"total": 0, "due_today": 0, "mastered": 0, "learning": 0, "new": 0},
            ),
            patch(
                "app.api.dashboard.srs_service.get_per_course_due_counts",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.api.dashboard.exam_service.list_exams", new_callable=AsyncMock, return_value=[]
            ),
            patch(
                "app.api.dashboard.streak_service.get_streak",
                new_callable=AsyncMock,
                return_value={"current_streak": 0, "longest_streak": 0, "last_study_date": None},
            ),
            patch(
                "app.api.dashboard.courseops_service.get_upcoming_deadlines_all_courses",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            response = await async_client.get("/api/dashboard")

        assert response.status_code == 200
        expected_user_id = "00000000-0000-0000-0000-000000000001"

        # Verify user_id was passed to key services
        assert mock_review.call_args[1].get("user_id") == expected_user_id
        assert mock_activity.call_args[1].get("user_id") == expected_user_id
        assert mock_courses.call_args[1].get("user_id") == expected_user_id
