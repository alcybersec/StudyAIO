"""Tests for calendar service."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.calendar_service import generate_ics, generate_task_plan_md


def _make_deadline(
    id: str = "dl-001",
    title: str = "Assignment 1",
    due_date: date = date(2026, 4, 15),
    deadline_type: str = "assignment",
    description: str = "Submit via Moodle",
    is_confirmed: bool = True,
) -> MagicMock:
    dl = MagicMock()
    dl.id = id
    dl.title = title
    dl.due_date = due_date
    dl.deadline_type = deadline_type
    dl.description = description
    dl.is_confirmed = is_confirmed
    return dl


def _make_assessment(
    title: str = "Final Exam",
    assessment_type: str = "exam",
    weight_pct: float | None = 40.0,
) -> MagicMock:
    a = MagicMock()
    a.title = title
    a.assessment_type = assessment_type
    a.weight_pct = weight_pct
    return a


class TestGenerateIcs:
    """Tests for generate_ics."""

    @pytest.mark.asyncio
    async def test_generates_ics_with_deadlines(self):
        """Generates valid .ics content with events."""
        session = AsyncMock()
        mock_course = MagicMock()
        mock_course.id = "course-001"
        mock_course.code = "CSIT302"

        course_result = MagicMock()
        course_result.scalar_one_or_none.return_value = mock_course

        deadlines = [
            _make_deadline(id="dl-001", title="Assignment 1", due_date=date(2026, 4, 15)),
            _make_deadline(id="dl-002", title="Final Exam", due_date=date(2026, 6, 15), deadline_type="exam"),
        ]
        dl_result = MagicMock()
        dl_result.scalars.return_value.all.return_value = deadlines

        session.execute = AsyncMock(side_effect=[course_result, dl_result])

        result = await generate_ics(session, "CSIT302")
        assert result is not None
        buf, filename = result
        assert filename == "CSIT302_deadlines.ics"

        content = buf.read().decode("utf-8")
        assert "BEGIN:VCALENDAR" in content
        assert "BEGIN:VEVENT" in content
        assert "[CSIT302] Assignment 1" in content
        assert "[CSIT302] Final Exam" in content
        assert "PRODID:-//StudyAIO" in content

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_course(self):
        """Returns None when course not found."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await generate_ics(session, "FAKE")
        assert result is None

    @pytest.mark.asyncio
    async def test_ics_marks_unconfirmed(self):
        """Unconfirmed deadlines are noted in the description."""
        session = AsyncMock()
        mock_course = MagicMock()
        mock_course.id = "course-001"
        mock_course.code = "CSIT302"

        course_result = MagicMock()
        course_result.scalar_one_or_none.return_value = mock_course

        deadlines = [_make_deadline(is_confirmed=False)]
        dl_result = MagicMock()
        dl_result.scalars.return_value.all.return_value = deadlines

        session.execute = AsyncMock(side_effect=[course_result, dl_result])

        result = await generate_ics(session, "CSIT302")
        content = result[0].read().decode("utf-8")
        # ICS uses line folding (\r\n + space), so unfold before checking
        unfolded = content.replace("\r\n ", "")
        assert "extracted by AI" in unfolded


class TestGenerateTaskPlanMd:
    """Tests for generate_task_plan_md."""

    @pytest.mark.asyncio
    async def test_generates_markdown(self):
        """Generates markdown with assessments and deadlines."""
        session = AsyncMock()
        mock_course = MagicMock()
        mock_course.id = "course-001"
        mock_course.code = "CSIT302"
        mock_course.name = "Software Engineering"
        mock_course.term = "Spring 2026"

        course_result = MagicMock()
        course_result.scalar_one_or_none.return_value = mock_course

        assessments = [
            _make_assessment("Final Exam", "exam", 40.0),
            _make_assessment("Assignment 1", "assignment", 20.0),
        ]
        assess_result = MagicMock()
        assess_result.scalars.return_value.all.return_value = assessments

        deadlines = [
            _make_deadline(title="Assignment 1 Due", due_date=date(2026, 4, 15)),
            _make_deadline(title="Final Exam", due_date=date(2026, 6, 15), deadline_type="exam"),
        ]
        dl_result = MagicMock()
        dl_result.scalars.return_value.all.return_value = deadlines

        session.execute = AsyncMock(side_effect=[course_result, assess_result, dl_result])

        result = await generate_task_plan_md(session, "CSIT302")
        assert result is not None
        buf, filename = result
        assert filename == "CSIT302_task_plan.md"

        content = buf.read().decode("utf-8")
        assert "# CSIT302" in content
        assert "Software Engineering" in content
        assert "Assessment Overview" in content
        assert "40%" in content
        assert "Assignment 1 Due" in content
        assert "Final Exam" in content

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_course(self):
        """Returns None when course not found."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await generate_task_plan_md(session, "FAKE")
        assert result is None
