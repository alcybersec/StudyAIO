"""Tests for readiness_service — shared weak-topic scoring and readiness detail."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import readiness_service


class TestScoreWeek:
    """Tests for the shared week-scoring helper (extracted weak-topic math)."""

    def test_low_quiz_accuracy_scores(self):
        """Accuracy 50% → 20 points of weakness (70 - 50), pinned to old math."""
        reasons, score = readiness_service.score_week(quiz_accuracy=50.0, avg_ease=None)
        assert reasons == ["low_quiz_accuracy"]
        assert score == 20.0

    def test_low_ease_scores(self):
        """Ease 1.5 → 25 points ((2.0 - 1.5) * 50), pinned to old math."""
        reasons, score = readiness_service.score_week(quiz_accuracy=None, avg_ease=1.5)
        assert reasons == ["low_flashcard_ease"]
        assert score == 25.0

    def test_unstudied_scores_100(self):
        """No data at all → unstudied with weakness 100."""
        reasons, score = readiness_service.score_week(quiz_accuracy=None, avg_ease=None)
        assert reasons == ["unstudied"]
        assert score == 100.0

    def test_strong_week_scores_zero(self):
        """Good accuracy and ease → no reasons, zero weakness."""
        reasons, score = readiness_service.score_week(quiz_accuracy=85.0, avg_ease=2.5)
        assert reasons == []
        assert score == 0.0

    def test_combined_weakness_adds_up(self):
        """Both weak signals sum (regression pin: 60% quiz + 1.8 ease = 20.0)."""
        reasons, score = readiness_service.score_week(quiz_accuracy=60.0, avg_ease=1.8)
        assert set(reasons) == {"low_quiz_accuracy", "low_flashcard_ease"}
        assert score == pytest.approx(10.0 + 10.0)


@pytest.mark.asyncio
class TestComputeReadinessDetail:
    """Tests for compute_readiness_detail."""

    def _quiz_stats_result(self, rows):
        result = MagicMock()
        result.__iter__ = MagicMock(return_value=iter(rows))
        return result

    async def test_returns_none_for_unknown_exam(self, mock_session):
        """Foreign/unknown exam → None (tenant isolation at service level)."""
        with patch(
            "app.services.exam_service.get_exam",
            new_callable=AsyncMock,
            return_value=None,
        ):
            detail = await readiness_service.compute_readiness_detail(
                mock_session, "exam-x", "user-001"
            )
        assert detail is None

    async def test_detail_matches_weak_topic_math(self, mock_session):
        """Topic rows carry exact accuracy/weight numbers from the shared math."""
        exam = MagicMock()
        exam.id = "exam-001"
        exam.title = "Midterm"
        exam.course_id = "course-001"
        exam.weeks_scope = [1, 2]

        # Week 1: 5 attempts, 2 correct → 40% accuracy → weakness 30
        quiz_row = MagicMock()
        quiz_row.week = 1
        quiz_row.attempts = 5
        quiz_row.correct = 2

        # Week 1: avg ease 2.5 (fine). Week 2: no data → unstudied.
        ease_row = MagicMock()
        ease_row.week = 1
        ease_row.avg_ease = 2.5

        # Card counts: week 1 → 12 cards
        card_row = MagicMock()
        card_row.week = 1
        card_row.card_count = 12

        # Titles: week 1 → "Network Security"
        title_row = MagicMock()
        title_row.week = 1
        title_row.title = "Network Security"

        mock_session.execute = AsyncMock(
            side_effect=[
                self._quiz_stats_result([quiz_row]),
                self._quiz_stats_result([ease_row]),
                self._quiz_stats_result([card_row]),
                self._quiz_stats_result([title_row]),
            ]
        )

        with (
            patch(
                "app.services.exam_service.get_exam",
                new_callable=AsyncMock,
                return_value=exam,
            ),
            patch(
                "app.services.analytics_service.get_exam_readiness",
                new_callable=AsyncMock,
                return_value={"readiness_score": 62.4},
            ),
        ):
            detail = await readiness_service.compute_readiness_detail(
                mock_session, "exam-001", "user-001"
            )

        assert detail is not None
        assert detail["overall"] == 62

        topics = {t["week"]: t for t in detail["topics"]}
        assert set(topics.keys()) == {1, 2}

        week1 = topics[1]
        assert week1["topic"] == "Network Security"
        assert week1["accuracy"] == 40.0
        assert week1["weight"] == 30.0  # 70 - 40, old weak-topic math
        assert week1["card_count"] == 12

        week2 = topics[2]
        assert week2["topic"] == "Week 2"
        assert week2["accuracy"] is None
        assert week2["weight"] == 100.0  # unstudied
        assert week2["card_count"] == 0


@pytest.mark.asyncio
class TestWeakTopicsRegression:
    """exam_service.get_weak_topics keeps its old outputs via the shared helper."""

    async def test_get_weak_topics_pins_old_numbers(self, mock_session):
        """Week with 40% accuracy → weakness_score 30.0, same as before extraction."""
        from app.services import exam_service

        quiz_row = MagicMock()
        quiz_row.week = 3
        quiz_row.attempts = 10
        quiz_row.correct = 4

        quiz_result = MagicMock()
        quiz_result.__iter__ = MagicMock(return_value=iter([quiz_row]))
        ease_result = MagicMock()
        ease_result.__iter__ = MagicMock(return_value=iter([]))

        mock_session.execute = AsyncMock(side_effect=[quiz_result, ease_result])

        weak = await exam_service.get_weak_topics(mock_session, "course-001", [3])
        assert len(weak) == 1
        assert weak[0]["week"] == 3
        assert weak[0]["quiz_accuracy"] == 40.0
        assert weak[0]["reasons"] == ["low_quiz_accuracy"]
        assert weak[0]["weakness_score"] == 30.0
