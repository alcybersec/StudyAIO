"""Tests for the assets API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_flashcard():
    """Mock Flashcard ORM object."""
    fc = MagicMock()
    fc.id = "fc-001"
    fc.course_id = "course-001"
    fc.week = 5
    fc.front = "What is a firewall?"
    fc.back = "A network security system."
    fc.tags = ["firewalls"]
    fc.source_artifact_id = "art-001"
    fc.source_page_ref = 1
    fc.generation_version = 1
    fc.created_at = datetime(2025, 1, 1)
    return fc


@pytest.fixture
def mock_quiz_question():
    """Mock QuizQuestion ORM object."""
    q = MagicMock()
    q.id = "quiz-001"
    q.course_id = "course-001"
    q.week = 5
    q.question_type = "multiple_choice"
    q.question = "What is a firewall?"
    q.options_json = ["A. Router", "B. Security system", "C. Switch", "D. Hub"]
    q.correct_answer = "B"
    q.explanation = "Firewalls filter traffic."
    q.source_artifact_id = "art-001"
    q.source_page_ref = 1
    q.generation_version = 1
    q.created_at = datetime(2025, 1, 1)
    return q


@pytest.mark.asyncio
class TestGetFlashcards:
    """Tests for GET /api/assets/flashcards."""

    async def test_get_flashcards_with_week(self, async_client, mock_session, mock_flashcard):
        """Returns flashcards filtered by course and week."""
        with patch(
            "app.api.assets.asset_service.get_flashcards_for_week",
            new_callable=AsyncMock,
            return_value=[mock_flashcard],
        ):
            response = await async_client.get("/api/assets/flashcards?course_code=CSIT302&week=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["front"] == "What is a firewall?"
        assert data[0]["tags"] == ["firewalls"]

    async def test_get_flashcards_without_week(self, async_client, mock_session, mock_flashcard):
        """Returns all flashcards for a course when week is omitted."""
        with patch(
            "app.api.assets.asset_service.get_flashcards_for_course",
            new_callable=AsyncMock,
            return_value=[mock_flashcard],
        ):
            response = await async_client.get("/api/assets/flashcards?course_code=CSIT302")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_get_flashcards_empty_result(self, async_client, mock_session):
        """Returns empty list when no flashcards exist."""
        with patch(
            "app.api.assets.asset_service.get_flashcards_for_week",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get("/api/assets/flashcards?course_code=CSIT302&week=99")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_flashcards_missing_course_returns_422(self, async_client, mock_session):
        """Missing course_code returns validation error."""
        response = await async_client.get("/api/assets/flashcards")
        assert response.status_code == 422


@pytest.mark.asyncio
class TestGetQuizQuestions:
    """Tests for GET /api/assets/quiz."""

    async def test_get_quiz_with_week(self, async_client, mock_session, mock_quiz_question):
        """Returns quiz questions filtered by course and week."""
        with patch(
            "app.api.assets.asset_service.get_quiz_questions_for_week",
            new_callable=AsyncMock,
            return_value=[mock_quiz_question],
        ):
            response = await async_client.get("/api/assets/quiz?course_code=CSIT302&week=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["question_type"] == "multiple_choice"
        assert data[0]["correct_answer"] == "B"

    async def test_get_quiz_without_week(self, async_client, mock_session, mock_quiz_question):
        """Returns all quiz questions for a course when week is omitted."""
        with patch(
            "app.api.assets.asset_service.get_quiz_questions_for_course",
            new_callable=AsyncMock,
            return_value=[mock_quiz_question],
        ):
            response = await async_client.get("/api/assets/quiz?course_code=CSIT302")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_get_quiz_empty_result(self, async_client, mock_session):
        """Returns empty list when no quiz questions exist."""
        with patch(
            "app.api.assets.asset_service.get_quiz_questions_for_week",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get("/api/assets/quiz?course_code=CSIT302&week=99")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_quiz_missing_course_returns_422(self, async_client, mock_session):
        """Missing course_code returns validation error."""
        response = await async_client.get("/api/assets/quiz")
        assert response.status_code == 422
