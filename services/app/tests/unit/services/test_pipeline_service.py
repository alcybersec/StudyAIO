"""Tests for pipeline_service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import pipeline_service


@pytest.mark.asyncio
class TestGetRecentActivity:
    """Tests for get_recent_activity."""

    async def test_returns_empty_list(self, mock_session):
        """get_recent_activity returns empty list when no runs exist."""
        mock_result = MagicMock()
        mock_result.unique.return_value.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await pipeline_service.get_recent_activity(mock_session)
        assert result == []

    async def test_returns_activity_with_artifact_info(self, mock_session):
        """get_recent_activity includes artifact filename in results."""
        from datetime import datetime

        mock_artifact = MagicMock()
        mock_artifact.original_filename = "lecture.pdf"

        mock_run = MagicMock()
        mock_run.id = "run-001"
        mock_run.artifact_id = "art-001"
        mock_run.artifact = mock_artifact
        mock_run.stage = "ingest"
        mock_run.status = "completed"
        mock_run.started_at = datetime(2024, 1, 1)
        mock_run.completed_at = datetime(2024, 1, 1, 0, 0, 5)
        mock_run.duration_ms = 5000

        mock_result = MagicMock()
        mock_result.unique.return_value.scalars.return_value.all.return_value = [mock_run]
        mock_session.execute.return_value = mock_result

        result = await pipeline_service.get_recent_activity(mock_session)
        assert len(result) == 1
        assert result[0]["filename"] == "lecture.pdf"
        assert result[0]["stage"] == "ingest"


@pytest.mark.asyncio
class TestGetArtifactPipelineRuns:
    """Tests for get_artifact_pipeline_runs."""

    async def test_returns_runs_for_artifact(self, mock_session):
        """get_artifact_pipeline_runs returns runs for the artifact."""
        mock_run = MagicMock()
        mock_run.id = "run-001"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_run]
        mock_session.execute.return_value = mock_result

        result = await pipeline_service.get_artifact_pipeline_runs(
            mock_session, "art-001"
        )
        assert len(result) == 1
        assert result[0].id == "run-001"
