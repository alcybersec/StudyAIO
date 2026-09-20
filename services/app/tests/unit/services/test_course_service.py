"""Tests for course_service."""

from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
class TestListCoursesWithStats:
    """Tests for list_courses_with_stats."""

    async def test_returns_empty_for_no_courses(self, mock_session):
        """Returns empty list when there are no courses."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await course_service.list_courses_with_stats(mock_session)
        assert result == []

    async def test_returns_stats_for_courses(self, mock_session):
        """Returns courses with aggregate weeks and artifact counts."""
        from datetime import datetime

        mock_course = MagicMock()
        mock_course.id = "course-001"
        mock_course.code = "CSIT302"
        mock_course.name = "Cybersecurity"
        mock_course.term = None
        mock_course.created_at = datetime(2024, 1, 1)
        mock_course.updated_at = datetime(2024, 1, 2)

        # First call: list_courses
        courses_result = MagicMock()
        courses_result.scalars.return_value.all.return_value = [mock_course]

        # Second call: aggregate query
        mock_stat_row = MagicMock()
        mock_stat_row.course_id = "course-001"
        mock_stat_row.weeks_covered = 5
        mock_stat_row.total_artifacts = 12

        stats_result = MagicMock()
        stats_result.__iter__ = MagicMock(return_value=iter([mock_stat_row]))

        mock_session.execute = AsyncMock(side_effect=[courses_result, stats_result])

        result = await course_service.list_courses_with_stats(mock_session)
        assert len(result) == 1
        assert result[0]["code"] == "CSIT302"
        assert result[0]["weeks_covered"] == 5
        assert result[0]["total_artifacts"] == 12


@pytest.mark.asyncio
class TestRenameCourse:
    """Tests for rename_course."""

    async def test_rename_updates_code_and_name(self, mock_session):
        """Rename sets the new code/name when no conflict exists."""
        course = MagicMock()
        course.id = "course-001"
        course.code = "CSIT302"
        found = MagicMock()
        found.scalar_one_or_none.return_value = course
        no_conflict = MagicMock()
        no_conflict.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(side_effect=[found, no_conflict])

        result = await course_service.rename_course(
            mock_session, "user-001", "CSIT302", new_code="CSIT999", name="Advanced"
        )

        assert result is course
        assert course.code == "CSIT999"
        assert course.name == "Advanced"

    async def test_rename_conflicting_code_raises(self, mock_session):
        """Renaming to a code owned by another course raises ValueError."""
        course = MagicMock()
        course.id = "course-001"
        conflict = MagicMock()
        conflict.id = "course-002"
        found = MagicMock()
        found.scalar_one_or_none.return_value = course
        conflict_result = MagicMock()
        conflict_result.scalar_one_or_none.return_value = conflict
        mock_session.execute = AsyncMock(side_effect=[found, conflict_result])

        with pytest.raises(ValueError):
            await course_service.rename_course(
                mock_session, "user-001", "CSIT302", new_code="CSIT999"
            )

    async def test_rename_unknown_course_raises(self, mock_session):
        """Unknown course raises LookupError."""
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=not_found)

        with pytest.raises(LookupError):
            await course_service.rename_course(mock_session, "user-001", "NOPE", name="x")


@pytest.mark.asyncio
class TestArchiveCourse:
    """Tests for archive_course."""

    async def test_archive_sets_archived_at(self, mock_session):
        """Archiving stamps archived_at."""
        course = MagicMock()
        course.archived_at = None
        found = MagicMock()
        found.scalar_one_or_none.return_value = course
        mock_session.execute = AsyncMock(return_value=found)

        result = await course_service.archive_course(mock_session, "user-001", "CSIT302")
        assert result is course
        assert course.archived_at is not None

    async def test_archive_unknown_course_raises(self, mock_session):
        """Unknown course raises LookupError."""
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=not_found)

        with pytest.raises(LookupError):
            await course_service.archive_course(mock_session, "user-001", "NOPE")


class TestListCoursesArchivedFilter:
    """list_courses hides archived courses unless asked."""

    @pytest.mark.asyncio
    async def test_default_excludes_archived(self, mock_session):
        """The default query filters archived_at IS NULL."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        captured = {}

        async def capture(query):
            captured["sql"] = str(query)
            return mock_result

        mock_session.execute = AsyncMock(side_effect=capture)
        await course_service.list_courses(mock_session, user_id="user-001")
        assert "archived_at IS NULL" in captured["sql"]

    @pytest.mark.asyncio
    async def test_include_archived_skips_filter(self, mock_session):
        """include_archived=True does not filter archived courses."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        captured = {}

        async def capture(query):
            captured["sql"] = str(query)
            return mock_result

        mock_session.execute = AsyncMock(side_effect=capture)
        await course_service.list_courses(mock_session, user_id="user-001", include_archived=True)
        assert "archived_at IS NULL" not in captured["sql"]


@pytest.mark.asyncio
class TestDeleteCourse:
    """Tests for delete_course."""

    async def test_delete_cascades_children_not_storage(self, mock_session):
        """Deletes child rows and the course; never touches storage blobs."""
        course = MagicMock()
        course.id = "course-001"
        found = MagicMock()
        found.scalar_one_or_none.return_value = course

        artifact_ids_result = MagicMock()
        artifact_ids_result.scalars.return_value.all.return_value = ["art-1", "art-2"]

        delete_result = MagicMock()
        delete_result.rowcount = 1
        delete_result.scalars.return_value.all.return_value = []

        async def dispatch(query):
            sql = str(query)
            if "FROM courses" in sql and "SELECT" in sql.upper()[:20]:
                return found
            if "lecture_artifacts.id" in sql and sql.upper().startswith("SELECT"):
                return artifact_ids_result
            return delete_result

        mock_session.execute = AsyncMock(side_effect=dispatch)

        with patch("app.services.course_service.get_storage", create=True) as mock_storage:
            counts = await course_service.delete_course(mock_session, "user-001", "CSIT302")
            mock_storage.assert_not_called()

        assert counts["artifacts"] == 2
        # Course row itself deleted
        deleted_sql = [str(c.args[0]) for c in mock_session.execute.call_args_list]
        assert any("DELETE FROM courses" in s for s in deleted_sql)
        assert any("DELETE FROM lecture_artifacts" in s for s in deleted_sql)
        assert any("DELETE FROM flashcards" in s for s in deleted_sql)
        assert any("DELETE FROM summaries" in s for s in deleted_sql)

    async def test_delete_unknown_course_raises(self, mock_session):
        """Unknown course raises LookupError."""
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=not_found)

        with pytest.raises(LookupError):
            await course_service.delete_course(mock_session, "user-001", "NOPE")


@pytest.mark.asyncio
class TestMergeCourses:
    """Tests for merge_courses."""

    # The conflict behaviour itself is covered by
    # tests/integration/test_course_merge_conflicts.py, against a real database
    # and a real storage root.
    #
    # It used to be covered here, by a mocked session whose `execute` returned a
    # fixed `side_effect` list. That test asserted `create_review_item` had been
    # awaited once -- which was true, and told us nothing about whether the
    # review item it created could ever be acted on. It could not (#63). A test
    # that can only see which methods were called cannot distinguish a working
    # feature from a half-built one, and this was the case in point: it passed
    # for the entire life of the bug, and its `side_effect` ordering broke the
    # moment the statements were reordered to fix it.
    #
    # What stays here is the input validation, which needs no database.

    async def test_unknown_conflict_policy_raises(self, mock_session):
        """An unrecognised on_conflict is refused before any lookup."""
        with pytest.raises(ValueError, match="on_conflict"):
            await course_service.merge_courses(
                mock_session,
                "user-001",
                "CSIT302",
                into_code="CSIT999",
                on_conflict="whatever",
            )
        # Refused without touching the session at all, so a typo in a script
        # cannot leave a course half-merged.
        mock_session.execute.assert_not_called()

    async def test_api_literal_matches_the_service_policy_set(self):
        """The request schema and the service's accepted set cannot drift.

        The endpoint validates `on_conflict` with a `Literal`, and the service
        validates it again against `MERGE_CONFLICT_POLICIES`. Two lists of the
        same strings in two files is exactly the shape that rots: adding a
        policy to one side alone yields either a 422 for a policy the service
        supports, or a `ValueError` surfacing as a 400 for one the schema
        advertises. So assert the wiring rather than restating the strings.
        """
        import typing

        from app.api.courses import CourseMergeRequest

        literal = CourseMergeRequest.model_fields["on_conflict"].annotation
        assert set(typing.get_args(literal)) == course_service.MERGE_CONFLICT_POLICIES

    async def test_merge_into_itself_raises(self, mock_session):
        """Merging a course into itself raises ValueError."""
        with pytest.raises(ValueError):
            await course_service.merge_courses(
                mock_session, "user-001", "CSIT302", into_code="CSIT302"
            )

    async def test_merge_unknown_source_raises(self, mock_session):
        """Unknown source course raises LookupError."""
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=not_found)

        with pytest.raises(LookupError):
            await course_service.merge_courses(
                mock_session, "user-001", "NOPE", into_code="CSIT999"
            )
