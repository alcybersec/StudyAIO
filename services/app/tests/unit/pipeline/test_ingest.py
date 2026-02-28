"""Tests for ingest pipeline stage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import DuplicateFileError


class TestIngestStage:
    """Tests for the _ingest async function."""

    @patch("app.pipeline.ingest.artifact_service")
    @patch("app.pipeline.ingest.async_session_factory")
    async def test_ingest_new_file(self, mock_session_factory, mock_art_svc):
        """Successful ingest returns artifact_id and status."""
        from app.pipeline.ingest import _ingest

        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.original_filename = "test.pdf"
        artifact.sha256 = "a" * 64
        mock_art_svc.ingest_file = AsyncMock(return_value=artifact)

        session = AsyncMock()
        session.add = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _ingest("/app/data/uploads/test.pdf")

        assert result["status"] == "ingested"
        assert result["artifact_id"] == "art-001"

    @patch("app.pipeline.ingest.artifact_service")
    @patch("app.pipeline.ingest.async_session_factory")
    async def test_ingest_duplicate_returns_existing(self, mock_session_factory, mock_art_svc):
        """Duplicate file returns existing artifact_id."""
        from app.pipeline.ingest import _ingest

        mock_art_svc.ingest_file = AsyncMock(side_effect=DuplicateFileError(
            sha256="a" * 64, existing_artifact_id="existing-001"
        ))

        session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _ingest("/app/data/uploads/test.pdf")

        assert result["status"] == "duplicate"
        assert result["artifact_id"] == "existing-001"
