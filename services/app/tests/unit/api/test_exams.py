"""Tests for the exam API endpoints."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
class TestCreateExam:
    """Tests for POST /api/exams."""

    async def test_creates_exam(self, async_client):
        """Creates an exam and returns 201."""
        mock_exam = MagicMock()
        mock_exam.id = "exam-001"
        mock_exam.course_id = "course-001"
        mock_exam.title = "Midterm"
        mock_exam.exam_date = datetime(2026, 4, 15)
        mock_exam.weeks_scope = [1, 2, 3]
        mock_exam.target_mastery_pct = 80
        mock_exam.status = "active"
        mock_exam.created_at = datetime(2026, 3, 1)
        mock_exam.updated_at = datetime(2026, 3, 1)

        with patch(
            "app.api.exams.exam_service.create_exam",
            new_callable=AsyncMock,
            return_value=mock_exam,
        ):
            response = await async_client.post(
                "/api/exams",
                json={
                    "course_code": "CSIT302",
                    "title": "Midterm",
                    "exam_date": "2026-04-15T09:00:00",
                    "weeks_scope": [1, 2, 3],
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "exam-001"
        assert data["title"] == "Midterm"
        assert data["status"] == "active"

    async def test_create_returns_400_for_invalid(self, async_client):
        """Returns 400 when course not found or date in past."""
        with patch(
            "app.api.exams.exam_service.create_exam",
            new_callable=AsyncMock,
            side_effect=ValueError("Course 'FAKE' not found"),
        ):
            response = await async_client.post(
                "/api/exams",
                json={
                    "course_code": "FAKE",
                    "title": "Test",
                    "exam_date": "2026-04-15T09:00:00",
                    "weeks_scope": [1],
                },
            )

        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    async def test_create_validates_weeks_scope(self, async_client):
        """Returns 422 when weeks_scope is empty."""
        response = await async_client.post(
            "/api/exams",
            json={
                "course_code": "CSIT302",
                "title": "Test",
                "exam_date": "2026-04-15T09:00:00",
                "weeks_scope": [],
            },
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestListExams:
    """Tests for GET /api/exams."""

    async def test_lists_exams(self, async_client):
        """Returns list of exams."""
        mock_exam = MagicMock()
        mock_exam.id = "exam-001"
        mock_exam.course_id = "course-001"
        mock_exam.title = "Midterm"
        mock_exam.exam_date = datetime(2026, 4, 15)
        mock_exam.weeks_scope = [1, 2]
        mock_exam.target_mastery_pct = 80
        mock_exam.status = "active"
        mock_exam.created_at = datetime(2026, 3, 1)
        mock_exam.updated_at = datetime(2026, 3, 1)

        with patch(
            "app.api.exams.exam_service.list_exams",
            new_callable=AsyncMock,
            return_value=[mock_exam],
        ):
            response = await async_client.get("/api/exams?status=active")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Midterm"

    async def test_lists_empty(self, async_client):
        """Returns empty list when no exams."""
        with patch(
            "app.api.exams.exam_service.list_exams",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get("/api/exams")

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
class TestGetExam:
    """Tests for GET /api/exams/{exam_id}."""

    async def test_returns_exam_progress(self, async_client):
        """Returns exam with progress data."""
        with patch(
            "app.api.exams.exam_service.get_exam_progress",
            new_callable=AsyncMock,
            return_value={
                "exam_id": "exam-001",
                "title": "Midterm",
                "course_id": "course-001",
                "exam_date": "2026-04-15T09:00:00",
                "status": "active",
                "days_remaining": 14,
                "mastery_pct": 45.0,
                "target_mastery_pct": 80,
                "quiz_accuracy": 60.0,
                "quiz_total": 10,
                "quiz_correct": 6,
                "flashcard_total": 20,
                "flashcard_mastered": 9,
                "weak_weeks": [2, 3],
                "session_count": 5,
                "weeks_scope": [1, 2, 3],
            },
        ):
            response = await async_client.get("/api/exams/exam-001")

        assert response.status_code == 200
        data = response.json()
        assert data["days_remaining"] == 14
        assert data["mastery_pct"] == 45.0
        assert data["weak_weeks"] == [2, 3]

    async def test_returns_404_for_missing(self, async_client):
        """Returns 404 when exam not found."""
        with patch(
            "app.api.exams.exam_service.get_exam_progress",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get("/api/exams/nonexistent")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestDeleteExam:
    """Tests for DELETE /api/exams/{exam_id}."""

    async def test_archives_exam(self, async_client):
        """Returns 204 on successful archive."""
        with patch(
            "app.api.exams.exam_service.delete_exam",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await async_client.delete("/api/exams/exam-001")

        assert response.status_code == 204

    async def test_returns_404_for_missing(self, async_client):
        """Returns 404 when exam not found."""
        with patch(
            "app.api.exams.exam_service.delete_exam",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = await async_client.delete("/api/exams/nonexistent")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestGetSchedule:
    """Tests for GET /api/exams/{exam_id}/schedule."""

    async def test_returns_schedule(self, async_client):
        """Returns 7-day schedule."""
        with patch(
            "app.api.exams.schedule_service.generate_study_schedule",
            new_callable=AsyncMock,
            return_value=[
                {
                    "date": "2026-03-03",
                    "days_until_exam": 10,
                    "priority": "medium",
                    "card_target": 15,
                    "quiz_target": 6,
                    "focus_weeks": [2],
                }
            ],
        ):
            response = await async_client.get("/api/exams/exam-001/schedule")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["priority"] == "medium"
        assert data[0]["card_target"] == 15

    async def test_returns_404_for_missing(self, async_client):
        """Returns 404 when exam not found."""
        with patch(
            "app.api.exams.schedule_service.generate_study_schedule",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get("/api/exams/nonexistent/schedule")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestGetToday:
    """Tests for GET /api/exams/{exam_id}/today."""

    async def test_returns_todays_plan(self, async_client):
        """Returns today's plan."""
        with patch(
            "app.api.exams.schedule_service.get_daily_study_plan",
            new_callable=AsyncMock,
            return_value={
                "date": "2026-03-03",
                "days_until_exam": 5,
                "priority": "high",
                "card_target": 20,
                "quiz_target": 8,
                "focus_weeks": [1, 3],
            },
        ):
            response = await async_client.get("/api/exams/exam-001/today")

        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == "high"
        assert data["focus_weeks"] == [1, 3]


