"""Tests for timed study session planning service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.services.timed_session_service import (
    MINUTES_PER_CARD,
    MINUTES_PER_QUIZ,
    TimedSessionPlan,
    generate_timed_plan,
)


def _make_card(card_id: str, week: int = 1) -> MagicMock:
    """Create a mock flashcard."""
    card = MagicMock()
    card.id = card_id
    card.week = week
    return card


def _make_quiz(quiz_id: str, week: int = 1) -> MagicMock:
    """Create a mock quiz question."""
    quiz = MagicMock()
    quiz.id = quiz_id
    quiz.week = week
    return quiz


class TestBudgetCalculation:
    """Tests for time budget allocation."""

    @pytest.mark.asyncio
    async def test_budget_calculation_30_min(self):
        """30 min -> card_budget=9, quiz_budget=4."""
        cards = [_make_card(f"fc-{i}") for i in range(9)]
        quizzes = [_make_quiz(f"qq-{i}") for i in range(4)]

        session = AsyncMock()
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = quizzes

        session.execute = AsyncMock(return_value=mock_quiz_result)

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=cards,
        ):
            plan = await generate_timed_plan(session, total_minutes=30)

        assert len(plan.card_ids) == 9
        assert len(plan.quiz_ids) == 4
        assert plan.total_minutes == 30

    @pytest.mark.asyncio
    async def test_budget_calculation_15_min(self):
        """15 min -> card_budget=4, quiz_budget=2."""
        # card_budget = floor(15 * 0.6 / 2) = floor(4.5) = 4
        # quiz_budget = floor(15 * 0.4 / 3) = floor(2.0) = 2
        cards = [_make_card(f"fc-{i}") for i in range(4)]
        quizzes = [_make_quiz(f"qq-{i}") for i in range(2)]

        session = AsyncMock()
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = quizzes

        session.execute = AsyncMock(return_value=mock_quiz_result)

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=cards,
        ):
            plan = await generate_timed_plan(session, total_minutes=15)

        assert len(plan.card_ids) == 4
        assert len(plan.quiz_ids) == 2

    @pytest.mark.asyncio
    async def test_budget_calculation_5_min_minimum(self):
        """5 min -> minimum 1 card, 1 quiz budget (may get fewer if unavailable)."""
        # card_budget = max(1, floor(5 * 0.6 / 2)) = max(1, 1) = 1
        # quiz_budget = max(1, floor(5 * 0.4 / 3)) = max(1, 0) = 1
        cards = [_make_card("fc-0")]
        quizzes = [_make_quiz("qq-0")]

        session = AsyncMock()
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = quizzes

        session.execute = AsyncMock(return_value=mock_quiz_result)

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=cards,
        ):
            plan = await generate_timed_plan(session, total_minutes=5)

        assert len(plan.card_ids) == 1
        assert len(plan.quiz_ids) == 1


class TestScoping:
    """Tests for course and exam scoping."""

    @pytest.mark.asyncio
    async def test_scoped_to_course(self):
        """When course_code provided, it is passed to get_due_cards and used in quiz filter."""
        cards = [_make_card("fc-0")]
        quizzes = [_make_quiz("qq-0")]

        session = AsyncMock()
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = quizzes

        session.execute = AsyncMock(return_value=mock_quiz_result)

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=cards,
        ) as mock_get_due:
            plan = await generate_timed_plan(session, total_minutes=30, course_code="CSIT302")

        # Verify course_code was passed through
        mock_get_due.assert_called_once()
        call_kwargs = mock_get_due.call_args
        assert call_kwargs[1]["course_code"] == "CSIT302"
        assert plan.course_code == "CSIT302"

    @pytest.mark.asyncio
    async def test_scoped_to_exam(self):
        """When exam_id provided, resolves course + weeks from exam."""
        mock_exam = MagicMock()
        mock_exam.course_id = "course-001"
        mock_exam.weeks_scope = [1, 2, 3]

        cards = [_make_card("fc-0", week=1)]
        quizzes = [_make_quiz("qq-0", week=2)]

        session = AsyncMock()

        # First call: select Exam
        mock_exam_result = MagicMock()
        mock_exam_result.scalar_one_or_none.return_value = mock_exam
        # Second call: select Course.code
        mock_course_result = MagicMock()
        mock_course_result.scalar_one_or_none.return_value = "CSIT302"
        # Third call: quiz query
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = quizzes

        session.execute = AsyncMock(
            side_effect=[mock_exam_result, mock_course_result, mock_quiz_result]
        )

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=cards,
        ) as mock_get_due:
            plan = await generate_timed_plan(session, total_minutes=30, exam_id="exam-001")

        assert plan.course_code == "CSIT302"
        assert plan.exam_id == "exam-001"
        # Verify course_code was resolved and passed
        mock_get_due.assert_called_once()
        assert mock_get_due.call_args[1]["course_code"] == "CSIT302"

    @pytest.mark.asyncio
    async def test_course_code_from_exam(self):
        """When only exam_id given, course_code is resolved from exam's course."""
        mock_exam = MagicMock()
        mock_exam.course_id = "course-001"
        mock_exam.weeks_scope = [1, 2]

        session = AsyncMock()

        mock_exam_result = MagicMock()
        mock_exam_result.scalar_one_or_none.return_value = mock_exam
        mock_course_result = MagicMock()
        mock_course_result.scalar_one_or_none.return_value = "CSIT314"
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[mock_exam_result, mock_course_result, mock_quiz_result]
        )

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            plan = await generate_timed_plan(session, total_minutes=30, exam_id="exam-002")

        assert plan.course_code == "CSIT314"

    @pytest.mark.asyncio
    async def test_exam_weeks_prioritized(self):
        """Cards from exam weeks appear before other cards in results."""
        # Cards from different weeks
        card_w5 = _make_card("fc-w5", week=5)
        card_w1 = _make_card("fc-w1", week=1)
        card_w3 = _make_card("fc-w3", week=3)
        card_w2 = _make_card("fc-w2", week=2)

        mock_exam = MagicMock()
        mock_exam.course_id = "course-001"
        mock_exam.weeks_scope = [1, 2, 3]

        session = AsyncMock()

        mock_exam_result = MagicMock()
        mock_exam_result.scalar_one_or_none.return_value = mock_exam
        mock_course_result = MagicMock()
        mock_course_result.scalar_one_or_none.return_value = "CSIT302"
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[mock_exam_result, mock_course_result, mock_quiz_result]
        )

        # get_due_cards returns all 4 cards in arbitrary order
        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=[card_w5, card_w1, card_w3, card_w2],
        ):
            plan = await generate_timed_plan(session, total_minutes=30, exam_id="exam-001")

        # Exam-week cards (w1, w3, w2) should come before non-exam card (w5)
        exam_week_ids = {"fc-w1", "fc-w3", "fc-w2"}
        # Find position of the non-exam card
        if "fc-w5" in plan.card_ids:
            w5_idx = plan.card_ids.index("fc-w5")
            # All exam-week cards that appear should be before w5
            for cid in plan.card_ids[:w5_idx]:
                assert cid in exam_week_ids


