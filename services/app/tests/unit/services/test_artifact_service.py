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
