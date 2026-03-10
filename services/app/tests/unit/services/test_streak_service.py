"""Tests for streak service."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.streak_service import (
    get_streak,
    get_study_history,
    record_study_session,
)


class TestRecordStudySession:
    """Tests for record_study_session."""

    @pytest.mark.asyncio
    async def test_creates_new_session(self):
        """Creates a new session when none exists for today."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()

        study = await record_study_session(
            session,
            course_id="course-001",
            cards_reviewed=10,
            quiz_questions_answered=5,
            quiz_correct=4,
            duration_seconds=600,
        )

        session.add.assert_called_once()
        assert study.cards_reviewed == 10
        assert study.quiz_questions_answered == 5
        assert study.quiz_correct == 4
        assert study.duration_seconds == 600

    @pytest.mark.asyncio
    async def test_upserts_existing_session(self):
        """Adds to existing session totals for today."""
        session = AsyncMock()
        existing = MagicMock()
        existing.id = "ss-001"
        existing.cards_reviewed = 5
        existing.quiz_questions_answered = 3
        existing.quiz_correct = 2
        existing.duration_seconds = 300

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        result = await record_study_session(
            session,
            course_id="course-001",
            cards_reviewed=10,
            quiz_questions_answered=5,
            quiz_correct=4,
            duration_seconds=600,
        )

        assert result.cards_reviewed == 15  # 5 + 10
        assert result.quiz_questions_answered == 8  # 3 + 5
        assert result.quiz_correct == 6  # 2 + 4
        assert result.duration_seconds == 900  # 300 + 600


class TestGetStreak:
    """Tests for get_streak."""

    @pytest.mark.asyncio
    async def test_no_sessions_returns_zero(self):
        """Returns zeros when no sessions exist."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_streak(session)
        assert result["current_streak"] == 0
        assert result["longest_streak"] == 0
        assert result["last_study_date"] is None

    @pytest.mark.asyncio
    async def test_consecutive_days_streak(self):
        """Counts consecutive study days correctly."""
        session = AsyncMock()
        today = date.today()

        dates = [
            (today,),
            (today - timedelta(days=1),),
            (today - timedelta(days=2),),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = dates
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_streak(session)
        assert result["current_streak"] == 3
        assert result["longest_streak"] == 3

    @pytest.mark.asyncio
    async def test_gap_breaks_current_streak(self):
        """A gap in dates breaks the current streak."""
        session = AsyncMock()
        today = date.today()

        dates = [
            (today,),
            (today - timedelta(days=2),),  # gap!
            (today - timedelta(days=3),),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = dates
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_streak(session)
        assert result["current_streak"] == 1  # only today
        assert result["longest_streak"] == 2  # the 2-day block

    @pytest.mark.asyncio
    async def test_yesterday_counts_as_active_streak(self):
        """If last study was yesterday and no study today, streak is still alive."""
        session = AsyncMock()
        today = date.today()

        dates = [
            (today - timedelta(days=1),),
            (today - timedelta(days=2),),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = dates
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_streak(session)
        assert result["current_streak"] == 2

    @pytest.mark.asyncio
    async def test_single_day_streak(self):
        """Single study day = streak of 1."""
        session = AsyncMock()
        today = date.today()

        dates = [(today,)]
        mock_result = MagicMock()
        mock_result.all.return_value = dates
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_streak(session)
        assert result["current_streak"] == 1
        assert result["longest_streak"] == 1


class TestGetStudyHistory:
    """Tests for get_study_history."""

    @pytest.mark.asyncio
    async def test_returns_aggregated_history(self):
        """Returns daily aggregates."""
        session = AsyncMock()
        today = date.today()

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(
            return_value=iter(
                [
                    MagicMock(
                        session_date=today,
                        cards_reviewed=20,
                        quiz_answered=10,
                        quiz_correct=8,
                        duration_seconds=1200,
                        session_count=2,
                    ),
                ]
            )
        )
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_study_history(session, days=7)
        assert len(result) == 1
        assert result[0]["date"] == today.isoformat()
        assert result[0]["cards_reviewed"] == 20

    @pytest.mark.asyncio
    async def test_empty_history(self):
        """Returns empty list when no sessions exist."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_study_history(session, days=30)
        assert result == []