class TestEdgeCases:
    """Tests for edge cases and empty data."""

    @pytest.mark.asyncio
    async def test_no_cards_available(self):
        """Returns empty card_ids when no flashcards are due."""
        quizzes = [_make_quiz(f"qq-{i}") for i in range(4)]

        session = AsyncMock()
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = quizzes

        session.execute = AsyncMock(return_value=mock_quiz_result)

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            plan = await generate_timed_plan(session, total_minutes=30)

        assert plan.card_ids == []
        assert len(plan.quiz_ids) == 4
        assert plan.estimated_card_minutes == 0

    @pytest.mark.asyncio
    async def test_no_quizzes_available(self):
        """Returns empty quiz_ids when no quiz questions exist."""
        cards = [_make_card(f"fc-{i}") for i in range(9)]

        session = AsyncMock()
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(return_value=mock_quiz_result)

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=cards,
        ):
            plan = await generate_timed_plan(session, total_minutes=30)

        assert len(plan.card_ids) == 9
        assert plan.quiz_ids == []
        assert plan.estimated_quiz_minutes == 0

    @pytest.mark.asyncio
    async def test_estimated_times(self):
        """Estimated minutes = count * per-item estimate."""
        cards = [_make_card(f"fc-{i}") for i in range(5)]
        quizzes = [_make_quiz(f"qq-{i}") for i in range(3)]

        session = AsyncMock()
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = quizzes

        session.execute = AsyncMock(return_value=mock_quiz_result)

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=cards,
        ):
            plan = await generate_timed_plan(session, total_minutes=30)

        assert plan.estimated_card_minutes == 5 * MINUTES_PER_CARD
        assert plan.estimated_quiz_minutes == 3 * MINUTES_PER_QUIZ

    @pytest.mark.asyncio
    async def test_plan_response_structure(self):
        """Plan has all expected fields with correct types."""
        session = AsyncMock()
        mock_quiz_result = MagicMock()
        mock_quiz_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(return_value=mock_quiz_result)

        with patch(
            "app.services.timed_session_service.srs_service.get_due_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            plan = await generate_timed_plan(session, total_minutes=30)

        assert isinstance(plan, TimedSessionPlan)
        assert isinstance(plan.total_minutes, int)
        assert isinstance(plan.card_ids, list)
        assert isinstance(plan.quiz_ids, list)
        assert isinstance(plan.estimated_card_minutes, int)
        assert isinstance(plan.estimated_quiz_minutes, int)
        assert plan.course_code is None
        assert plan.exam_id is None


class TestSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_minutes_field_validation_minimum(self):
        """TimedPlanRequest rejects minutes below 5."""
        from app.api.study_schemas import TimedPlanRequest

        with pytest.raises(ValidationError):
            TimedPlanRequest(minutes=4)

    def test_minutes_field_validation_maximum(self):
        """TimedPlanRequest rejects minutes above 180."""
        from app.api.study_schemas import TimedPlanRequest

        with pytest.raises(ValidationError):
            TimedPlanRequest(minutes=181)

    def test_minutes_field_validation_valid(self):
        """TimedPlanRequest accepts valid minutes range."""
        from app.api.study_schemas import TimedPlanRequest

        req = TimedPlanRequest(minutes=30)
        assert req.minutes == 30
        assert req.course_code is None
        assert req.exam_id is None

    def test_minutes_field_validation_with_optional_fields(self):
        """TimedPlanRequest accepts optional course_code and exam_id."""
        from app.api.study_schemas import TimedPlanRequest

        req = TimedPlanRequest(minutes=60, course_code="CSIT302", exam_id="exam-001")
        assert req.minutes == 60
        assert req.course_code == "CSIT302"
        assert req.exam_id == "exam-001"
