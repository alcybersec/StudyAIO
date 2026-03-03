"""Tests for exam service."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.exam_service import (
    create_exam,
    delete_exam,
    get_exam,
    get_exam_progress,
    get_weak_topics,
    list_exams,
    record_quiz_attempt,
    update_exam,
)


class TestCreateExam:
    """Tests for create_exam."""

    @pytest.mark.asyncio
    async def test_creates_exam_successfully(self):
        """Creates an exam when course exists and date is future."""
        session = AsyncMock()
        mock_course = MagicMock()
        mock_course.id = "course-001"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_course
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()

        exam = await create_exam(
            session,
            course_code="CSIT302",
            title="Midterm",
            exam_date=datetime.utcnow() + timedelta(days=14),
            weeks_scope=[1, 2, 3, 4],
        )

        session.add.assert_called_once()
        assert exam.course_id == "course-001"
        assert exam.title == "Midterm"
        assert exam.status == "active"
        assert exam.weeks_scope == [1, 2, 3, 4]
        assert exam.target_mastery_pct == 80

    @pytest.mark.asyncio
    async def test_raises_for_unknown_course(self):
        """Raises ValueError when course does not exist."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="not found"):
            await create_exam(
                session,
                course_code="FAKE",
                title="Test",
                exam_date=datetime.utcnow() + timedelta(days=7),
                weeks_scope=[1],
            )

    @pytest.mark.asyncio
    async def test_raises_for_past_date(self):
        """Raises ValueError when exam date is in the past."""
        session = AsyncMock()
        mock_course = MagicMock()
        mock_course.id = "course-001"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_course
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="future"):
            await create_exam(
                session,
                course_code="CSIT302",
                title="Past Exam",
                exam_date=datetime.utcnow() - timedelta(days=1),
                weeks_scope=[1],
            )

    @pytest.mark.asyncio
    async def test_custom_target_mastery(self):
        """Accepts custom target mastery percentage."""
        session = AsyncMock()
        mock_course = MagicMock()
        mock_course.id = "course-001"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_course
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()

        exam = await create_exam(
            session,
            course_code="CSIT302",
            title="Final",
            exam_date=datetime.utcnow() + timedelta(days=30),
            weeks_scope=[1, 2, 3],
            target_mastery_pct=90,
        )

        assert exam.target_mastery_pct == 90


class TestGetExam:
    """Tests for get_exam."""

    @pytest.mark.asyncio
    async def test_returns_active_exam(self):
        """Returns an active exam."""
        session = AsyncMock()
        mock_exam = MagicMock()
        mock_exam.status = "active"
        mock_exam.exam_date = datetime.utcnow() + timedelta(days=7)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_exam
        session.execute = AsyncMock(return_value=mock_result)

        exam = await get_exam(session, "exam-001")
        assert exam == mock_exam
        assert exam.status == "active"

    @pytest.mark.asyncio
    async def test_auto_completes_past_exam(self):
        """Auto-completes an active exam whose date has passed."""
        session = AsyncMock()
        mock_exam = MagicMock()
        mock_exam.status = "active"
        mock_exam.exam_date = datetime.utcnow() - timedelta(days=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_exam
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        exam = await get_exam(session, "exam-001")
        assert exam.status == "completed"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self):
        """Returns None when exam ID doesn't exist."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_exam(session, "nonexistent")
        assert result is None


class TestDeleteExam:
    """Tests for delete_exam (archive)."""

    @pytest.mark.asyncio
    async def test_archives_exam(self):
        """Archives an existing exam."""
        session = AsyncMock()
        mock_exam = MagicMock()
        mock_exam.status = "active"
        mock_exam.exam_date = datetime.utcnow() + timedelta(days=7)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_exam
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        result = await delete_exam(session, "exam-001")
        assert result is True
        assert mock_exam.status == "archived"

    @pytest.mark.asyncio
    async def test_returns_false_for_missing(self):
        """Returns False when exam doesn't exist."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await delete_exam(session, "nonexistent")
        assert result is False


class TestRecordQuizAttempt:
    """Tests for record_quiz_attempt."""

    @pytest.mark.asyncio
    async def test_records_correct_attempt(self):
        """Records a correct quiz attempt."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        attempt = await record_quiz_attempt(
            session,
            quiz_question_id="qq-001",
            selected_answer="Option A",
            is_correct=True,
            exam_id="exam-001",
            time_spent_ms=5000,
        )

        session.add.assert_called_once()
        assert attempt.quiz_question_id == "qq-001"
        assert attempt.is_correct is True
        assert attempt.exam_id == "exam-001"
        assert attempt.time_spent_ms == 5000

    @pytest.mark.asyncio
    async def test_records_without_exam(self):
        """Records an attempt without exam scope."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        attempt = await record_quiz_attempt(
            session,
            quiz_question_id="qq-001",
            selected_answer="Wrong",
            is_correct=False,
        )

        assert attempt.exam_id is None
        assert attempt.is_correct is False


class TestGetWeakTopics:
    """Tests for get_weak_topics."""

    @pytest.mark.asyncio
    async def test_identifies_low_quiz_accuracy(self):
        """Week with <70% quiz accuracy is flagged."""
        session = AsyncMock()

        # Quiz stats: week 1 has 50% accuracy
        mock_quiz = MagicMock()
        mock_quiz.__iter__ = MagicMock(return_value=iter([
            MagicMock(week=1, attempts=10, correct=5),
        ]))
        # Ease stats: no flashcard data
        mock_ease = MagicMock()
        mock_ease.__iter__ = MagicMock(return_value=iter([]))

        session.execute = AsyncMock(side_effect=[mock_quiz, mock_ease])

        result = await get_weak_topics(session, "course-001", [1, 2])

        # Both weeks should be in result
        weeks = {t["week"] for t in result}
        assert 1 in weeks
        assert 2 in weeks  # unstudied

        week1 = next(t for t in result if t["week"] == 1)
        assert "low_quiz_accuracy" in week1["reasons"]
        assert week1["quiz_accuracy"] == 50.0

    @pytest.mark.asyncio
    async def test_unstudied_weeks_flagged(self):
        """Weeks with no data are flagged as unstudied."""
        session = AsyncMock()

        mock_quiz = MagicMock()
        mock_quiz.__iter__ = MagicMock(return_value=iter([]))
        mock_ease = MagicMock()
        mock_ease.__iter__ = MagicMock(return_value=iter([]))

        session.execute = AsyncMock(side_effect=[mock_quiz, mock_ease])

        result = await get_weak_topics(session, "course-001", [1, 2, 3])

        assert len(result) == 3
        for topic in result:
            assert "unstudied" in topic["reasons"]
