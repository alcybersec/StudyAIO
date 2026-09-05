"""Tests for batch upload endpoint."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_upload_file(name: str, content: bytes = b"test pdf content"):
    """Create a tuple suitable for httpx multipart file upload."""
    return ("files", (name, io.BytesIO(content), "application/octet-stream"))


def _patch_existing_artifact(artifact_id: str):
    """Make every dedup lookup report an already-stored artifact.

    Batch upload now hashes and dedups in the request, so a duplicate is an
    artifact_service lookup hit rather than an exception out of run_pipeline.
    """
    existing = MagicMock()
    existing.id = artifact_id
    return patch(
        "app.api.uploads.artifact_service.check_duplicate",
        new_callable=AsyncMock,
        return_value=existing,
    )


@pytest.mark.asyncio
class TestBatchUpload:
    """Tests for POST /api/uploads/batch."""

    async def test_batch_upload_success(self, async_client, tmp_path):
        """Batch upload of two valid PDFs succeeds."""
        with patch("app.api.uploads.run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock(id="task-123")
            response = await async_client.post(
                "/api/uploads/batch",
                files=[
                    _make_upload_file("lecture1.pdf"),
                    _make_upload_file("lecture2.pdf"),
                ],
            )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["duplicates"] == 0
        assert data["failed"] == 0
        assert len(data["results"]) == 2
        for result in data["results"]:
            assert result["status"] == "processing"

    async def test_batch_upload_empty(self, async_client):
        """Batch upload with no files returns 400."""
        response = await async_client.post(
            "/api/uploads/batch",
            files=[],
        )
        # FastAPI may return 422 for missing required field or 400 from our check
        assert response.status_code in (400, 422)

    async def test_batch_upload_unsupported_type(self, async_client):
        """Batch upload rejects unsupported file types."""
        with patch("app.api.uploads.run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock(id="task-123")
            response = await async_client.post(
                "/api/uploads/batch",
                files=[_make_upload_file("notes.txt")],
            )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 1
        assert data["succeeded"] == 0
        assert data["failed"] == 1
        assert data["results"][0]["status"] == "error"
        assert "Unsupported file type" in data["results"][0]["error"]

    async def test_batch_upload_mixed(self, async_client):
        """Batch upload with mix of valid and invalid files."""
        with patch("app.api.uploads.run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock(id="task-123")
            response = await async_client.post(
                "/api/uploads/batch",
                files=[
                    _make_upload_file("lecture.pdf"),
                    _make_upload_file("notes.txt"),
                ],
            )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        # PDF should be processing
        pdf_result = next(r for r in data["results"] if r["filename"] == "lecture.pdf")
        assert pdf_result["status"] == "processing"
        # TXT should be error
        txt_result = next(r for r in data["results"] if r["filename"] == "notes.txt")
        assert txt_result["status"] == "error"

    async def test_batch_upload_duplicate(self, async_client):
        """A file already in the library is reported with its existing id."""
        with (
            patch("app.api.uploads.run_pipeline") as mock_pipeline,
            _patch_existing_artifact("existing-art-001"),
        ):
            response = await async_client.post(
                "/api/uploads/batch",
                files=[_make_upload_file("duplicate.pdf")],
            )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 1
        assert data["succeeded"] == 0
        assert data["duplicates"] == 1
        assert data["failed"] == 0
        assert data["results"][0]["status"] == "duplicate"
        assert data["results"][0]["artifact_id"] == "existing-art-001"
        # Dedup happens before dispatch, so no pipeline runs for a duplicate.
        mock_pipeline.assert_not_called()

    async def test_batch_upload_response_structure(self, async_client):
        """Batch upload response contains all expected fields."""
        with patch("app.api.uploads.run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock(id="task-456")
            response = await async_client.post(
                "/api/uploads/batch",
                files=[_make_upload_file("lecture.docx")],
            )

        assert response.status_code == 201
        data = response.json()
        # Top-level fields
        assert "total" in data
        assert "succeeded" in data
        assert "duplicates" in data
        assert "failed" in data
        assert "results" in data
        # Per-file result fields
        result = data["results"][0]
        assert "filename" in result
        assert "status" in result
        assert "artifact_id" in result
        assert "error" in result

    async def test_batch_upload_counts_correct(self, async_client):
        """Verify total = succeeded + failed + duplicates."""
        existing = MagicMock()
        existing.id = "dup-art"
        dedup_calls = 0

        async def fake_check_duplicate(session, sha256, user_id):
            # Second file of the batch is the one already in the library.
            nonlocal dedup_calls
            dedup_calls += 1
            return existing if dedup_calls == 2 else None

        pipeline_calls = 0

        def dispatch(file_path, user_id=None, artifact_id=None):
            nonlocal pipeline_calls
            pipeline_calls += 1
            if pipeline_calls == 1:
                return MagicMock(id="task-1")
            raise RuntimeError("Pipeline error")

        with (
            patch("app.api.uploads.run_pipeline", side_effect=dispatch),
            patch(
                "app.api.uploads.artifact_service.check_duplicate",
                fake_check_duplicate,
            ),
        ):
            response = await async_client.post(
                "/api/uploads/batch",
                files=[
                    _make_upload_file("file1.pdf", b"one"),
                    _make_upload_file("file2.pdf", b"two"),
                    _make_upload_file("file3.pdf", b"three"),
                    _make_upload_file("bad.txt"),  # unsupported ext
                ],
            )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 4
        assert data["succeeded"] == 1
        assert data["duplicates"] == 1
        assert data["failed"] == 2  # 1 pipeline error + 1 unsupported ext
        assert data["total"] == data["succeeded"] + data["duplicates"] + data["failed"]

    async def test_batch_upload_single_file(self, async_client):
        """Batch upload works with a single file."""
        with patch("app.api.uploads.run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock(id="task-single")
            response = await async_client.post(
                "/api/uploads/batch",
                files=[_make_upload_file("single.pptx")],
            )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 1
        assert data["succeeded"] == 1
        assert data["results"][0]["filename"] == "single.pptx"
        assert data["results"][0]["status"] == "processing"
        # The real artifact id, not the old "pending" placeholder (issue #25).
        artifact_id = data["results"][0]["artifact_id"]
        assert artifact_id
        assert artifact_id != "pending"
        assert mock_pipeline.call_args.kwargs["artifact_id"] == artifact_id
