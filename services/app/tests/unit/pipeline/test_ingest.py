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

        mock_art_svc.ingest_file = AsyncMock(
            side_effect=DuplicateFileError(sha256="a" * 64, existing_artifact_id="existing-001")
        )

        session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _ingest("/app/data/uploads/test.pdf")

        assert result["status"] == "duplicate"
        assert result["artifact_id"] == "existing-001"


class TestIngestTaskEvents:
    """Regression tests for issue #25 — ingest published a fake artifact id.

    The task used to publish ``"pending"`` on start and ``"unknown"`` on
    failure. The Upload page filters the SSE stream by the id the API returned,
    so neither could ever match and the card never left ``processing``.
    """

    @patch("app.pipeline.ingest.publish_pipeline_event_sync")
    @patch("app.pipeline.ingest.run_async")
    @patch("app.pipeline.ingest._ingest")
    def test_events_carry_the_precreated_artifact_id(
        self, mock_ingest, mock_run_async, mock_publish
    ):
        """Both events published on a successful run carry the real id."""
        from app.pipeline.ingest import ingest_file

        mock_run_async.return_value = {
            "artifact_id": "art-real-001",
            "status": "ingested",
        }

        ingest_file(
            {
                "file_path": "uploads/art-real-001_lecture.pdf",
                "user_id": "user-001",
                "artifact_id": "art-real-001",
            }
        )

        published_ids = [call.args[0] for call in mock_publish.call_args_list]
        assert published_ids == ["art-real-001", "art-real-001"]
        assert "pending" not in published_ids

    @patch("app.pipeline.ingest.publish_pipeline_event_sync")
    @patch("app.pipeline.ingest.run_async")
    @patch("app.pipeline.ingest._ingest")
    def test_failure_event_carries_the_precreated_artifact_id(
        self, mock_ingest, mock_run_async, mock_publish
    ):
        """A crashed ingest reports the failure under the id the client holds."""
        from app.pipeline.ingest import ingest_file

        mock_run_async.side_effect = RuntimeError("worker exploded")

        with pytest.raises(RuntimeError):
            ingest_file(
                {
                    "file_path": "uploads/art-real-002_lecture.pdf",
                    "user_id": "user-001",
                    "artifact_id": "art-real-002",
                }
            )

        published_ids = [call.args[0] for call in mock_publish.call_args_list]
        assert published_ids == ["art-real-002", "art-real-002"]
        assert "unknown" not in published_ids

    @patch("app.pipeline.ingest.artifact_service")
    @patch("app.pipeline.ingest.async_session_factory")
    async def test_precreated_artifact_is_adopted_not_recreated(
        self, mock_session_factory, mock_art_svc
    ):
        """_ingest forwards the pre-created id so the service skips create."""
        from app.pipeline.ingest import _ingest

        artifact = MagicMock()
        artifact.id = "art-real-003"
        artifact.original_filename = "lecture.pdf"
        artifact.sha256 = "a" * 64
        mock_art_svc.ingest_file = AsyncMock(return_value=artifact)

        session = AsyncMock()
        session.add = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _ingest("uploads/x.pdf", user_id="user-001", artifact_id="art-real-003")

        assert result["artifact_id"] == "art-real-003"
        assert mock_art_svc.ingest_file.await_args.kwargs["artifact_id"] == "art-real-003"