@pytest.mark.asyncio
class TestQuizAttempt:
    """Tests for POST /api/study/quiz-attempt."""

    async def test_records_attempt(self, async_client):
        """Records a quiz attempt."""
        mock_qq = MagicMock()
        mock_qq_result = MagicMock()
        mock_qq_result.scalar_one_or_none.return_value = mock_qq

        mock_attempt = MagicMock()
        mock_attempt.id = "qa-001"
        mock_attempt.quiz_question_id = "qq-001"
        mock_attempt.exam_id = None
        mock_attempt.selected_answer = "Option A"
        mock_attempt.is_correct = True
        mock_attempt.time_spent_ms = 5000
        mock_attempt.created_at = datetime(2026, 3, 1)

        from app.core.database import get_session
        from app.main import app

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_qq_result)
        mock_session.commit = AsyncMock()

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override

        with patch(
            "app.api.study.exam_service.record_quiz_attempt",
            new_callable=AsyncMock,
            return_value=mock_attempt,
        ):
            response = await async_client.post(
                "/api/study/quiz-attempt",
                json={
                    "quiz_question_id": "qq-001",
                    "selected_answer": "Option A",
                    "is_correct": True,
                    "time_spent_ms": 5000,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["is_correct"] is True

    async def test_404_for_missing_question(self, async_client):
        """Returns 404 when quiz question not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        from app.core.database import get_session
        from app.main import app

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override

        response = await async_client.post(
            "/api/study/quiz-attempt",
            json={
                "quiz_question_id": "nonexistent",
                "selected_answer": "A",
                "is_correct": False,
            },
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestGetStreak:
    """Tests for GET /api/study/streak."""

    async def test_returns_streak(self, async_client):
        """Returns streak data."""
        with patch(
            "app.api.study.streak_service.get_streak",
            new_callable=AsyncMock,
            return_value={
                "current_streak": 5,
                "longest_streak": 12,
                "last_study_date": "2026-03-03",
            },
        ):
            response = await async_client.get("/api/study/streak")

        assert response.status_code == 200
        data = response.json()
        assert data["current_streak"] == 5
        assert data["longest_streak"] == 12
