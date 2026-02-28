"""Tests for index pipeline stage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import IndexingError


class TestIndexInput:
    """Tests for chain-compatible input handling."""

    def test_index_skips_duplicate(self):
        """Dict with duplicate status is passed through."""
        from app.pipeline.index import index_artifact

        input_value = {"artifact_id": "art-001", "status": "duplicate"}
        result = index_artifact.run(input_value)

        assert result["status"] == "duplicate"

    def test_index_skips_waiting_review(self):
        """Dict with waiting_review status is passed through."""
        from app.pipeline.index import index_artifact

        input_value = {"artifact_id": "art-001", "status": "waiting_review"}
        result = index_artifact.run(input_value)

        assert result["status"] == "waiting_review"

    def test_index_skips_failed(self):
        """Dict with failed status is passed through."""
        from app.pipeline.index import index_artifact

        input_value = {"artifact_id": "art-001", "status": "failed"}
        result = index_artifact.run(input_value)

        assert result["status"] == "failed"

    def test_index_accepts_string(self):
        """String input is treated as artifact_id (will fail without DB)."""
        from app.pipeline.index import index_artifact

        with pytest.raises(Exception):
            index_artifact.run("art-001")


class TestIndexStage:
    """Tests for _index async function."""

    @patch("app.pipeline.index.get_embedding_provider")
    @patch("app.pipeline.index.index_service")
    @patch("app.pipeline.index.async_session_factory")
    @pytest.mark.asyncio
    async def test_index_success(
        self, mock_session_factory, mock_index_svc, mock_get_provider
    ):
        """Successful indexing creates chunks and returns indexed status."""
        from app.pipeline.index import _index

        # Mock artifact
        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.sha256 = "a" * 64

        # Mock extraction
        extraction = MagicMock()
        extraction.manifest_json = {
            "pages": [{"page_number": 1, "text": "Test content", "images": []}],
        }

        session = AsyncMock()
        session.add = MagicMock()

        # First execute returns artifact, second returns extraction
        mock_result_artifact = MagicMock()
        mock_result_artifact.scalar_one_or_none.return_value = artifact

        mock_result_extraction = MagicMock()
        mock_result_extraction.scalar_one_or_none.return_value = extraction

        session.execute = AsyncMock(
            side_effect=[mock_result_artifact, mock_result_extraction]
        )

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock embedding provider
        provider = MagicMock()
        mock_get_provider.return_value = provider

        # Mock index service
        chunk_record = MagicMock()
        mock_index_svc.index_artifact_chunks = AsyncMock(return_value=[chunk_record])

        result = await _index("art-001")

        assert result["status"] == "indexed"
        assert result["artifact_id"] == "art-001"
        assert result["chunk_count"] == 1

    @patch("app.pipeline.index.async_session_factory")
    @pytest.mark.asyncio
    async def test_index_artifact_not_found_raises(self, mock_session_factory):
        """Missing artifact raises IndexingError."""
        from app.pipeline.index import _index

        session = AsyncMock()
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(IndexingError, match="not found"):
            await _index("art-001")

    @patch("app.pipeline.index.async_session_factory")
    @pytest.mark.asyncio
    async def test_index_no_extraction_raises(self, mock_session_factory):
        """Missing extraction raises IndexingError."""
        from app.pipeline.index import _index

        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.sha256 = "a" * 64

        session = AsyncMock()
        session.add = MagicMock()

        mock_result_artifact = MagicMock()
        mock_result_artifact.scalar_one_or_none.return_value = artifact

        mock_result_extraction = MagicMock()
        mock_result_extraction.scalar_one_or_none.return_value = None

        session.execute = AsyncMock(
            side_effect=[mock_result_artifact, mock_result_extraction]
        )

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(IndexingError, match="No extraction found"):
            await _index("art-001")

    @patch("app.pipeline.index.async_session_factory")
    @pytest.mark.asyncio
    async def test_index_empty_manifest_raises(self, mock_session_factory):
        """Empty manifest raises IndexingError."""
        from app.pipeline.index import _index

        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.sha256 = "a" * 64

        extraction = MagicMock()
        extraction.manifest_json = {}

        session = AsyncMock()
        session.add = MagicMock()

        mock_result_artifact = MagicMock()
        mock_result_artifact.scalar_one_or_none.return_value = artifact

        mock_result_extraction = MagicMock()
        mock_result_extraction.scalar_one_or_none.return_value = extraction

        session.execute = AsyncMock(
            side_effect=[mock_result_artifact, mock_result_extraction]
        )

        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(IndexingError, match="no pages"):
            await _index("art-001")
