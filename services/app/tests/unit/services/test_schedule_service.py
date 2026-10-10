"""Tests for schedule service."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.schedule_service import (
    _get_priority,
    generate_study_schedule,
    get_daily_study_plan,
)


class TestGetPriority:
    """Tests for priority calculation."""

    def test_critical_within_3_days(self):
        label, mult = _get_priority(2)
        assert label == "critical"
        assert mult == 2.0

    def test_high_within_7_days(self):
        label, mult = _get_priority(5)
        assert label == "high"
        assert mult == 1.5

    def test_medium_within_14_days(self):
        label, mult = _get_priority(10)
        assert label == "medium"
        assert mult == 1.2

    def test_low_beyond_14_days(self):
        label, mult = _get_priority(20)
        assert label == "low"
        assert mult == 1.0

    def test_zero_days_is_critical(self):
        label, mult = _get_priority(0)
        assert label == "critical"
        assert mult == 2.0


class TestGenerateStudySchedule:
    """Tests for generate_study_schedule."""

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_exam(self):
        """Returns None when exam doesn't exist."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await generate_study_schedule(session, "nonexistent", user_id="user-1")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.schedule_service.get_weak_topics", new_callable=AsyncMock)
    async def test_generates_7_day_schedule(self, mock_weak):
        """Generates a 7-day schedule by default."""
        mock_weak.return_value = [{"week": 2, "weakness_score": 50}]

        session = AsyncMock()
        mock_exam = MagicMock()
        mock_exam.id = "exam-001"
        mock_exam.course_id = "course-001"
        mock_exam.exam_date = datetime.now(UTC) + timedelta(days=10)
        mock_exam.weeks_scope = [1, 2, 3, 4]

        mock_exam_result = MagicMock()
        mock_exam_result.scalar_one_or_none.return_value = mock_exam

        mock_due_result = MagicMock()
        mock_due_result.scalar.return_value = 50

        session.execute = AsyncMock(side_effect=[mock_exam_result, mock_due_result])

        schedule = await generate_study_schedule(session, "exam-001", user_id="user-1")

        assert schedule is not None
        assert len(schedule) == 7
        for day in schedule:
            assert "date" in day
            assert "priority" in day
            assert "card_target" in day
            assert "quiz_target" in day
            assert "focus_weeks" in day
            assert day["card_target"] > 0
            assert day["quiz_target"] > 0

    @pytest.mark.asyncio
    @patch("app.services.schedule_service.get_weak_topics", new_callable=AsyncMock)
    async def test_higher_targets_near_exam(self, mock_weak):
        """Card/quiz targets increase as exam approaches."""
        mock_weak.return_value = []

        session = AsyncMock()
        mock_exam = MagicMock()
        mock_exam.id = "exam-001"
        mock_exam.course_id = "course-001"
        mock_exam.exam_date = datetime.now(UTC) + timedelta(days=2)
        mock_exam.weeks_scope = [1, 2]

        mock_exam_result = MagicMock()
        mock_exam_result.scalar_one_or_none.return_value = mock_exam

        mock_due_result = MagicMock()
        mock_due_result.scalar.return_value = 20

        session.execute = AsyncMock(side_effect=[mock_exam_result, mock_due_result])

        schedule = await generate_study_schedule(
            session, "exam-001", days_ahead=1, user_id="user-1"
        )

        assert schedule is not None
        assert schedule[0]["priority"] in ("critical", "high")


class TestGetDailyStudyPlan:
    """Tests for get_daily_study_plan."""

    @pytest.mark.asyncio
    @patch("app.services.schedule_service.generate_study_schedule", new_callable=AsyncMock)
    async def test_returns_todays_plan(self, mock_gen):
        """Returns only today's plan."""
        mock_gen.return_value = [{"date": date.today().isoformat(), "priority": "medium"}]

        result = await get_daily_study_plan(AsyncMock(), "exam-001", user_id="user-1")

        assert result is not None
        assert result["date"] == date.today().isoformat()

    @pytest.mark.asyncio
    @patch("app.services.schedule_service.generate_study_schedule", new_callable=AsyncMock)
    async def test_returns_none_when_no_exam(self, mock_gen):
        """Returns None when exam doesn't exist."""
        mock_gen.return_value = None

        result = await get_daily_study_plan(AsyncMock(), "nonexistent", user_id="user-1")
        assert result is None


class TestScheduleUsesUtcDates:
    """The schedule must compare UTC dates with the UTC exam_date."""

    @pytest.mark.asyncio
    @patch("app.services.schedule_service.get_weak_topics", new_callable=AsyncMock)
    async def test_days_until_exam_uses_utc_today_not_host_local(self, mock_weak):
        mock_weak.return_value = []
        fixed_now = datetime(2026, 3, 10, 2, 0, tzinfo=UTC)  # UTC date: Mar 10

        session = AsyncMock()
        exam = MagicMock()
        exam.course_id = "c"
        exam.exam_date = datetime(2026, 3, 20, 9, 0, tzinfo=UTC)
        exam.weeks_scope = [1, 2]
        exam_result = MagicMock()
        exam_result.scalar_one_or_none.return_value = exam
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        session.execute = AsyncMock(side_effect=[exam_result, count_result])

        with patch("app.core.clock.utc_now", return_value=fixed_now):
            result = await generate_study_schedule(session, "e", user_id="u", days_ahead=2)

        assert result is not None
        assert result[0]["date"] == "2026-03-10"
        assert result[0]["days_until_exam"] == 10
