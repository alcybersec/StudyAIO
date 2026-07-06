"""Tests for the CourseOps API endpoints."""

import io
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_document(
    id: str = "doc-001",
    course_id: str = "course-001",
    document_type: str = "outline",
    title: str = "Outline.pdf",
    original_filename: str = "Outline.pdf",
    file_type: str = "pdf",
    sha256: str = "abc123",
    file_size_bytes: int = 1024,
    status: str = "processed",
) -> MagicMock:
    doc = MagicMock()
    doc.id = id
    doc.course_id = course_id
    doc.document_type = document_type
    doc.title = title
    doc.original_filename = original_filename
    doc.file_type = file_type
    doc.sha256 = sha256
    doc.file_size_bytes = file_size_bytes
    doc.status = status
    doc.created_at = datetime(2026, 3, 1)
    doc.updated_at = datetime(2026, 3, 1)
    return doc


def _mock_assessment(
    id: str = "assess-001",
    course_id: str = "course-001",
    title: str = "Final Exam",
    assessment_type: str = "exam",
    weight_pct: float = 40.0,
) -> MagicMock:
    a = MagicMock()
    a.id = id
    a.course_id = course_id
    a.source_document_id = "doc-001"
    a.title = title
    a.assessment_type = assessment_type
    a.weight_pct = weight_pct
    a.description = "Covers all weeks"
    a.weeks_relevant = [1, 2, 3]
    a.created_at = datetime(2026, 3, 1)
    a.updated_at = datetime(2026, 3, 1)
    return a


def _mock_deadline(
    id: str = "dl-001",
    title: str = "Assignment 1 Due",
    due_date: date = date(2026, 4, 15),
    deadline_type: str = "assignment",
    is_confirmed: bool = False,
) -> MagicMock:
    dl = MagicMock()
    dl.id = id
    dl.course_id = "course-001"
    dl.assessment_id = None
    dl.source_document_id = "doc-001"
    dl.title = title
    dl.due_date = due_date
    dl.deadline_type = deadline_type
    dl.description = "Submit via Moodle"
    dl.is_confirmed = is_confirmed
    dl.created_at = datetime(2026, 3, 1)
    dl.updated_at = datetime(2026, 3, 1)
    return dl


@pytest.mark.asyncio
class TestListDocuments:
    """Tests for GET /api/courseops/documents."""

    async def test_list_documents(self, async_client):
        """Returns documents for a course."""
        docs = [_mock_document()]
        with patch(
            "app.api.courseops.courseops_service.list_course_documents",
            new_callable=AsyncMock,
            return_value=docs,
        ):
            response = await async_client.get("/api/courseops/documents?course_code=CSIT302")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "doc-001"
        assert data[0]["document_type"] == "outline"


