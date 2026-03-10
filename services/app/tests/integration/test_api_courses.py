"""Integration tests for courses API endpoints."""

import pytest

from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course


@pytest.mark.asyncio(loop_scope="session")
class TestCoursesEndpoints:
    """Test /api/courses endpoints against a real database."""

    async def test_list_courses_empty(self, integration_client, db_session):
        """GET /api/courses returns empty list when no courses."""
        resp = await integration_client.get("/api/courses")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_courses_with_stats(self, integration_client, db_session, test_user_id):
        """GET /api/courses returns courses with aggregate stats."""
        course = Course(id=generate_id(), code="INT100", name="Integration", user_id=test_user_id)
        db_session.add(course)
        a = LectureArtifact(
            id=generate_id(),
            course_id=course.id,
            user_id=test_user_id,
            week=1,
            original_filename="lec.pdf",
            file_path="/data/uploads/lec.pdf",
            file_type="pdf",
            sha256="e" * 64,
            file_size_bytes=512,
            status="ingested",
        )
        db_session.add(a)
        await db_session.flush()

        resp = await integration_client.get("/api/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "INT100"
        assert data[0]["weeks_covered"] == 1
        assert data[0]["total_artifacts"] == 1

    async def test_get_course_detail(self, integration_client, db_session, test_user_id):
        """GET /api/courses/{code} returns course with weeks."""
        course = Course(id=generate_id(), code="INT200", name="Detail Test", user_id=test_user_id)
        db_session.add(course)
        a = LectureArtifact(
            id=generate_id(),
            course_id=course.id,
            user_id=test_user_id,
            week=3,
            title="Week 3 Lecture",
            original_filename="w3.pdf",
            file_path="/data/uploads/w3.pdf",
            file_type="pdf",
            sha256="f" * 64,
            file_size_bytes=512,
            status="ingested",
        )
        db_session.add(a)
        await db_session.flush()

        resp = await integration_client.get("/api/courses/INT200")
        assert resp.status_code == 200
        data = resp.json()
        assert data["course"]["code"] == "INT200"
        assert len(data["weeks"]) == 1
        assert data["weeks"][0]["week"] == 3

    async def test_get_nonexistent_course_returns_404(self, integration_client, db_session):
        """GET /api/courses/{code} returns 404 for unknown course."""
        resp = await integration_client.get("/api/courses/NOPE999")
        assert resp.status_code == 404
