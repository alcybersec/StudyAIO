"""Tests for pipeline orchestrator."""

from unittest.mock import MagicMock, patch

import pytest

from app.pipeline.orchestrator import resolve_pipeline_input


class TestResolvePipelineInput:
    """Tests for resolve_pipeline_input()."""

    def test_string_input_returns_artifact_id(self):
        """Plain string is returned as artifact_id."""
        result = resolve_pipeline_input("art-001", "classify")
        assert result == "art-001"

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        result = resolve_pipeline_input("", "classify")
        assert result is None

    def test_dict_with_artifact_id(self):
        """Dict with good status returns artifact_id."""
        result = resolve_pipeline_input(
            {"artifact_id": "art-001", "status": "ingested"}, "classify"
        )
        assert result == "art-001"

    def test_dict_with_duplicate_stops(self):
        """Dict with duplicate status returns None."""
        result = resolve_pipeline_input(
            {"artifact_id": "art-001", "status": "duplicate"}, "classify"
        )
        assert result is None

    def test_dict_with_waiting_review_stops(self):
        """Dict with waiting_review status returns None."""
        result = resolve_pipeline_input(
            {"artifact_id": "art-001", "status": "waiting_review"}, "extract"
        )
        assert result is None

    def test_dict_with_failed_stops(self):
        """Dict with failed status returns None."""
        result = resolve_pipeline_input({"artifact_id": "art-001", "status": "failed"}, "summarize")
        assert result is None

    def test_dict_with_classified_continues(self):
        """Dict with classified status returns artifact_id."""
        result = resolve_pipeline_input(
            {"artifact_id": "art-001", "status": "classified"}, "extract"
        )
        assert result == "art-001"


class TestRunPipeline:
    """Tests for run_pipeline()."""

    @patch("app.pipeline.orchestrator.ingest_file")
    @patch("app.pipeline.orchestrator.classify_artifact")
    @patch("app.pipeline.orchestrator.extract_artifact")
    @patch("app.pipeline.orchestrator.summarize_artifact")
    def test_run_pipeline_builds_chain(
        self, mock_summarize, mock_extract, mock_classify, mock_ingest
    ):
        """run_pipeline dispatches a 4-stage chain."""
        from app.pipeline.orchestrator import run_pipeline

        # Mock the .s() method for each task
        mock_ingest.s = MagicMock()
        mock_classify.s = MagicMock()
        mock_extract.s = MagicMock()
        mock_summarize.s = MagicMock()

        with patch("app.pipeline.orchestrator.chain") as mock_chain:
            mock_chain.return_value.apply_async.return_value = MagicMock(id="chain-001")

            run_pipeline("/app/data/uploads/test.pdf")

            mock_chain.assert_called_once()
            mock_chain.return_value.apply_async.assert_called_once()


class TestResumePipeline:
    """Tests for resume_pipeline()."""

    def test_invalid_stage_raises(self):
        """Unknown stage raises ValueError."""
        from app.pipeline.orchestrator import resume_pipeline

        with pytest.raises(ValueError, match="Unknown stage"):
            resume_pipeline("art-001", "nonexistent")

    @patch("app.pipeline.orchestrator.summarize_artifact")
    def test_resume_from_summarize_single_task(self, mock_summarize):
        """Resuming from summarize dispatches single task."""
        from app.pipeline import orchestrator

        # Must also patch _STAGES since it captured the original reference
        mock_summarize.apply_async.return_value = MagicMock(id="task-001")
        with patch.dict(orchestrator._STAGES, {"summarize": [mock_summarize]}):
            orchestrator.resume_pipeline("art-001", "summarize")

        mock_summarize.apply_async.assert_called_once_with(args=["art-001"])
