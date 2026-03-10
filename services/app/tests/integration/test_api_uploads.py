"""Integration tests for upload API endpoints."""

from unittest.mock import patch

import pytest

from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.pipeline_run import PipelineRun


@pytest.mark.asyncio(loop_scope="session")
class TestUploadEndpoints:
    """Test /api/uploads endpoints against a real database."""

    async def test_upload_creates_artifact(self, integration_client, db_session):
        """POST /api/uploads saves file and dispatches pipeline."""
        pdf_content = b"%PDF-1.4 minimal test content"

        with patch("app.api.uploads.run_pipeline") as mock_run:
            mock_run.return_value = type("R", (), {"id": "task-123"})()
            resp = await integration_client.post(
                "/api/uploads",
                files={"file": ("lecture.pdf", pdf_content, "application/pdf")},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "lecture.pdf"
        assert data["status"] == "processing"
        mock_run.assert_called_once()

    async def test_upload_unsupported_type(self, integration_client):
        """POST /api/uploads rejects unsupported file types."""
        resp = await integration_client.post(
            "/api/uploads",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    async def test_get_status_returns_pipeline_runs(self, integration_client, db_session):
        """GET /api/uploads/{id}/status returns pipeline runs."""
        artifact = LectureArtifact(
            id=generate_id(),
            original_filename="test.pdf",
            file_path="/data/uploads/test.pdf",
            file_type="pdf",
            sha256="c" * 64,
            file_size_bytes=1024,
            status="classified",
        )
        db_session.add(artifact)

        run = PipelineRun(
            id=generate_id(),
            artifact_id=artifact.id,
            stage="ingest",
            status="completed",
        )
        db_session.add(run)
        await db_session.flush()

        resp = await integration_client.get(f"/api/uploads/{artifact.id}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["stage"] == "ingest"
        assert data[0]["status"] == "completed"

    async def test_get_status_nonexistent_returns_404(self, integration_client):
        """GET /api/uploads/{id}/status returns 404 for nonexistent artifact."""
        resp = await integration_client.get("/api/uploads/nonexistent-id/status")
        assert resp.status_code == 404

    async def test_retry_resets_failed_artifact(self, integration_client, db_session):
        """POST /api/uploads/{id}/retry resets status and dispatches pipeline."""
        artifact = LectureArtifact(
            id=generate_id(),
            original_filename="fail.pdf",
            file_path="/data/uploads/fail.pdf",
            file_type="pdf",
            sha256="d" * 64,
            file_size_bytes=1024,
            status="failed",
        )
        db_session.add(artifact)

        run = PipelineRun(
            id=generate_id(),
            artifact_id=artifact.id,
            stage="extract",
            status="failed",
            error_message="timeout",
        )
        db_session.add(run)
        await db_session.flush()

        with patch("app.api.uploads.resume_pipeline"):
            resp = await integration_client.post(f"/api/uploads/{artifact.id}/retry")

        assert resp.status_code == 200
        data = resp.json()
        assert data["retrying_from_stage"] == "extract"
        assert data["status"] == "classified"
