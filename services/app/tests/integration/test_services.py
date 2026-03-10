"""Integration tests for service-layer business logic against real DB."""

import pytest

from app.core.exceptions import DuplicateFileError
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.services import artifact_service, course_service, review_service


@pytest.mark.asyncio(loop_scope="session")
class TestArtifactService:
    """Test artifact_service with a real database."""

    async def test_ingest_file_round_trip(self, db_session, simple_pdf, tmp_path):
        """ingest_file creates an artifact and persists it."""
        artifact = await artifact_service.ingest_file(db_session, str(simple_pdf))

        assert artifact.id is not None
        assert artifact.original_filename == "test_lecture.pdf"
        assert artifact.file_type == "pdf"
        assert artifact.status == "ingested"
        assert len(artifact.sha256) == 64

        # Verify it's in the DB
        fetched = await artifact_service.get_artifact(db_session, artifact.id)
        assert fetched is not None
        assert fetched.sha256 == artifact.sha256

    async def test_ingest_duplicate_raises(self, db_session, simple_pdf):
        """Ingesting the same file twice raises DuplicateFileError."""
        await artifact_service.ingest_file(db_session, str(simple_pdf))

        with pytest.raises(DuplicateFileError):
            await artifact_service.ingest_file(db_session, str(simple_pdf))

    async def test_ingest_unsupported_type_raises(self, db_session, tmp_path):
        """Ingesting an unsupported file type raises ValueError."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported file type"):
            await artifact_service.ingest_file(db_session, str(txt_file))


@pytest.mark.asyncio(loop_scope="session")
class TestReviewService:
    """Test review_service lifecycle with a real database."""

    async def test_create_and_list(self, db_session):
        """Create a review item, verify it appears in pending list."""
        item = await review_service.create_review_item(
            db_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=generate_id(),
            payload={"filename": "test.pdf"},
            suggested_values={"course_code": "CSIT302"},
        )
        await db_session.commit()

        assert item.status == "pending"

        pending = await review_service.list_pending_reviews(db_session)
        assert any(r.id == item.id for r in pending)

    async def test_resolve_lifecycle(self, db_session):
        """Create → resolve → verify status and resolution."""
        item = await review_service.create_review_item(
            db_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=generate_id(),
            payload={},
            suggested_values={},
        )
        await db_session.commit()

        resolved = await review_service.resolve_review_item(
            db_session, item.id, {"course_code": "CSIT314"}
        )
        await db_session.commit()

        assert resolved.status == "resolved"
        assert resolved.resolution_json == {"course_code": "CSIT314"}
        assert resolved.resolved_at is not None

    async def test_dismiss_lifecycle(self, db_session):
        """Create → dismiss → verify status."""
        item = await review_service.create_review_item(
            db_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=generate_id(),
            payload={},
            suggested_values={},
        )
        await db_session.commit()

        dismissed = await review_service.dismiss_review_item(db_session, item.id)
        await db_session.commit()

        assert dismissed.status == "dismissed"
        assert dismissed.resolved_at is not None

    async def test_double_resolve_raises(self, db_session):
        """Resolving an already-resolved item raises ValueError."""
        item = await review_service.create_review_item(
            db_session,
            review_type="classification_course",
            entity_type="lecture_artifact",
            entity_id=generate_id(),
            payload={},
            suggested_values={},
        )
        await db_session.commit()

        await review_service.resolve_review_item(db_session, item.id, {})
        await db_session.commit()

        with pytest.raises(ValueError, match="already"):
            await review_service.resolve_review_item(db_session, item.id, {})


@pytest.mark.asyncio(loop_scope="session")
class TestCourseService:
    """Test course_service with a real database."""

    async def test_list_courses_with_stats_empty(self, db_session):
        """Returns empty list when no courses exist."""
        result = await course_service.list_courses_with_stats(db_session)
        assert result == []

    async def test_list_courses_with_stats_aggregation(self, db_session):
        """Stats reflect actual artifact counts."""
        course = Course(id=generate_id(), code="TEST200", name="Test")
        db_session.add(course)
        await db_session.flush()

        # Add 2 artifacts in week 1, 1 artifact in week 2
        for i, week in enumerate([1, 1, 2]):
            a = LectureArtifact(
                id=generate_id(),
                course_id=course.id,
                week=week,
                original_filename=f"lec{i}.pdf",
                file_path=f"/data/uploads/lec{i}.pdf",
                file_type="pdf",
                sha256=f"{i:064d}",
                file_size_bytes=1024,
                status="ingested",
            )
            db_session.add(a)
        await db_session.flush()

        result = await course_service.list_courses_with_stats(db_session)
        assert len(result) == 1
        assert result[0]["code"] == "TEST200"
        assert result[0]["weeks_covered"] == 2
        assert result[0]["total_artifacts"] == 3
