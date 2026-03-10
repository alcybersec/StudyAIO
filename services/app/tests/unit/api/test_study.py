"""Tests for the study API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.srs_service import StudyStats


@pytest.mark.asyncio
class TestGetDueCards:
    """Tests for GET /api/study/due."""

    async def test_returns_due_cards(self, async_client):
        """Returns flashcards due for review."""
        mock_card = MagicMock()
        mock_card.id = "fc-001"
        mock_card.course_id = "course-001"
        mock_card.week = 3
        mock_card.front = "What is TCP?"
        mock_card.back = "Transmission Control Protocol"
        mock_card.tags = ["networking"]
        mock_card.source_artifact_id = "art-001"
        mock_card.source_page_ref = 5
        mock_card.generation_version = 1
        mock_card.created_at = datetime(2024, 1, 1)

        with patch(
            "app.api.study.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=[mock_card],
        ):
            response = await async_client.get("/api/study/due?course_code=CSIT302&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "fc-001"
        assert data[0]["front"] == "What is TCP?"

    async def test_returns_empty_when_none_due(self, async_client):
        """Returns empty list when no cards due."""
        with patch(
            "app.api.study.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await async_client.get("/api/study/due")

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
class TestPostReview:
    """Tests for POST /api/study/review."""

    async def test_records_review_success(self, async_client):
        """Records a review and returns updated state."""
        mock_flashcard = MagicMock()
        mock_flashcard_result = MagicMock()
        mock_flashcard_result.scalar_one_or_none.return_value = mock_flashcard

        mock_review = MagicMock()
        mock_review.id = "rev-001"
        mock_review.flashcard_id = "fc-001"
        mock_review.ease_factor = 2.5
        mock_review.interval_days = 1
        mock_review.repetition_count = 1
        mock_review.next_review_at = datetime(2024, 1, 2)
        mock_review.last_reviewed_at = datetime(2024, 1, 1)

        with (
            patch(
                "app.api.study.srs_service.record_review",
                new_callable=AsyncMock,
                return_value=mock_review,
            ),
            patch(
                "app.api.study.select",
            ),
        ):
            # Mock the flashcard existence check
            async_client._transport.app.dependency_overrides  # noqa: B018
            from app.core.database import get_session
            from app.main import app

            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value=mock_flashcard_result)
            mock_session.commit = AsyncMock()

            async def override():
                yield mock_session

            app.dependency_overrides[get_session] = override
            response = await async_client.post(
                "/api/study/review",
                json={"flashcard_id": "fc-001", "quality": 4},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["flashcard_id"] == "fc-001"
        assert data["interval_days"] == 1

    async def test_review_404_for_missing_flashcard(self, async_client):
        """Returns 404 when flashcard doesn't exist."""
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
            "/api/study/review",
            json={"flashcard_id": "nonexistent", "quality": 3},
        )

        assert response.status_code == 404

    async def test_review_validation_error(self, async_client):
        """Returns 422 when quality is out of range."""
        response = await async_client.post(
            "/api/study/review",
            json={"flashcard_id": "fc-001", "quality": 10},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestGetStats:
    """Tests for GET /api/study/stats."""

    async def test_returns_stats(self, async_client):
        """Returns study statistics."""
        with patch(
            "app.api.study.srs_service.get_study_stats",
            new_callable=AsyncMock,
            return_value=StudyStats(total=20, due_today=5, mastered=8, learning=7, new=5),
        ):
            response = await async_client.get("/api/study/stats?course_code=CSIT302")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 20
        assert data["due_today"] == 5
        assert data["mastered"] == 8
        assert data["learning"] == 7
        assert data["new"] == 5

    async def test_stats_no_filter(self, async_client):
        """Stats work without course/week filters (global stats)."""
        with patch(
            "app.api.study.srs_service.get_study_stats",
            new_callable=AsyncMock,
            return_value=StudyStats(total=0, due_today=0, mastered=0, learning=0, new=0),
        ):
            response = await async_client.get("/api/study/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
