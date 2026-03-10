"""Tests for the uploads API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
class TestUploadFile:
    """Tests for POST /api/uploads."""

    async def test_upload_unsupported_file_type(self, async_client):
        """Upload rejects unsupported file types."""
        response = await async_client.post(
            "/api/uploads",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    async def test_upload_pdf_dispatches_pipeline(self, async_client):
        """Upload a PDF triggers pipeline dispatch."""
        mock_result = MagicMock()
        mock_result.id = "celery-task-123"

        with patch(
            "app.api.uploads.run_pipeline",
            return_value=mock_result,
        ):
            response = await async_client.post(
                "/api/uploads",
                files={"file": ("lecture.pdf", b"%PDF-1.4 content", "application/pdf")},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "lecture.pdf"
        assert data["status"] == "processing"
        assert data["pipeline_task_id"] == "celery-task-123"


@pytest.mark.asyncio
class TestGetUploadStatus:
    """Tests for GET /api/uploads/{artifact_id}/status."""

    async def test_get_status_returns_pipeline_runs(self, async_client):
        """Status endpoint returns pipeline run records."""
        mock_run = AsyncMock()
        mock_run.id = "run-001"
        mock_run.artifact_id = "art-001"
        mock_run.stage = "ingest"
        mock_run.status = "completed"
        mock_run.error_message = None
        mock_run.started_at = datetime(2024, 1, 1)
        mock_run.completed_at = datetime(2024, 1, 1, 0, 0, 5)
        mock_run.duration_ms = 5000

        with patch(
            "app.api.uploads.pipeline_service.get_artifact_pipeline_runs",
            new_callable=AsyncMock,
            return_value=[mock_run],
        ):
            response = await async_client.get("/api/uploads/art-001/status")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["stage"] == "ingest"
        assert data[0]["status"] == "completed"

    async def test_get_status_artifact_not_found(self, async_client):
        """Status endpoint returns 404 for unknown artifact."""
        with (
            patch(
                "app.api.uploads.pipeline_service.get_artifact_pipeline_runs",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.api.uploads.artifact_service.get_artifact",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            response = await async_client.get("/api/uploads/unknown-id/status")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestRetryPipeline:
    """Tests for POST /api/uploads/{artifact_id}/retry."""

    async def test_retry_not_found(self, async_client):
        """Retry returns 404 for unknown artifact."""
        with patch(
            "app.api.uploads.artifact_service.get_artifact",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.post("/api/uploads/unknown-id/retry")

        assert response.status_code == 404

    async def test_retry_not_failed_returns_400(self, async_client):
        """Retry returns 400 if artifact is not failed."""
        mock_artifact = MagicMock()
        mock_artifact.status = "processed"

        with patch(
            "app.api.uploads.artifact_service.get_artifact",
            new_callable=AsyncMock,
            return_value=mock_artifact,
        ):
            response = await async_client.post("/api/uploads/art-001/retry")

        assert response.status_code == 400
        assert "not 'failed'" in response.json()["detail"]

    async def test_retry_failed_resumes_pipeline(self, async_client, mock_session):
        """Retry dispatches resume_pipeline for failed artifact."""
        mock_artifact = MagicMock()
        mock_artifact.status = "failed"

        mock_run = MagicMock()
        mock_run.status = "failed"
        mock_run.stage = "summarize"

        with (
            patch(
                "app.api.uploads.artifact_service.get_artifact",
                new_callable=AsyncMock,
                return_value=mock_artifact,
            ),
            patch(
                "app.api.uploads.pipeline_service.get_artifact_pipeline_runs",
                new_callable=AsyncMock,
                return_value=[mock_run],
            ),
            patch(
                "app.api.uploads.resume_pipeline",
            ) as mock_resume,
        ):
            response = await async_client.post("/api/uploads/art-001/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["retrying_from_stage"] == "summarize"
        assert data["status"] == "extracted"
        mock_resume.assert_called_once_with(
            "art-001", from_stage="summarize", user_id="00000000-0000-0000-0000-000000000001"
        )

    async def test_retry_no_failed_runs_returns_400(self, async_client):
        """Retry returns 400 when no failed runs exist."""
        mock_artifact = MagicMock()
        mock_artifact.status = "failed"

        mock_run = MagicMock()
        mock_run.status = "completed"
        mock_run.stage = "ingest"

        with (
            patch(
                "app.api.uploads.artifact_service.get_artifact",
                new_callable=AsyncMock,
                return_value=mock_artifact,
            ),
            patch(
                "app.api.uploads.pipeline_service.get_artifact_pipeline_runs",
                new_callable=AsyncMock,
                return_value=[mock_run],
            ),
        ):
            response = await async_client.post("/api/uploads/art-001/retry")

        assert response.status_code == 400
        assert "No failed pipeline run" in response.json()["detail"]