@pytest.mark.asyncio
class TestCreateAssessment:
    """Tests for POST /api/courseops/assessments."""

    async def test_creates_manual_assessment(self, async_client):
        """Creates an assessment for a course and returns 201."""
        created = _mock_assessment(title="Midterm", assessment_type="exam")
        created.source_document_id = None
        with patch(
            "app.api.courseops.courseops_service.create_assessment",
            new_callable=AsyncMock,
            return_value=created,
        ) as mock_create:
            response = await async_client.post(
                "/api/courseops/assessments?course_code=CSIT302",
                json={"title": "Midterm", "assessment_type": "exam", "weight_pct": 30.0},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Midterm"
        assert data["source_document_id"] is None
        mock_create.assert_called_once()
        assert mock_create.call_args.kwargs["course_code"] == "CSIT302"
        assert mock_create.call_args.kwargs["title"] == "Midterm"

    async def test_returns_404_for_unknown_course(self, async_client):
        """Unknown course code yields 404."""
        with patch(
            "app.api.courseops.courseops_service.create_assessment",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.post(
                "/api/courseops/assessments?course_code=NOPE",
                json={"title": "X", "assessment_type": "exam"},
            )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestCreateDeadline:
    """Tests for POST /api/courseops/deadlines."""

    async def test_creates_manual_deadline(self, async_client):
        """Creates a deadline for a course and returns 201, confirmed by default."""
        created = _mock_deadline(title="Lab report", is_confirmed=True)
        created.source_document_id = None
        with patch(
            "app.api.courseops.courseops_service.create_deadline",
            new_callable=AsyncMock,
            return_value=created,
        ) as mock_create:
            response = await async_client.post(
                "/api/courseops/deadlines?course_code=CSIT302",
                json={"title": "Lab report", "due_date": "2026-05-01", "deadline_type": "assignment"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Lab report"
        assert data["is_confirmed"] is True
        mock_create.assert_called_once()
        assert mock_create.call_args.kwargs["course_code"] == "CSIT302"

    async def test_returns_404_for_unknown_course(self, async_client):
        """Unknown course code yields 404."""
        with patch(
            "app.api.courseops.courseops_service.create_deadline",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.post(
                "/api/courseops/deadlines?course_code=NOPE",
                json={"title": "X", "due_date": "2026-05-01"},
            )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestListAssessments:
    """Tests for GET /api/courseops/assessments."""

    async def test_list_assessments(self, async_client):
        """Returns assessments for a course."""
        assessments = [_mock_assessment()]
        with patch(
            "app.api.courseops.courseops_service.list_assessments",
            new_callable=AsyncMock,
            return_value=assessments,
        ):
            response = await async_client.get("/api/courseops/assessments?course_code=CSIT302")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Final Exam"
        assert data[0]["weight_pct"] == 40.0


@pytest.mark.asyncio
class TestListDeadlines:
    """Tests for GET /api/courseops/deadlines."""

    async def test_list_deadlines(self, async_client):
        """Returns deadlines for a course."""
        deadlines = [_mock_deadline()]
        with patch(
            "app.api.courseops.courseops_service.list_deadlines",
            new_callable=AsyncMock,
            return_value=deadlines,
        ):
            response = await async_client.get("/api/courseops/deadlines?course_code=CSIT302")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Assignment 1 Due"

    async def test_list_deadlines_upcoming(self, async_client):
        """Passes upcoming flag to service."""
        with patch(
            "app.api.courseops.courseops_service.list_deadlines",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_list:
            response = await async_client.get(
                "/api/courseops/deadlines?course_code=CSIT302&upcoming=true"
            )

        assert response.status_code == 200
        mock_list.assert_called_once_with(
            pytest.approx(mock_list.call_args[0][0], abs=1),
            "CSIT302",
            upcoming_only=True,
        )


@pytest.mark.asyncio
class TestUpdateDeadline:
    """Tests for PUT /api/courseops/deadlines/{id}."""

    async def test_updates_deadline(self, async_client):
        """Updates a deadline and returns it."""
        updated = _mock_deadline(is_confirmed=True)
        updated.title = "Updated Title"
        with patch(
            "app.api.courseops.courseops_service.update_deadline",
            new_callable=AsyncMock,
            return_value=updated,
        ):
            response = await async_client.put(
                "/api/courseops/deadlines/dl-001",
                json={"title": "Updated Title", "is_confirmed": True},
            )

        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"

    async def test_returns_404_for_missing(self, async_client):
        """Returns 404 when deadline not found."""
        with patch(
            "app.api.courseops.courseops_service.update_deadline",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.put(
                "/api/courseops/deadlines/bad-id",
                json={"title": "X"},
            )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestDeleteDeadline:
    """Tests for DELETE /api/courseops/deadlines/{id}."""

    async def test_deletes_deadline(self, async_client):
        """Deletes a deadline and returns 204."""
        with patch(
            "app.api.courseops.courseops_service.delete_deadline",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await async_client.delete("/api/courseops/deadlines/dl-001")

        assert response.status_code == 204

    async def test_returns_404_for_missing(self, async_client):
        """Returns 404 when deadline not found."""
        with patch(
            "app.api.courseops.courseops_service.delete_deadline",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = await async_client.delete("/api/courseops/deadlines/bad-id")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestCreateExamFromDeadline:
    """Tests for POST /api/courseops/deadlines/{id}/create-exam."""

    async def test_creates_exam(self, async_client):
        """Creates an exam from a deadline."""
        mock_exam = MagicMock()
        mock_exam.id = "exam-001"
        mock_exam.title = "Final Exam"
        mock_exam.exam_date = datetime(2026, 6, 15)
        mock_exam.status = "active"

        with patch(
            "app.api.courseops.courseops_service.create_exam_from_deadline",
            new_callable=AsyncMock,
            return_value=mock_exam,
        ):
            response = await async_client.post("/api/courseops/deadlines/dl-001/create-exam")

        assert response.status_code == 201
        data = response.json()
        assert data["exam_id"] == "exam-001"
        assert data["status"] == "active"

    async def test_returns_404_for_missing(self, async_client):
        """Returns 404 when deadline not found."""
        with patch(
            "app.api.courseops.courseops_service.create_exam_from_deadline",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.post("/api/courseops/deadlines/bad-id/create-exam")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestExportCalendar:
    """Tests for GET /api/courseops/export/calendar/{course_code}."""

    async def test_downloads_ics(self, async_client):
        """Returns .ics file as a download."""
        ics_content = b"BEGIN:VCALENDAR\nEND:VCALENDAR"
        buf = io.BytesIO(ics_content)

        with patch(
            "app.api.courseops.generate_ics",
            new_callable=AsyncMock,
            return_value=(buf, "CSIT302_deadlines.ics"),
        ):
            response = await async_client.get("/api/courseops/export/calendar/CSIT302")

        assert response.status_code == 200
        assert "text/calendar" in response.headers["content-type"]

    async def test_returns_404_for_unknown(self, async_client):
        """Returns 404 when course not found."""
        with patch(
            "app.api.courseops.generate_ics",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get("/api/courseops/export/calendar/FAKE")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestExportTaskPlan:
    """Tests for GET /api/courseops/export/task-plan/{course_code}."""

    async def test_downloads_md(self, async_client):
        """Returns .md file as a download."""
        md_content = b"# Task Plan"
        buf = io.BytesIO(md_content)

        with patch(
            "app.api.courseops.generate_task_plan_md",
            new_callable=AsyncMock,
            return_value=(buf, "CSIT302_task_plan.md"),
        ):
            response = await async_client.get("/api/courseops/export/task-plan/CSIT302")

        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]
