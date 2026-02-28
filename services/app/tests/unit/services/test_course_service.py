"""Tests for course_service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import course_service


@pytest.mark.asyncio
class TestListCourses:
    """Tests for list_courses."""

    async def test_list_courses_returns_ordered_results(self, mock_session):
        """list_courses queries with order_by code."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await course_service.list_courses(mock_session)
        assert result == []
        mock_session.execute.assert_called_once()


@pytest.mark.asyncio
class TestGetCourseByCode:
    """Tests for get_course_by_code."""

    async def test_get_course_found(self, mock_session):
        """get_course_by_code returns course when found."""
        mock_course = MagicMock()
        mock_course.code = "CSIT302"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_course
        mock_session.execute.return_value = mock_result

        result = await course_service.get_course_by_code(mock_session, "CSIT302")
        assert result is mock_course

    async def test_get_course_not_found(self, mock_session):
        """get_course_by_code returns None when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await course_service.get_course_by_code(mock_session, "UNKNOWN")
        assert result is None


@pytest.mark.asyncio
class TestGetCourseWeeks:
    """Tests for get_course_weeks."""

    async def test_get_weeks_empty(self, mock_session):
        """get_course_weeks returns empty list when no data."""
        # Each of the 4 queries returns empty results
        empty_result = MagicMock()
        empty_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute = AsyncMock(return_value=empty_result)

        result = await course_service.get_course_weeks(mock_session, "course-001")
        assert result == []
