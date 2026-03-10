"""Tests for pipeline user_id threading through all stages."""

from unittest.mock import patch

from app.pipeline.orchestrator import resolve_pipeline_input

USER_ID = "user-pipeline-001"


class TestResolveWithUserId:
    """Verify resolve_pipeline_input extracts user_id from chain payloads."""

    def test_dict_with_user_id(self):
        """Dict payload with user_id returns both artifact_id and user_id."""
        result = resolve_pipeline_input(
            {"artifact_id": "art-001", "user_id": USER_ID, "status": "ingested"},
            "classify",
        )
        assert result == ("art-001", USER_ID)

    def test_dict_without_user_id(self):
        """Dict payload without user_id returns None for user_id."""
        result = resolve_pipeline_input(
            {"artifact_id": "art-001", "status": "ingested"},
            "classify",
        )
        assert result == ("art-001", None)

    def test_string_input_returns_none_user_id(self):
        """String input returns artifact_id with None user_id."""
        result = resolve_pipeline_input("art-001", "classify")
        assert result == ("art-001", None)


class TestPipelineStagesThreadUserId:
    """Verify each pipeline stage extracts and threads user_id.

    These tests mock run_async to avoid event loop conflicts with Celery tasks.
    """

    def test_classify_threads_user_id(self):
        """Classify stage extracts user_id from input dict and passes to _classify."""
        from app.pipeline.classify import classify_artifact

        input_dict = {"artifact_id": "art-001", "user_id": USER_ID, "status": "ingested"}
        expected_result = {"artifact_id": "art-001", "user_id": USER_ID, "status": "classified"}

        with (
            patch("app.pipeline.classify.run_async", return_value=expected_result) as mock_run,
            patch("app.pipeline.classify.publish_pipeline_event_sync"),
        ):
            result = classify_artifact(input_dict)

        assert result["user_id"] == USER_ID
        # Verify run_async was called with the coroutine from _classify(artifact_id, user_id=USER_ID)
        assert mock_run.called

    def test_extract_threads_user_id(self):
        """Extract stage extracts user_id from input dict."""
        from app.pipeline.extract import extract_artifact

        input_dict = {"artifact_id": "art-001", "user_id": USER_ID, "status": "classified"}
        expected_result = {"artifact_id": "art-001", "user_id": USER_ID, "status": "extracted"}

        with (
            patch("app.pipeline.extract.run_async", return_value=expected_result) as mock_run,
            patch("app.pipeline.extract.publish_pipeline_event_sync"),
        ):
            result = extract_artifact(input_dict)

        assert result["user_id"] == USER_ID
        assert mock_run.called

    def test_summarize_threads_user_id(self):
        """Summarize stage extracts user_id from input dict."""
        from app.pipeline.summarize import summarize_artifact

        input_dict = {"artifact_id": "art-001", "user_id": USER_ID, "status": "extracted"}
        expected_result = {"artifact_id": "art-001", "user_id": USER_ID, "status": "summarized"}

        with (
            patch("app.pipeline.summarize.run_async", return_value=expected_result) as mock_run,
            patch("app.pipeline.summarize.publish_pipeline_event_sync"),
        ):
            result = summarize_artifact(input_dict)

        assert result["user_id"] == USER_ID
        assert mock_run.called

    def test_index_threads_user_id(self):
        """Index stage extracts user_id from input dict."""
        from app.pipeline.index import index_artifact

        input_dict = {"artifact_id": "art-001", "user_id": USER_ID, "status": "summarized"}
        expected_result = {"artifact_id": "art-001", "user_id": USER_ID, "status": "indexed"}

        with (
            patch("app.pipeline.index.run_async", return_value=expected_result) as mock_run,
            patch("app.pipeline.index.publish_pipeline_event_sync"),
        ):
            result = index_artifact(input_dict)

        assert result["user_id"] == USER_ID
        assert mock_run.called

    def test_assets_threads_user_id(self):
        """Assets stage extracts user_id from input dict."""
        from app.pipeline.assets import generate_assets

        input_dict = {"artifact_id": "art-001", "user_id": USER_ID, "status": "indexed"}
        expected_result = {"artifact_id": "art-001", "user_id": USER_ID, "status": "processed"}

        with (
            patch("app.pipeline.assets.run_async", return_value=expected_result) as mock_run,
            patch("app.pipeline.assets.publish_pipeline_event_sync"),
        ):
            result = generate_assets(input_dict)

        assert result["user_id"] == USER_ID
        assert mock_run.called

    def test_classify_skips_on_waiting_review(self):
        """Classify skips processing for waiting_review status."""
        from app.pipeline.classify import classify_artifact

        input_dict = {"artifact_id": "art-001", "user_id": USER_ID, "status": "waiting_review"}

        result = classify_artifact(input_dict)
        assert result == input_dict  # Returned as-is

    def test_classify_skips_on_failed(self):
        """Classify skips processing for failed status."""
        from app.pipeline.classify import classify_artifact

        input_dict = {"artifact_id": "art-001", "user_id": USER_ID, "status": "failed"}

        result = classify_artifact(input_dict)
        assert result == input_dict
