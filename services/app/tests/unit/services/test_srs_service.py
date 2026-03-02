"""Tests for the SM-2 spaced repetition service."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.srs_service import (
    SM2Result,
    StudyStats,
    calculate_sm2,
    get_due_cards,
    get_global_study_stats,
    get_per_course_due_counts,
    get_study_stats,
    record_review,
)


class TestCalculateSM2:
    """Tests for the SM-2 algorithm."""

    def test_first_review_quality_5(self):
        """First review with perfect quality: interval=1, reps=1."""
        result = calculate_sm2(quality=5, ease_factor=2.5, interval_days=0, repetition_count=0)
        assert result.interval_days == 1
        assert result.repetition_count == 1
        assert result.ease_factor == 2.6

    def test_first_review_quality_3(self):
        """First review with quality 3: interval=1, reps=1."""
        result = calculate_sm2(quality=3, ease_factor=2.5, interval_days=0, repetition_count=0)
        assert result.interval_days == 1
        assert result.repetition_count == 1
        assert result.ease_factor == 2.36

    def test_second_review_quality_4(self):
        """Second review (reps=1→2): interval jumps to 6."""
        result = calculate_sm2(quality=4, ease_factor=2.5, interval_days=1, repetition_count=1)
        assert result.interval_days == 6
        assert result.repetition_count == 2
        assert result.ease_factor == 2.5

    def test_third_review_applies_ease(self):
        """Third review (reps=2→3): interval = round(6 * EF)."""
        result = calculate_sm2(quality=4, ease_factor=2.5, interval_days=6, repetition_count=2)
        assert result.interval_days == round(6 * 2.5)  # 15
        assert result.repetition_count == 3

    def test_perfect_streak_intervals(self):
        """Perfect streak produces increasing intervals."""
        ef = 2.5
        interval = 0
        reps = 0
        intervals = []

        for _ in range(5):
            result = calculate_sm2(quality=5, ease_factor=ef, interval_days=interval, repetition_count=reps)
            ef = result.ease_factor
            interval = result.interval_days
            reps = result.repetition_count
            intervals.append(interval)

        # 1, 6, 6*EF, ...
        assert intervals[0] == 1
        assert intervals[1] == 6
        assert all(intervals[i] >= intervals[i - 1] for i in range(1, len(intervals)))

    def test_failure_resets_interval_and_reps(self):
        """Quality < 3 resets interval to 1 and repetition to 0."""
        result = calculate_sm2(quality=2, ease_factor=2.5, interval_days=15, repetition_count=3)
        assert result.interval_days == 1
        assert result.repetition_count == 0

    def test_failure_quality_0(self):
        """Complete blackout (q=0) resets and lowers ease."""
        result = calculate_sm2(quality=0, ease_factor=2.5, interval_days=10, repetition_count=5)
        assert result.interval_days == 1
        assert result.repetition_count == 0
        assert result.ease_factor < 2.5

    def test_failure_quality_1(self):
        """Quality 1 resets interval."""
        result = calculate_sm2(quality=1, ease_factor=2.5, interval_days=10, repetition_count=3)
        assert result.interval_days == 1
        assert result.repetition_count == 0

    def test_min_ease_factor_enforced(self):
        """Ease factor never drops below 1.3."""
        ef = 1.3
        for _ in range(10):
            result = calculate_sm2(quality=0, ease_factor=ef, interval_days=1, repetition_count=0)
            ef = result.ease_factor
        assert ef >= 1.3

    def test_quality_clamped_to_0_5(self):
        """Quality values outside 0-5 are clamped."""
        result_low = calculate_sm2(quality=-1, ease_factor=2.5, interval_days=0, repetition_count=0)
        result_high = calculate_sm2(quality=10, ease_factor=2.5, interval_days=0, repetition_count=0)
        # -1 clamped to 0, 10 clamped to 5
        assert result_low.repetition_count == 0  # quality 0 → fail
        assert result_high.repetition_count == 1  # quality 5 → pass

    def test_all_quality_levels(self):
        """All quality levels 0-5 produce valid results."""
        for q in range(6):
            result = calculate_sm2(quality=q, ease_factor=2.5, interval_days=6, repetition_count=2)
            assert result.ease_factor >= 1.3
            assert result.interval_days >= 1
            assert result.repetition_count >= 0


class TestRecordReview:
    """Tests for record_review."""

    @pytest.mark.asyncio
    async def test_creates_new_review(self):
        """First review creates a new FlashcardReview record."""
        session = AsyncMock()
        # No existing review
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()

        review = await record_review(session, "fc-001", quality=4)

        session.add.assert_called_once()
        assert review.flashcard_id == "fc-001"
        assert review.interval_days == 1
        assert review.repetition_count == 1
        assert review.ease_factor == 2.5
        assert review.last_reviewed_at is not None

    @pytest.mark.asyncio
    async def test_updates_existing_review(self):
        """Subsequent review updates the existing record."""
        session = AsyncMock()

        existing = MagicMock()
        existing.ease_factor = 2.5
        existing.interval_days = 1
        existing.repetition_count = 1

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        review = await record_review(session, "fc-001", quality=4)

        assert review.interval_days == 6  # second review → 6 days
        assert review.repetition_count == 2
        assert review.last_reviewed_at is not None


class TestGetStudyStats:
    """Tests for get_study_stats."""

    @pytest.mark.asyncio
    async def test_returns_correct_bucket_counts(self):
        """Stats correctly bucket cards into new/learning/mastered."""
        session = AsyncMock()
        now = datetime.utcnow()

        # Total: 5 cards
        mock_total = MagicMock()
        mock_total.scalar.return_value = 5

        # Reviewed: 3 cards (1 mastered, 2 learning)
        mock_reviewed = MagicMock()
        mock_reviewed.all.return_value = [
            ("fc-1", 25, now - timedelta(days=1)),   # mastered, overdue
            ("fc-2", 6, now + timedelta(days=3)),     # learning, not due
            ("fc-3", 10, now - timedelta(hours=1)),   # learning, overdue
        ]

        session.execute = AsyncMock(side_effect=[mock_total, mock_reviewed])

        stats = await get_study_stats(session, course_code="TEST")

        assert stats.total == 5
        assert stats.new == 2       # 5 total - 3 reviewed
        assert stats.mastered == 1  # interval > 21
        assert stats.learning == 2  # interval 1-21
        assert stats.due_today == 4 # 2 new + 1 mastered overdue + 1 learning overdue
