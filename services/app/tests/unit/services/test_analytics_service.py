"""Tests for analytics service."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.analytics_service import (
    compute_and_store_snapshot,
    get_exam_readiness,
    get_mastery_breakdown,
    get_overview,
    get_retention_data,
    get_study_heatmap,
)


class TestGetOverview:
    """Tests for get_overview."""

    @pytest.mark.asyncio
    async def test_get_overview_with_data(self):
        """Returns correct aggregated stats when data exists."""
        session = AsyncMock()

        # StudySession aggregates: 7200 seconds, 50 cards, 10 sessions
        mock_time_result = MagicMock()
        mock_time_result.one.return_value = (7200, 50, 10)

        # Total flashcards: 20
        mock_fc_result = MagicMock()
        mock_fc_result.scalar.return_value = 20

        # Mastered flashcards (interval > 21): 5
        mock_mastered_result = MagicMock()
        mock_mastered_result.scalar.return_value = 5

        # Active courses: 3
        mock_courses_result = MagicMock()
        mock_courses_result.scalar.return_value = 3

        session.execute = AsyncMock(
            side_effect=[
                mock_time_result,
                mock_fc_result,
                mock_mastered_result,
                mock_courses_result,
            ]
        )

        result = await get_overview(session, "user-001")

        assert result["total_study_hours"] == 2.0
        assert result["total_cards_reviewed"] == 50
        assert result["total_sessions"] == 10
        assert result["mastery_pct"] == 25.0
        assert result["total_flashcards"] == 20
        assert result["mastered_flashcards"] == 5
        assert result["active_courses"] == 3

    @pytest.mark.asyncio
    async def test_get_overview_empty(self):
        """Returns zeroed stats when no data exists."""
        session = AsyncMock()

        mock_time_result = MagicMock()
        mock_time_result.one.return_value = (0, 0, 0)

        mock_fc_result = MagicMock()
        mock_fc_result.scalar.return_value = 0

        mock_mastered_result = MagicMock()
        mock_mastered_result.scalar.return_value = 0

        mock_courses_result = MagicMock()
        mock_courses_result.scalar.return_value = 0

        session.execute = AsyncMock(
            side_effect=[
                mock_time_result,
                mock_fc_result,
                mock_mastered_result,
                mock_courses_result,
            ]
        )

        result = await get_overview(session, "user-001")

        assert result["total_study_hours"] == 0.0
        assert result["total_cards_reviewed"] == 0
        assert result["total_sessions"] == 0
        assert result["mastery_pct"] == 0.0
        assert result["total_flashcards"] == 0
        assert result["mastered_flashcards"] == 0
        assert result["active_courses"] == 0


class TestGetStudyHeatmap:
    """Tests for get_study_heatmap."""

    @pytest.mark.asyncio
    async def test_fills_gaps(self):
        """Returns all days in range, filling zero-activity days."""
        session = AsyncMock()

        today = date.today()
        yesterday = today - timedelta(days=1)

        # Only one day with data
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.session_date = yesterday
        mock_row.total_seconds = 3600
        mock_row.total_cards = 20
        mock_row.session_count = 2
        mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))

        session.execute = AsyncMock(return_value=mock_result)

        result = await get_study_heatmap(session, "user-001", days=7)

        # Should have 8 entries (7 days ago through today inclusive)
        assert len(result) == 8

        # Find the data day
        data_day = next(d for d in result if d["date"] == yesterday.isoformat())
        assert data_day["minutes"] == 60.0
        assert data_day["cards"] == 20
        assert data_day["sessions"] == 2

        # Zero days should have zero values
        zero_days = [d for d in result if d["date"] != yesterday.isoformat()]
        for d in zero_days:
            assert d["minutes"] == 0
            assert d["cards"] == 0
            assert d["sessions"] == 0

    @pytest.mark.asyncio
    async def test_empty(self):
        """Returns all-zero heatmap when no sessions exist."""
        session = AsyncMock()

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_study_heatmap(session, "user-001", days=7)

        assert len(result) == 8  # 7 days ago through today
        for d in result:
            assert d["minutes"] == 0
            assert d["cards"] == 0
            assert d["sessions"] == 0


class TestGetRetentionData:
    """Tests for get_retention_data."""

    @pytest.mark.asyncio
    async def test_with_reviews(self):
        """Calculates retention percentages for interval buckets."""
        session = AsyncMock()

        # Simulate reviews: 3 reviews at interval=5 (bucket 7),
        # 2 retained (ease>=2.0), 1 not
        mock_result = MagicMock()
        rows = [
            (5, 2.5, "CSIT302"),   # retained, bucket 7
            (5, 2.1, "CSIT302"),   # retained, bucket 7
            (5, 1.5, "CSIT302"),   # not retained, bucket 7
            (25, 2.0, "CSIT302"),  # retained, bucket 30
        ]
        mock_result.all.return_value = rows
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_retention_data(session, "user-001")

        assert len(result) == 2

        bucket_7 = next(r for r in result if r["interval_bucket"] == 7)
        assert bucket_7["card_count"] == 3
        assert bucket_7["retention_pct"] == pytest.approx(66.7, abs=0.1)

        bucket_30 = next(r for r in result if r["interval_bucket"] == 30)
        assert bucket_30["card_count"] == 1
        assert bucket_30["retention_pct"] == 100.0

    @pytest.mark.asyncio
    async def test_empty(self):
        """Returns empty list when no reviews exist."""
        session = AsyncMock()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_retention_data(session, "user-001")

        assert result == []


class TestGetMasteryBreakdown:
    """Tests for get_mastery_breakdown."""

    @pytest.mark.asyncio
    async def test_with_data(self):
        """Returns mastery breakdown per week."""
        session = AsyncMock()

        # Mock query result: 1 week with 10 total, 3 mastered, 4 learning
        mock_row = MagicMock()
        mock_row.code = "CSIT302"
        mock_row.week = 1
        mock_row.total = 10
        mock_row.mastered = 3
        mock_row.learning = 4

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_mastery_breakdown(session, "user-001")

        assert len(result) == 1
        week1 = result[0]
        assert week1["course_code"] == "CSIT302"
        assert week1["week"] == 1
        assert week1["total"] == 10
        assert week1["mastered"] == 3
        assert week1["learning"] == 4
        assert week1["new"] == 3
        assert week1["mastery_pct"] == 30.0

    @pytest.mark.asyncio
    async def test_by_course(self):
        """Filters by course_code when provided."""
        session = AsyncMock()

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_mastery_breakdown(
            session, "user-001", course_code="CSIT302"
        )

        assert result == []
        # Verify execute was called (query was built with filter)
        session.execute.assert_called_once()


class TestGetExamReadiness:
    """Tests for get_exam_readiness."""

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_exam(self):
        """Returns None when exam not found."""
        session = AsyncMock()

        with patch(
            "app.services.exam_service.get_exam",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await get_exam_readiness(session, "nonexistent", "user-001")

        assert result is None

    @pytest.mark.asyncio
    async def test_calculates_weighted_score(self):
        """Calculates readiness as 40% mastery + 30% quiz + 30% consistency."""
        session = AsyncMock()

        mock_exam = MagicMock()
        mock_exam.id = "exam-001"
        mock_exam.title = "Midterm"
        mock_exam.course_id = "course-001"
        mock_exam.weeks_scope = [1, 2, 3]

        mock_progress = {
            "mastery_pct": 60.0,
            "quiz_accuracy": 80.0,
            "days_remaining": 10,
            "flashcard_total": 30,
            "flashcard_mastered": 18,
            "quiz_total": 15,
            "quiz_correct": 12,
        }

        # Consistency: 5 study days in last 7
        mock_consistency_result = MagicMock()
        mock_consistency_result.scalar.return_value = 5

        session.execute = AsyncMock(return_value=mock_consistency_result)

        with (
            patch(
                "app.services.exam_service.get_exam",
                new_callable=AsyncMock,
                return_value=mock_exam,
            ),
            patch(
                "app.services.exam_service.get_exam_progress",
                new_callable=AsyncMock,
                return_value=mock_progress,
            ),
            patch(
                "app.services.exam_service.get_weak_topics",
                new_callable=AsyncMock,
                return_value=[{"week": 2}, {"week": 3}],
            ),
        ):
            result = await get_exam_readiness(session, "exam-001", "user-001")

        assert result is not None
        assert result["exam_id"] == "exam-001"
        assert result["title"] == "Midterm"

        # mastery: 60 * 0.4 = 24
        # quiz: 80 * 0.3 = 24
        # consistency: (5/7 * 100) * 0.3 = 71.4 * 0.3 = 21.43
        expected = round(60.0 * 0.4 + 80.0 * 0.3 + min(100, round(5 / 7 * 100, 1)) * 0.3, 1)
        assert result["readiness_score"] == expected
        assert result["mastery_score"] == 60.0
        assert result["quiz_score"] == 80.0
        assert result["weak_weeks"] == [2, 3]
        assert result["flashcard_total"] == 30
        assert result["study_days_last_week"] == 5


class TestComputeAndStoreSnapshot:
    """Tests for compute_and_store_snapshot."""

    @pytest.mark.asyncio
    async def test_creates_new(self):
        """Creates a new snapshot when none exists for today."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        # No existing snapshot
        mock_existing = MagicMock()
        mock_existing.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_existing)

        mock_overview = {
            "total_study_hours": 5.0,
            "total_cards_reviewed": 100,
            "total_sessions": 20,
            "mastery_pct": 50.0,
            "total_flashcards": 40,
            "mastered_flashcards": 20,
            "active_courses": 2,
        }

        with patch(
            "app.services.analytics_service.get_overview",
            new_callable=AsyncMock,
            return_value=mock_overview,
        ):
            result = await compute_and_store_snapshot(session, "user-001")

        session.add.assert_called_once()
        assert result.user_id == "user-001"
        assert result.snapshot_date == date.today()
        assert result.metrics_json == mock_overview

    @pytest.mark.asyncio
    async def test_updates_existing(self):
        """Updates existing snapshot if one exists for today."""
        session = AsyncMock()
        session.flush = AsyncMock()

        existing_snapshot = MagicMock()
        existing_snapshot.user_id = "user-001"
        existing_snapshot.snapshot_date = date.today()
        existing_snapshot.metrics_json = {"old": "data"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_snapshot
        session.execute = AsyncMock(return_value=mock_result)

        mock_overview = {
            "total_study_hours": 6.0,
            "total_cards_reviewed": 120,
            "total_sessions": 22,
            "mastery_pct": 55.0,
            "total_flashcards": 40,
            "mastered_flashcards": 22,
            "active_courses": 2,
        }

        with patch(
            "app.services.analytics_service.get_overview",
            new_callable=AsyncMock,
            return_value=mock_overview,
        ):
            result = await compute_and_store_snapshot(session, "user-001")

        # Should NOT call session.add (updating, not creating)
        session.add.assert_not_called()
        assert result.metrics_json == mock_overview
        assert result is existing_snapshot
