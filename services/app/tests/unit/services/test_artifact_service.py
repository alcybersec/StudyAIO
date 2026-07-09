"""Tests for artifact_service."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import DuplicateFileError
from app.core.storage import LocalStorageBackend
from app.services import artifact_service

TEST_USER_ID = "user-001"


class TestCheckDuplicate:
    """Tests for check_duplicate()."""

    async def test_returns_none_when_no_match(self, mock_session):
        """No duplicate returns None."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await artifact_service.check_duplicate(mock_session, "abc123", TEST_USER_ID)
        assert result is None

    async def test_returns_artifact_when_match(self, mock_session):
        """Existing hash returns the artifact."""
        existing = MagicMock()
        existing.id = "artifact-existing"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        result = await artifact_service.check_duplicate(mock_session, "abc123", TEST_USER_ID)
        assert result is not None
        assert result.id == "artifact-existing"


class TestIngestFile:
    """Tests for ingest_file()."""

    async def test_file_not_found_raises(self, mock_session):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await artifact_service.ingest_file(mock_session, "/nonexistent/file.pdf", TEST_USER_ID)

    async def test_unsupported_extension_raises(self, mock_session, tmp_path):
        """Unsupported file type raises ValueError."""
        bad_file = tmp_path / "file.txt"
        bad_file.write_text("hello")

        with pytest.raises(ValueError, match="Unsupported file type"):
            await artifact_service.ingest_file(mock_session, str(bad_file), TEST_USER_ID)

    async def test_duplicate_raises(self, mock_session, simple_pdf):
        """Duplicate file raises DuplicateFileError."""
        existing = MagicMock()
        existing.id = "existing-id"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        with pytest.raises(DuplicateFileError):
            await artifact_service.ingest_file(mock_session, str(simple_pdf), TEST_USER_ID)

    async def test_ingest_success(self, mock_session, simple_pdf, tmp_path):
        """Successful ingest creates artifact."""
        local_storage = LocalStorageBackend(base_dir=str(tmp_path))

        # No duplicate found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("app.services.artifact_service.get_storage", return_value=local_storage):
            result = await artifact_service.ingest_file(mock_session, str(simple_pdf), TEST_USER_ID)

        assert result.original_filename == simple_pdf.name
        assert result.file_type == "pdf"
        assert result.status == "ingested"
        assert len(result.sha256) == 64
        assert result.user_id == TEST_USER_ID
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
class TestIngestTextCapture:
    """Tests for ingest_text_capture."""

    async def test_creates_capture_artifact(self, mock_session, tmp_path):
        """Text capture creates a txt artifact with source_type='capture'."""
        from unittest.mock import patch

        from app.core.storage import reset_storage

        # No duplicate
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = dup_result

        with patch("app.config.settings.data_dir", str(tmp_path)):
            reset_storage()
            try:
                artifact = await artifact_service.ingest_text_capture(
                    mock_session,
                    text="Some captured notes",
                    title="My notes",
                    user_id=TEST_USER_ID,
                )
            finally:
                reset_storage()

        assert artifact.source_type == "capture"
        assert artifact.file_type == "txt"
        assert artifact.user_id == TEST_USER_ID
        assert artifact.original_filename.endswith(".txt")
        assert "My notes" in artifact.original_filename
        mock_session.add.assert_called_once()
        # The stored file exists under uploads/
        stored = list((tmp_path / "uploads").glob("*.txt"))
        assert len(stored) == 1
        assert stored[0].read_text() == "Some captured notes"

    async def test_duplicate_capture_raises(self, mock_session, tmp_path):
        """The same text captured twice raises DuplicateFileError."""
        from unittest.mock import patch

        from app.core.exceptions import DuplicateFileError
        from app.core.storage import reset_storage

        existing = MagicMock()
        existing.id = "art-existing"
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = dup_result

        with patch("app.config.settings.data_dir", str(tmp_path)):
            reset_storage()
            try:
                with pytest.raises(DuplicateFileError) as exc_info:
                    await artifact_service.ingest_text_capture(
                        mock_session,
                        text="Same text",
                        title=None,
                        user_id=TEST_USER_ID,
                    )
            finally:
                reset_storage()

        assert exc_info.value.existing_artifact_id == "art-existing"


