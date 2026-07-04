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
            await course_service.rename_course(
                mock_session, "user-001", "NOPE", name="x"
            )


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
        await course_service.list_courses(
            mock_session, user_id="user-001", include_archived=True
        )
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
            counts = await course_service.delete_course(
                mock_session, "user-001", "CSIT302"
            )
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

    def _course(self, course_id: str, code: str) -> MagicMock:
        course = MagicMock()
        course.id = course_id
        course.code = code
        course.archived_at = None
        return course

    async def test_merge_moves_and_creates_review_items_for_conflicts(self, mock_session):
        """Colliding weeks get review items instead of silent overwrite."""
        source = self._course("course-src", "CSIT302")
        target = self._course("course-tgt", "CSIT999")

        source_found = MagicMock()
        source_found.scalar_one_or_none.return_value = source
        target_found = MagicMock()
        target_found.scalar_one_or_none.return_value = target

        # Target already has a summary for week 2
        target_weeks = MagicMock()
        target_weeks.scalars.return_value.all.return_value = [2]

        # Source has summaries for weeks 1 (clean) and 2 (conflict)
        sum_w1 = MagicMock()
        sum_w1.id = "sum-1"
        sum_w1.week = 1
        sum_w1.course_id = "course-src"
        sum_w2 = MagicMock()
        sum_w2.id = "sum-2"
        sum_w2.week = 2
        sum_w2.course_id = "course-src"
        source_summaries = MagicMock()
        source_summaries.scalars.return_value.all.return_value = [sum_w1, sum_w2]

        update_result = MagicMock()
        update_result.rowcount = 1

        mock_session.execute = AsyncMock(
            side_effect=[source_found, target_found, target_weeks, source_summaries]
            + [update_result] * 12
        )

        with patch(
            "app.services.review_service.create_review_item",
            new_callable=AsyncMock,
        ) as mock_review:
            result = await course_service.merge_courses(
                mock_session, "user-001", "CSIT302", into_code="CSIT999"
            )

        # Clean week moved, conflict week untouched + review item
        assert sum_w1.course_id == "course-tgt"
        assert sum_w2.course_id == "course-src"
        mock_review.assert_awaited_once()
        review_kwargs = mock_review.call_args.kwargs
        assert review_kwargs.get("entity_id") == "sum-2"

        assert result["moved_summaries"] == 1
        assert result["conflict_weeks"] == [2]
        assert result["review_items_created"] == 1
        # Source course archived, not deleted
        assert source.archived_at is not None

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
