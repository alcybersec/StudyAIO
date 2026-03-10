"""Tests for the file serving API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
class TestViewArtifact:
    """Tests for GET /api/files/uploads/artifacts/{id}/view."""

    async def test_view_pdf_returns_correct_mime_type(self, async_client, tmp_path):
        """View endpoint serves PDF with application/pdf content type."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(pdf_file)
        mock_artifact.file_type = "pdf"
        mock_artifact.original_filename = "lecture.pdf"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-001/view")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        # Should NOT have content-disposition: attachment
        assert "attachment" not in response.headers.get("content-disposition", "")

    async def test_view_docx_returns_correct_mime_type(self, async_client, tmp_path):
        """View endpoint serves DOCX with correct content type."""
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"PK fake docx")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(docx_file)
        mock_artifact.file_type = "docx"
        mock_artifact.original_filename = "lecture.docx"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-002/view")

        assert response.status_code == 200
        content_type = response.headers["content-type"]
        assert "officedocument.wordprocessingml" in content_type

    async def test_view_pptx_returns_correct_mime_type(self, async_client, tmp_path):
        """View endpoint serves PPTX with correct content type."""
        pptx_file = tmp_path / "test.pptx"
        pptx_file.write_bytes(b"PK fake pptx")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(pptx_file)
        mock_artifact.file_type = "pptx"
        mock_artifact.original_filename = "lecture.pptx"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-003/view")

        assert response.status_code == 200
        content_type = response.headers["content-type"]
        assert "officedocument.presentationml" in content_type

    async def test_view_artifact_not_found(self, async_client):
        """View returns 404 when artifact doesn't exist."""
        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=None,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/nonexistent/view")

        assert response.status_code == 404
        assert "Artifact not found" in response.json()["detail"]

    async def test_view_artifact_file_missing_on_disk(self, async_client):
        """View returns 404 when artifact exists but file is gone."""
        mock_artifact = AsyncMock()
        mock_artifact.file_path = "/nonexistent/path/file.pdf"
        mock_artifact.file_type = "pdf"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-004/view")

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]

    async def test_view_unknown_type_falls_back_to_octet_stream(self, async_client, tmp_path):
        """View serves unknown file types as octet-stream."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("hello")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(txt_file)
        mock_artifact.file_type = "txt"
        mock_artifact.original_filename = "notes.txt"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-005/view")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"


@pytest.mark.asyncio
class TestDownloadArtifact:
    """Tests for GET /api/files/uploads/artifacts/{id} (download)."""

    async def test_download_returns_attachment_header(self, async_client, tmp_path):
        """Download endpoint includes content-disposition attachment."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf")

        mock_artifact = AsyncMock()
        mock_artifact.file_path = str(pdf_file)
        mock_artifact.file_type = "pdf"
        mock_artifact.original_filename = "CSIT302_Week5.pdf"

        with patch(
            "app.api.files.artifact_service.get_artifact",
            return_value=mock_artifact,
        ):
            response = await async_client.get("/api/files/uploads/artifacts/art-001")

        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")
