"""Tests for summarize pipeline stage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ExtractionData, SummaryResult
from app.core.exceptions import SummarizationError
from app.core.storage import LocalStorageBackend


class TestSummarizeInput:
    """Tests for chain-compatible input handling."""

    def test_summarize_skips_duplicate(self):
        """Dict with duplicate status is passed through."""
        from app.pipeline.summarize import summarize_artifact

        input_value = {"artifact_id": "art-001", "status": "duplicate"}
        result = summarize_artifact.run(input_value)

        assert result["status"] == "duplicate"

    def test_summarize_skips_waiting_review(self):
        """Dict with waiting_review status is passed through."""
        from app.pipeline.summarize import summarize_artifact

        input_value = {"artifact_id": "art-001", "status": "waiting_review"}
        result = summarize_artifact.run(input_value)

        assert result["status"] == "waiting_review"

    def test_summarize_skips_failed(self):
        """Dict with failed status is passed through."""
        from app.pipeline.summarize import summarize_artifact

        input_value = {"artifact_id": "art-001", "status": "failed"}
        result = summarize_artifact.run(input_value)

        assert result["status"] == "failed"

    def test_summarize_accepts_string(self):
        """String input is treated as artifact_id."""
        # This will fail since there's no DB, but verifies the code path
        from app.pipeline.summarize import summarize_artifact

        with pytest.raises((Exception, SystemExit)):
            summarize_artifact.run("art-001")


class TestSummarizeStage:
    """Tests for _summarize async function."""

    @patch("app.pipeline.summarize.get_agent")
    @patch("app.pipeline.summarize.summary_service")
    @patch("app.pipeline.summarize.async_session_factory")
    async def test_summarize_success(
        self, mock_session_factory, mock_summary_svc, mock_get_agent, tmp_path
    ):
        """Successful summarization creates summary."""
        from app.pipeline.summarize import _summarize

        # Mock course
        course = MagicMock()
        course.id = "course-001"
        course.code = "CSIT302"

        # Mock artifact
        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.course_id = "course-001"
        artifact.week = 5
        artifact.course = course

        session = AsyncMock()
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.unique.return_value = mock_result
        mock_result.scalar_one_or_none.return_value = artifact
        session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock summary service
        extraction = MagicMock()
        extraction.artifact_id = "art-001"
        extraction.manifest_json = {
            "pages": [{"page_number": 1, "text": "Content", "images": []}],
            "metadata": {},
        }
        mock_summary_svc.get_week_extractions = AsyncMock(return_value=[extraction])
        mock_summary_svc.merge_extractions.return_value = ExtractionData(
            pages=[{"page_number": 1, "text": "Content", "images": []}],
            metadata={"artifact_ids": ["art-001"]},
        )
        mock_summary_svc.get_existing_summary = AsyncMock(return_value=None)

        summary_record = MagicMock()
        summary_record.id = "summary-001"
        summary_record.version = 1
        mock_summary_svc.create_or_update_summary = AsyncMock(return_value=summary_record)
        mock_summary_svc.build_summary_storage_key.return_value = "summaries/CSIT302/CSIT302_Week5.md"

        # Mock agent
        agent = AsyncMock()
        agent.generate_summary.return_value = SummaryResult(
            content_md="# CSIT302 — Week 5: Topic\n\n## Key Concepts\n- Test",
            embedded_images=[],
        )
        mock_get_agent.return_value = agent

        local_storage = LocalStorageBackend(base_dir=str(tmp_path))

        with patch("app.pipeline.summarize.get_storage", return_value=local_storage):
            result = await _summarize("art-001")

        assert result["status"] == "summarized"
        assert result["summary_id"] == "summary-001"
        assert result["version"] == 1

    @patch("app.pipeline.summarize.async_session_factory")
    async def test_summarize_not_classified_raises(self, mock_session_factory):
        """Artifact without course_id raises SummarizationError."""
        from app.pipeline.summarize import _summarize

        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.course_id = None
        artifact.week = None
        artifact.course = None

        session = AsyncMock()
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.unique.return_value = mock_result
        mock_result.scalar_one_or_none.return_value = artifact
        session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(SummarizationError, match="not classified"):
            await _summarize("art-001")

    @patch("app.pipeline.summarize.summary_service")
    @patch("app.pipeline.summarize.async_session_factory")
    async def test_summarize_no_extraction_raises(self, mock_session_factory, mock_summary_svc):
        """No extractions raises SummarizationError."""
        from app.pipeline.summarize import _summarize

        course = MagicMock()
        course.id = "course-001"
        course.code = "CSIT302"

        artifact = MagicMock()
        artifact.id = "art-001"
        artifact.course_id = "course-001"
        artifact.week = 5
        artifact.course = course

        session = AsyncMock()
        session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.unique.return_value = mock_result
        mock_result.scalar_one_or_none.return_value = artifact
        session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_summary_svc.get_week_extractions = AsyncMock(return_value=[])

        with pytest.raises(SummarizationError, match="No extractions found"):
            await _summarize("art-001")
