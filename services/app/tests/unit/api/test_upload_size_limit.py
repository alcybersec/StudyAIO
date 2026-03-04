"""Tests for upload size limit enforcement."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.core.utils import read_upload_with_limit


class TestReadUploadWithLimit:
    """Tests for the chunked upload reader."""

    @pytest.mark.asyncio
    async def test_small_file_succeeds(self):
        """File under the limit is read successfully."""
        content = b"hello world"
        file = MagicMock()
        file.read = _async_reader(content)

        result = await read_upload_with_limit(file, max_bytes=1024)
        assert result == content

    @pytest.mark.asyncio
    async def test_oversized_file_returns_413(self):
        """File exceeding max_bytes raises HTTPException 413."""
        from fastapi import HTTPException

        content = b"x" * 2048
        file = MagicMock()
        file.read = _async_reader(content)

        with pytest.raises(HTTPException) as exc_info:
            await read_upload_with_limit(file, max_bytes=1024)
        assert exc_info.value.status_code == 413
        assert "too large" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_exact_limit_succeeds(self):
        """File exactly at the limit is accepted."""
        content = b"x" * 1024
        file = MagicMock()
        file.read = _async_reader(content)

        result = await read_upload_with_limit(file, max_bytes=1024)
        assert result == content

    @pytest.mark.asyncio
    async def test_empty_file_succeeds(self):
        """Empty file is accepted."""
        file = MagicMock()
        file.read = _async_reader(b"")

        result = await read_upload_with_limit(file, max_bytes=1024)
        assert result == b""


@pytest.mark.asyncio
class TestUploadEndpointSizeLimit:
    """Tests for upload endpoint size enforcement."""

    async def test_upload_oversized_file_returns_413(self, async_client):
        """POST /api/uploads with oversized file returns 413."""
        large_content = b"x" * (2 * 1024 * 1024)  # 2 MB

        with patch("app.config.settings.max_upload_size_mb", 1):
            response = await async_client.post(
                "/api/uploads",
                files={"file": ("test.pdf", large_content, "application/pdf")},
            )
        assert response.status_code == 413

    async def test_upload_small_file_succeeds(self, async_client):
        """POST /api/uploads with small file succeeds."""
        small_content = b"x" * 100  # 100 bytes

        mock_result = MagicMock()
        mock_result.id = "task-123"

        with (
            patch("app.config.settings.max_upload_size_mb", 1),
            patch("app.api.uploads.run_pipeline", return_value=mock_result),
        ):
            response = await async_client.post(
                "/api/uploads",
                files={"file": ("test.pdf", small_content, "application/pdf")},
            )
        assert response.status_code == 201

    async def test_courseops_oversized_file_returns_413(self, async_client):
        """POST /api/courseops/documents with oversized file returns 413."""
        large_content = b"x" * (2 * 1024 * 1024)

        with patch("app.config.settings.max_upload_size_mb", 1):
            response = await async_client.post(
                "/api/courseops/documents",
                params={"course_code": "TEST101", "document_type": "outline"},
                files={"file": ("doc.pdf", large_content, "application/pdf")},
            )
        assert response.status_code == 413


def _async_reader(content: bytes):
    """Create an async read function that mimics UploadFile.read() with chunking."""
    buf = BytesIO(content)

    async def read(size: int = -1) -> bytes:
        return buf.read(size)

    return read
