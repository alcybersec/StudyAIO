"""Integration tests for database constraint enforcement."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.summary import Summary
from app.models.user import User


@pytest.mark.asyncio(loop_scope="session")
class TestCourseConstraints:
    """Test Course model DB constraints."""

    async def test_course_code_unique(self, db_session, test_user_id):
        """Duplicate course codes raise IntegrityError."""
        c1 = Course(id=generate_id(), code="CSIT302", name="Cybersecurity", user_id=test_user_id)
        db_session.add(c1)
        await db_session.flush()

        c2 = Course(id=generate_id(), code="CSIT302", name="Duplicate", user_id=test_user_id)
        db_session.add(c2)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_course_code_not_null(self, db_session, test_user_id):
        """Course code cannot be null."""
        c = Course(id=generate_id(), code=None, name="No Code", user_id=test_user_id)
        db_session.add(c)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio(loop_scope="session")
class TestArtifactConstraints:
    """Test LectureArtifact model DB constraints."""

    async def test_artifact_sha256_unique(self, db_session, test_user_id):
        """Duplicate SHA-256 hashes raise IntegrityError."""
        sha = "a" * 64
        a1 = LectureArtifact(
            id=generate_id(),
            user_id=test_user_id,
            original_filename="file1.pdf",
            file_path="/data/uploads/file1.pdf",
            file_type="pdf",
            sha256=sha,
            file_size_bytes=1024,
            status="ingested",
        )
        db_session.add(a1)
        await db_session.flush()

        a2 = LectureArtifact(
            id=generate_id(),
            user_id=test_user_id,
            original_filename="file2.pdf",
            file_path="/data/uploads/file2.pdf",
            file_type="pdf",
            sha256=sha,
            file_size_bytes=2048,
            status="ingested",
        )
        db_session.add(a2)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_artifact_fk_course(self, db_session, test_user_id):
        """Artifact with nonexistent course_id raises IntegrityError."""
        a = LectureArtifact(
            id=generate_id(),
            user_id=test_user_id,
            course_id="nonexistent-id",
            original_filename="file.pdf",
            file_path="/data/uploads/file.pdf",
            file_type="pdf",
            sha256="b" * 64,
            file_size_bytes=1024,
            status="ingested",
        )
        db_session.add(a)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio(loop_scope="session")
class TestSummaryConstraints:
    """Test Summary model DB constraints."""

    async def test_summary_course_week_unique(self, db_session, test_user_id):
        """Duplicate (course_id, week) raises IntegrityError."""
        course = Course(id=generate_id(), code="TEST101", name="Test Course", user_id=test_user_id)
        db_session.add(course)
        await db_session.flush()

        s1 = Summary(
            id=generate_id(),
            course_id=course.id,
            week=1,
            content_md="# Week 1 Summary",
            file_path="/data/summaries/s1.md",
            version=1,
            source_artifacts=[],
        )
        db_session.add(s1)
        await db_session.flush()

        s2 = Summary(
            id=generate_id(),
            course_id=course.id,
            week=1,
            content_md="# Duplicate",
            file_path="/data/summaries/s2.md",
            version=2,
            source_artifacts=[],
        )
        db_session.add(s2)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio(loop_scope="session")
class TestUserEmailConstraints:
    """The case-insensitive unique index from issue #91.

    The code normalizes on the way in, but a code-only fix leaves the next
    `select(User).where(User.email == ...)` free to reintroduce the bug. This
    is the half the database enforces: whatever a call site forgets, two rows
    cannot claim one address. It exists only because the migration ran, so
    this also proves `d0e1f2g3h4i5` created the index for real.
    """

    def _user(self, email: str, username: str) -> User:
        return User(
            id=generate_id(),
            email=email,
            username=username,
            role="user",
            tier="free",
            is_active=True,
            email_verified=False,
            mfa_enabled=False,
        )

    async def test_case_differing_emails_are_rejected(self, db_session):
        """`alex@…` and `Alex@…` were two valid accounts before #91."""
        db_session.add(self._user("constraint.alex@example.com", "constraint_alex_1"))
        await db_session.flush()

        db_session.add(self._user("Constraint.Alex@Example.com", "constraint_alex_2"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_genuinely_different_emails_are_still_accepted(self, db_session):
        """The negative control: the index must not reject distinct addresses."""
        db_session.add(self._user("distinct.one@example.com", "distinct_one"))
        db_session.add(self._user("distinct.two@example.com", "distinct_two"))

        await db_session.flush()  # would raise IntegrityError if over-broad
