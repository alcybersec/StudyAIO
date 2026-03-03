"""Tests for courseops service."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import CourseOpsAssessment, CourseOpsDeadline, CourseOpsResult
from app.core.exceptions import CourseOpsError
from app.services.courseops_service import (
    create_exam_from_deadline,
    delete_deadline,
    get_upcoming_deadlines_all_courses,
    list_assessments,
    list_course_documents,
    list_deadlines,
    process_course_document,
    update_deadline,
    upload_course_document,
)


class TestUploadCourseDocument:
    """Tests for upload_course_document."""

    @pytest.mark.asyncio
    async def test_uploads_successfully(self):
        """Creates a course document when course exists and no duplicate."""
        session = AsyncMock()
        mock_course = MagicMock()
        mock_course.id = "course-001"

        # First execute: find course; second: check duplicate
        no_dup = MagicMock()
        no_dup.scalar_one_or_none.return_value = None
        find_course = MagicMock()
        find_course.scalar_one_or_none.return_value = mock_course
        session.execute = AsyncMock(side_effect=[find_course, no_dup])
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        doc = await upload_course_document(
            session=session,
            course_code="CSIT302",
            document_type="outline",
            original_filename="outline.pdf",
            file_path="/data/courseops/outline.pdf",
            file_type="pdf",
            sha256="abc123",
            file_size_bytes=1024,
        )

        session.add.assert_called_once()
        assert doc.course_id == "course-001"
        assert doc.document_type == "outline"
        assert doc.status == "pending"

    @pytest.mark.asyncio
    async def test_raises_for_unknown_course(self):
        """Raises CourseOpsError when course not found."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(CourseOpsError, match="not found"):
            await upload_course_document(
                session=session,
                course_code="FAKE",
                document_type="outline",
                original_filename="f.pdf",
                file_path="/data/f.pdf",
                file_type="pdf",
                sha256="abc",
                file_size_bytes=100,
            )

    @pytest.mark.asyncio
    async def test_raises_for_duplicate(self):
        """Raises CourseOpsError when SHA-256 already exists for course."""
        session = AsyncMock()
        mock_course = MagicMock()
        mock_course.id = "course-001"
        find_course = MagicMock()
        find_course.scalar_one_or_none.return_value = mock_course
        dup_found = MagicMock()
        dup_found.scalar_one_or_none.return_value = MagicMock()
        session.execute = AsyncMock(side_effect=[find_course, dup_found])

        with pytest.raises(CourseOpsError, match="already uploaded"):
            await upload_course_document(
                session=session,
                course_code="CSIT302",
                document_type="outline",
                original_filename="f.pdf",
                file_path="/data/f.pdf",
                file_type="pdf",
                sha256="abc",
                file_size_bytes=100,
            )


class TestProcessCourseDocument:
    """Tests for process_course_document."""

    @pytest.mark.asyncio
    async def test_processes_with_assessments_and_deadlines(self):
        """Creates assessments and deadlines from AI result."""
        session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.course_id = "course-001"
        mock_course = MagicMock()
        mock_course.name = None
        mock_course.term = None

        session.get = AsyncMock(side_effect=lambda model, id: {
            "doc-001": mock_doc,
            "course-001": mock_course,
        }.get(id))
        session.add = MagicMock()
        session.commit = AsyncMock()

        ai_result = CourseOpsResult(
            assessments=[
                CourseOpsAssessment(
                    title="Final Exam",
                    assessment_type="exam",
                    weight_pct=40.0,
                    description="Weeks 1-13",
                    weeks_relevant=[1, 2, 3],
                ),
                CourseOpsAssessment(
                    title="Assignment 1",
                    assessment_type="assignment",
                    weight_pct=20.0,
                ),
            ],
            deadlines=[
                CourseOpsDeadline(
                    title="Final Exam",
                    due_date="2026-06-15",
                    deadline_type="exam",
                    description="Main exam hall",
                ),
            ],
            course_info={"course_name": "Software Eng", "term": "Spring 2026"},
            confidence=0.85,
        )

        result = await process_course_document(
            session=session,
            document_id="doc-001",
            extracted_text="Course outline text...",
            ai_result=ai_result,
        )

        assert result["assessment_count"] == 2
        assert result["deadline_count"] == 1
        assert result["confidence"] == 0.85
        assert mock_doc.status == "processed"
        # Course info should be updated
        assert mock_course.name == "Software Eng"
        assert mock_course.term == "Spring 2026"

    @pytest.mark.asyncio
    async def test_skips_invalid_dates(self):
        """Skips deadlines with invalid date strings."""
        session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.course_id = "course-001"
        session.get = AsyncMock(side_effect=lambda model, id: {
            "doc-001": mock_doc,
            "course-001": MagicMock(name=None, term=None),
        }.get(id))
        session.add = MagicMock()
        session.commit = AsyncMock()

        ai_result = CourseOpsResult(
            deadlines=[
                CourseOpsDeadline(title="Bad Date", due_date="not-a-date", deadline_type="exam"),
                CourseOpsDeadline(title="Good", due_date="2026-06-15", deadline_type="assignment"),
            ],
        )

        result = await process_course_document(session, "doc-001", "text", ai_result)
        assert result["deadline_count"] == 1

    @pytest.mark.asyncio
    async def test_raises_for_missing_document(self):
        """Raises CourseOpsError when document not found."""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        with pytest.raises(CourseOpsError, match="not found"):
            await process_course_document(session, "bad-id", "text", CourseOpsResult())


