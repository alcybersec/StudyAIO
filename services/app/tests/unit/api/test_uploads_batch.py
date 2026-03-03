"""Tests for batch upload endpoint."""

import io
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import DuplicateFileError


def _make_upload_file(name: str, content: bytes = b"test pdf content"):
    """Create a tuple suitable for httpx multipart file upload."""
    return ("files", (name, io.BytesIO(content), "application/octet-stream"))


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
        """Batch upload handles duplicate files gracefully."""
        with patch("app.api.uploads.run_pipeline") as mock_pipeline:
            mock_pipeline.side_effect = DuplicateFileError(
                sha256="abc123" * 10 + "abcd",
                existing_artifact_id="existing-art-001",
            )
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
        with patch("app.api.uploads.run_pipeline") as mock_pipeline:
            call_count = 0

            def side_effect(file_path):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return MagicMock(id="task-1")
                elif call_count == 2:
                    raise DuplicateFileError(
                        sha256="d" * 64,
                        existing_artifact_id="dup-art",
                    )
                else:
                    raise RuntimeError("Pipeline error")

            mock_pipeline.side_effect = side_effect
            response = await async_client.post(
                "/api/uploads/batch",
                files=[
                    _make_upload_file("file1.pdf"),
                    _make_upload_file("file2.pdf"),
                    _make_upload_file("file3.pdf"),
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
        assert data["results"][0]["artifact_id"] == "pending"
