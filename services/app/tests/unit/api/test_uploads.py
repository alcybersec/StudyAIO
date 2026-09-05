"""Tests for the uploads API endpoints."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services import artifact_service


@pytest.fixture
def artifact_store():
    """Dict-backed stand-in for the ``lecture_artifacts`` table.

    ``tests/unit`` runs the endpoints against an AsyncMock session, so a real
    SHA-256 lookup can never find anything and every upload would look new.
    This patches the two artifact_service calls the upload path makes so dedup
    behaves like the (sha256, user_id) unique constraint does in production.
    ``create_upload_artifact`` still runs for real, so the storage backend is
    genuinely written to and can be asserted on.

    Yields the {(sha256, user_id): artifact} mapping.
    """
    store: dict[tuple[str, str], object] = {}
    real_create = artifact_service.create_upload_artifact

    async def fake_check_duplicate(session, sha256, user_id):
        return store.get((sha256, user_id))

    async def recording_create(session, *, content, original_filename, sha256, user_id):
        artifact = await real_create(
            session,
            content=content,
            original_filename=original_filename,
            sha256=sha256,
            user_id=user_id,
        )
        store[(sha256, user_id)] = artifact
        return artifact

    with (
        patch.object(artifact_service, "check_duplicate", fake_check_duplicate),
        patch.object(artifact_service, "create_upload_artifact", recording_create),
    ):
        yield store


def _stored_uploads() -> list[Path]:
    """Every file the local storage backend currently holds under uploads/."""
    uploads = Path(settings.data_dir) / "uploads"
    if not uploads.exists():
        return []
    return sorted(p for p in uploads.iterdir() if p.is_file())


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
class TestUploadArtifactId:
    """Regression tests for issue #25 — the upload response carried a fake id.

    ``POST /api/uploads`` used to return the literal string ``"pending"``. The
    UI stored that as the card key and filtered the SSE stream by it, so no
    real pipeline event ever matched and the card never left ``processing``.
    """

    async def test_upload_returns_real_artifact_id(self, async_client, artifact_store):
        """The response carries the id of an artifact that actually exists."""
        with patch("app.api.uploads.run_pipeline", return_value=MagicMock(id="task-1")):
            response = await async_client.post(
                "/api/uploads",
                files={"file": ("lecture.pdf", b"%PDF-1.4 real id", "application/pdf")},
            )

        assert response.status_code == 201
        artifact_id = response.json()["artifact_id"]
        assert artifact_id != "pending"
        created = {a.id for a in artifact_store.values()}
        assert artifact_id in created

    async def test_duplicate_upload_returns_the_existing_artifact_id(
        self, async_client, artifact_store
    ):
        """The same bytes twice resolve to the same, already-existing artifact."""
        content = b"%PDF-1.4 uploaded twice"

        with patch("app.api.uploads.run_pipeline", return_value=MagicMock(id="task-1")):
            first = await async_client.post(
                "/api/uploads",
                files={"file": ("lecture.pdf", content, "application/pdf")},
            )
            second = await async_client.post(
                "/api/uploads",
                files={"file": ("lecture.pdf", content, "application/pdf")},
            )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["status"] == "processing"
        assert second.json()["status"] == "duplicate"
        assert second.json()["artifact_id"] == first.json()["artifact_id"]

    async def test_duplicate_upload_stores_nothing_and_costs_nothing(
        self, async_client, artifact_store
    ):
        """A duplicate leaves no orphan file and burns no upload quota."""
        content = b"%PDF-1.4 uploaded twice"

        with (
            patch("app.api.uploads.run_pipeline", return_value=MagicMock(id="task-1")),
            patch(
                "app.api.uploads.billing_service.record_usage", new_callable=AsyncMock
            ) as mock_usage,
        ):
            await async_client.post(
                "/api/uploads",
                files={"file": ("lecture.pdf", content, "application/pdf")},
            )
            after_first = _stored_uploads()

            await async_client.post(
                "/api/uploads",
                files={"file": ("lecture.pdf", content, "application/pdf")},
            )
            after_second = _stored_uploads()

        assert len(after_first) == 1
        assert after_second == after_first, "duplicate upload wrote a second copy to storage"
        assert mock_usage.await_count == 1, "duplicate upload counted against upload quota"

    async def test_pipeline_is_dispatched_with_the_real_artifact_id(
        self, async_client, artifact_store
    ):
        """The worker is handed the real id, so its events can carry it.

        Every ``publish_pipeline_event_sync`` call in the ingest stage keys off
        this value; the companion assertion that it is never ``"pending"``
        lives in ``tests/unit/pipeline/test_ingest.py``.
        """
        with patch("app.api.uploads.run_pipeline", return_value=MagicMock(id="task-1")) as mock_run:
            response = await async_client.post(
                "/api/uploads",
                files={"file": ("lecture.pdf", b"%PDF-1.4 dispatch", "application/pdf")},
            )

        artifact_id = response.json()["artifact_id"]
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["artifact_id"] == artifact_id
        assert mock_run.call_args.kwargs["artifact_id"] != "pending"

    async def test_retry_resolves_the_returned_artifact_id(self, async_client, artifact_store):
        """POST /uploads/{returned id}/retry finds the artifact instead of 404ing."""
        with patch("app.api.uploads.run_pipeline", return_value=MagicMock(id="task-1")):
            response = await async_client.post(
                "/api/uploads",
                files={"file": ("lecture.pdf", b"%PDF-1.4 retry me", "application/pdf")},
            )
        artifact_id = response.json()["artifact_id"]

        by_id = {a.id: a for a in artifact_store.values()}
        by_id[artifact_id].status = "failed"

        async def fake_get_artifact(session, requested_id, user_id=None):
            return by_id.get(requested_id)

        failed_run = MagicMock()
        failed_run.status = "failed"
        failed_run.stage = "summarize"

        with (
            patch("app.api.uploads.artifact_service.get_artifact", fake_get_artifact),
            patch(
                "app.api.uploads.pipeline_service.get_artifact_pipeline_runs",
                new_callable=AsyncMock,
                return_value=[failed_run],
            ),
            patch("app.api.uploads.resume_pipeline"),
        ):
            retry = await async_client.post(f"/api/uploads/{artifact_id}/retry")

        assert retry.status_code == 200, (
            "the id the upload returned does not resolve to an artifact"
        )
        assert retry.json()["artifact_id"] == artifact_id


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
