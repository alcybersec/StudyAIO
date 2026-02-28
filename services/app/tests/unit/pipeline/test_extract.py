"""Tests for extract pipeline stage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ExtractionError
from app.extractors.base import ExtractionResult, PageContent


class TestExtractInput:
    """Tests for chain-compatible input handling."""

    def test_extract_skips_duplicate(self):
        """Dict with duplicate status is passed through."""
        from app.pipeline.extract import extract_artifact

        input_value = {"artifact_id": "art-001", "status": "duplicate"}
        result = extract_artifact.run(input_value)

        assert result["status"] == "duplicate"

    def test_extract_skips_waiting_review(self):
        """Dict with waiting_review status is passed through."""
        from app.pipeline.extract import extract_artifact

        input_value = {"artifact_id": "art-001", "status": "waiting_review"}
        result = extract_artifact.run(input_value)

        assert result["status"] == "waiting_review"


class TestExtractStage:
    """Tests for _extract async function."""

    @patch("app.pipeline.extract.get_extractor")
    @patch("app.pipeline.extract.async_session_factory")
    async def test_extract_success(self, mock_session_factory, mock_get_extractor, tmp_path):
        """Successful extraction creates Extraction record."""
        from app.pipeline.extract import _extract

        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.file_path = str(tmp_path / "test.pdf")
        artifact.file_type = "pdf"

        session = AsyncMock()
        session.add = MagicMock()

        # First call: artifact query, second call: existing extraction check
        call_count = 0

        async def multi_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = artifact
            else:
                result.scalar_one_or_none.return_value = None
            return result

        session.execute = AsyncMock(side_effect=multi_execute)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        extractor = MagicMock()
        extractor.extract.return_value = ExtractionResult(
            pages=[PageContent(page_number=1, text="Hello", images=[])],
            metadata={"source_type": "pdf"},
            image_count=0,
            page_count=1,
        )
        mock_get_extractor.return_value = extractor

        with patch("app.pipeline.extract.settings") as mock_settings:
            mock_settings.extractions_dir = str(tmp_path / "extractions")

            result = await _extract("art-001")

        assert result["status"] == "extracted"
        assert result["page_count"] == 1

    @patch("app.pipeline.extract.async_session_factory")
    async def test_extract_not_found_raises(self, mock_session_factory):
        """Missing artifact raises ExtractionError."""
        from app.pipeline.extract import _extract

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(ExtractionError, match="not found"):
            await _extract("nonexistent-id")

    @patch("app.pipeline.extract.async_session_factory")
    async def test_extract_idempotent_skip(self, mock_session_factory):
        """Already-extracted artifact is skipped."""
        from app.pipeline.extract import _extract

        artifact = MagicMock()
        artifact.id = "art-001"

        existing_extraction = MagicMock()

        session = AsyncMock()
        call_count = 0

        async def multi_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = artifact
            else:
                result.scalar_one_or_none.return_value = existing_extraction
            return result

        session.execute = AsyncMock(side_effect=multi_execute)
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _extract("art-001")

        assert result["status"] == "already_extracted"