class TestUpdateDeadline:
    """Tests for update_deadline."""

    @pytest.mark.asyncio
    async def test_updates_fields(self):
        """Updates specified fields on a deadline."""
        session = AsyncMock()
        mock_deadline = MagicMock()
        mock_deadline.title = "Old Title"
        mock_deadline.is_confirmed = False
        session.get = AsyncMock(return_value=mock_deadline)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        result = await update_deadline(
            session, "dl-001", title="New Title", is_confirmed=True
        )

        assert result.title == "New Title"
        assert result.is_confirmed is True

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self):
        """Returns None when deadline not found."""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        result = await update_deadline(session, "bad-id", title="X")
        assert result is None


class TestDeleteDeadline:
    """Tests for delete_deadline."""

    @pytest.mark.asyncio
    async def test_deletes_existing(self):
        """Deletes a deadline and returns True."""
        session = AsyncMock()
        session.get = AsyncMock(return_value=MagicMock())
        session.delete = AsyncMock()
        session.commit = AsyncMock()

        assert await delete_deadline(session, "dl-001") is True
        session.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_for_missing(self):
        """Returns False when deadline not found."""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        assert await delete_deadline(session, "bad-id") is False


class TestCreateExamFromDeadline:
    """Tests for create_exam_from_deadline."""

    @pytest.mark.asyncio
    async def test_creates_exam(self):
        """Creates an exam from a deadline."""
        session = AsyncMock()
        mock_deadline = MagicMock()
        mock_deadline.course_id = "course-001"
        mock_deadline.title = "Final Exam"
        mock_deadline.due_date = date(2026, 6, 15)
        mock_deadline.assessment_id = "assess-001"
        mock_deadline.is_confirmed = False

        mock_assessment = MagicMock()
        mock_assessment.weeks_relevant = [1, 2, 3, 4, 5]

        session.get = AsyncMock(side_effect=lambda model, id: {
            "dl-001": mock_deadline,
            "assess-001": mock_assessment,
        }.get(id))
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        exam = await create_exam_from_deadline(session, "dl-001")
        assert exam is not None
        session.add.assert_called_once()
        assert mock_deadline.is_confirmed is True

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self):
        """Returns None when deadline not found."""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        assert await create_exam_from_deadline(session, "bad-id") is None


class TestListFunctions:
    """Tests for list_course_documents, list_assessments, list_deadlines."""

    @pytest.mark.asyncio
    async def test_list_documents_returns_empty_for_unknown_course(self):
        """Returns empty list when course not found."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await list_course_documents(session, "FAKE")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_assessments_returns_empty_for_unknown_course(self):
        """Returns empty list when course not found."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await list_assessments(session, "FAKE")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_deadlines_returns_empty_for_unknown_course(self):
        """Returns empty list when course not found."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await list_deadlines(session, "FAKE")
        assert result == []