@pytest.mark.asyncio
class TestApplyClassification:
    """Tests for the shared classification helper."""

    async def test_applies_course_week_and_title(self, mock_session):
        """Sets course_id, week, title and status from resolution values."""
        course = MagicMock()
        course.id = "course-001"
        course_result = MagicMock()
        course_result.scalar_one_or_none.return_value = course
        mock_session.execute.return_value = course_result

        artifact = MagicMock()
        result = await artifact_service.apply_classification(
            mock_session,
            artifact,
            course_code="CSIT302",
            week=5,
            title="Network Security",
        )

        assert result is course
        assert artifact.course_id == "course-001"
        assert artifact.week == 5
        assert artifact.title == "Network Security"

    async def test_unknown_course_leaves_course_unset(self, mock_session):
        """Unknown course code returns None and does not set course_id."""
        course_result = MagicMock()
        course_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = course_result

        artifact = MagicMock()
        artifact.course_id = "original"
        result = await artifact_service.apply_classification(
            mock_session, artifact, course_code="NOPE", week=2
        )

        assert result is None
        assert artifact.course_id == "original"
        assert artifact.week == 2


@pytest.mark.asyncio
class TestReclassify:
    """Tests for reclassify()."""

    def _artifact(self, status: str = "processed") -> MagicMock:
        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.user_id = TEST_USER_ID
        artifact.course_id = "course-src"
        artifact.week = 2
        artifact.status = status
        return artifact

    async def test_reclassify_moves_artifact_and_children(self, mock_session):
        """Artifact, flashcards, and quiz questions all point at the target."""
        from unittest.mock import AsyncMock

        artifact = self._artifact()
        course = MagicMock()
        course.id = "course-target"
        course.code = "CSIT302"

        artifact_result = MagicMock()
        artifact_result.scalar_one_or_none.return_value = artifact
        course_result = MagicMock()
        course_result.scalar_one_or_none.return_value = course
        update_result = MagicMock()
        remaining_result = MagicMock()
        remaining_result.scalar_one_or_none.return_value = "art-002"

        mock_session.execute = AsyncMock(
            side_effect=[
                artifact_result,  # load artifact
                course_result,  # resolve target course
                update_result,  # flashcards update
                update_result,  # quiz update
                remaining_result,  # remaining source-week artifact
            ]
        )

        result = await artifact_service.reclassify(
            mock_session,
            "art-001",
            user_id=TEST_USER_ID,
            course_code="CSIT302",
            week=4,
        )

        assert artifact.course_id == "course-target"
        assert artifact.week == 4
        assert result["old_course_id"] == "course-src"
        assert result["old_week"] == 2
        assert result["source_artifact_id"] == "art-002"
        # 5 statements: load, course lookup, 2 child updates, remaining lookup
        assert mock_session.execute.await_count == 5

    async def test_reclassify_busy_artifact_raises(self, mock_session):
        """An artifact still processing raises ArtifactBusyError."""
        from unittest.mock import AsyncMock

        from app.core.exceptions import ArtifactBusyError

        artifact = self._artifact(status="summarizing")
        artifact_result = MagicMock()
        artifact_result.scalar_one_or_none.return_value = artifact
        mock_session.execute = AsyncMock(return_value=artifact_result)

        with pytest.raises(ArtifactBusyError):
            await artifact_service.reclassify(
                mock_session,
                "art-001",
                user_id=TEST_USER_ID,
                course_code="CSIT302",
                week=4,
            )

    async def test_reclassify_unknown_artifact_raises(self, mock_session):
        """Foreign/unknown artifact raises LookupError (tenant isolation)."""
        from unittest.mock import AsyncMock

        artifact_result = MagicMock()
        artifact_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=artifact_result)

        with pytest.raises(LookupError):
            await artifact_service.reclassify(
                mock_session,
                "art-x",
                user_id=TEST_USER_ID,
                course_code="CSIT302",
                week=4,
            )

    async def test_reclassify_unknown_course_raises(self, mock_session):
        """Unknown target course raises ValueError."""
        from unittest.mock import AsyncMock

        artifact = self._artifact()
        artifact_result = MagicMock()
        artifact_result.scalar_one_or_none.return_value = artifact
        course_result = MagicMock()
        course_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(side_effect=[artifact_result, course_result])

        with pytest.raises(ValueError):
            await artifact_service.reclassify(
                mock_session,
                "art-001",
                user_id=TEST_USER_ID,
                course_code="NOPE",
                week=4,
            )
