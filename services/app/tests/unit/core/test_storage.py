"""Unit tests for the storage backend abstraction."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.storage import (
    LocalStorageBackend,
    S3StorageBackend,
    get_storage,
    normalize_storage_key,
    reset_storage,
)


# ======================================================================
# LocalStorageBackend
# ======================================================================

class TestLocalStorageBackend:
    """Tests for the local filesystem storage backend."""

    @pytest.fixture(autouse=True)
    def setup_local(self, tmp_path: Path):
        self.backend = LocalStorageBackend(base_dir=str(tmp_path))
        self.tmp = tmp_path

    @pytest.mark.asyncio
    async def test_put_and_get(self):
        """put() then get() returns the same bytes."""
        await self.backend.put("uploads/test.txt", b"hello world")
        data = await self.backend.get("uploads/test.txt")
        assert data == b"hello world"

    @pytest.mark.asyncio
    async def test_put_creates_parent_dirs(self):
        """put() creates intermediate directories."""
        await self.backend.put("deep/nested/path/file.bin", b"\x00\x01")
        assert (self.tmp / "deep" / "nested" / "path" / "file.bin").exists()

    @pytest.mark.asyncio
    async def test_put_file_and_get_to_file(self, tmp_path: Path):
        """put_file() + get_to_file() round-trips a file."""
        src = tmp_path / "source.pdf"
        src.write_bytes(b"pdf-content")

        await self.backend.put_file("uploads/copy.pdf", src)
        assert await self.backend.exists("uploads/copy.pdf")

        dest = tmp_path / "downloaded.pdf"
        await self.backend.get_to_file("uploads/copy.pdf", dest)
        assert dest.read_bytes() == b"pdf-content"

    @pytest.mark.asyncio
    async def test_exists_false_for_missing(self):
        """exists() returns False for a missing key."""
        assert await self.backend.exists("no/such/key") is False

    @pytest.mark.asyncio
    async def test_delete(self):
        """delete() removes a key."""
        await self.backend.put("tmp/del.txt", b"data")
        assert await self.backend.exists("tmp/del.txt")
        await self.backend.delete("tmp/del.txt")
        assert await self.backend.exists("tmp/del.txt") is False

    @pytest.mark.asyncio
    async def test_delete_missing_no_error(self):
        """delete() on a nonexistent key does not raise."""
        await self.backend.delete("nope/nothing")  # should not raise

    def test_get_url(self):
        """get_url() returns a relative API path."""
        url = self.backend.get_url("uploads/abc.pdf")
        assert url == "/api/files/uploads/abc.pdf"

    def test_resolve_path(self):
        """resolve_path() returns absolute path under base_dir."""
        p = self.backend.resolve_path("uploads/foo.pdf")
        assert p == self.tmp / "uploads" / "foo.pdf"

    @pytest.mark.asyncio
    async def test_ensure_dir(self):
        """ensure_dir() creates the prefix directory."""
        await self.backend.ensure_dir("extractions/some-id/images")
        assert (self.tmp / "extractions" / "some-id" / "images").is_dir()


# ======================================================================
# S3StorageBackend (mocked boto3)
# ======================================================================

@pytest.fixture()
def _s3_settings():
    """Patch storage settings for S3 tests."""
    with patch("app.core.storage.settings") as mock_settings:
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.s3_region = "us-east-1"
        mock_settings.s3_access_key_id = "AKID"
        mock_settings.s3_secret_access_key = MagicMock()
        mock_settings.s3_secret_access_key.get_secret_value.return_value = "secret"
        mock_settings.s3_endpoint_url = ""
        mock_settings.s3_prefix = ""
        mock_settings.cdn_base_url = ""
        mock_settings.data_dir = "/app/data"
        yield mock_settings


@pytest.mark.usefixtures("_s3_settings")
class TestS3StorageBackend:
    """Tests for the S3 storage backend with mocked boto3."""

    @pytest.fixture(autouse=True)
    def setup_s3(self, _s3_settings):
        self.mock_client = MagicMock()
        self.backend = S3StorageBackend()
        self.backend._client = self.mock_client
        self.settings = _s3_settings

    @pytest.mark.asyncio
    async def test_put_calls_put_object(self):
        """put() delegates to boto3 put_object."""
        await self.backend.put("uploads/file.pdf", b"pdf-bytes")
        self.mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="uploads/file.pdf",
            Body=b"pdf-bytes",
        )

    @pytest.mark.asyncio
    async def test_get_reads_body(self):
        """get() returns the Body stream contents."""
        body_mock = MagicMock()
        body_mock.read.return_value = b"returned-data"
        self.mock_client.get_object.return_value = {"Body": body_mock}

        data = await self.backend.get("uploads/file.pdf")
        assert data == b"returned-data"

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """exists() returns True when head_object succeeds."""
        self.mock_client.head_object.return_value = {}
        assert await self.backend.exists("uploads/file.pdf") is True

    @pytest.mark.asyncio
    async def test_exists_false_on_error(self):
        """exists() returns False when head_object raises."""
        self.mock_client.head_object.side_effect = Exception("404")
        assert await self.backend.exists("missing.pdf") is False

    @pytest.mark.asyncio
    async def test_prefix_applied(self):
        """S3 prefix is prepended to keys."""
        self.settings.s3_prefix = "studyaio-data"
        await self.backend.put("uploads/x.pdf", b"data")
        self.mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="studyaio-data/uploads/x.pdf",
            Body=b"data",
        )

    def test_get_url_with_cdn(self):
        """get_url() uses CDN base URL when configured."""
        self.settings.cdn_base_url = "https://cdn.example.com"
        url = self.backend.get_url("uploads/file.pdf")
        assert url == "https://cdn.example.com/uploads/file.pdf"

    def test_get_url_presigned_fallback(self):
        """get_url() generates presigned URL when no CDN."""
        self.settings.cdn_base_url = ""
        self.mock_client.generate_presigned_url.return_value = "https://s3.example.com/presigned"
        url = self.backend.get_url("uploads/file.pdf")
        assert url == "https://s3.example.com/presigned"


# ======================================================================
# Singleton & helpers
# ======================================================================

class TestGetStorage:
    """Tests for get_storage() factory and normalize_storage_key()."""

    def setup_method(self):
        reset_storage()

    def teardown_method(self):
        reset_storage()

    @patch("app.core.storage.settings")
    def test_default_is_local(self, mock_settings):
        """Default storage_backend='local' returns LocalStorageBackend."""
        mock_settings.storage_backend = "local"
        mock_settings.data_dir = "/tmp/test-storage"
        backend = get_storage()
        assert isinstance(backend, LocalStorageBackend)

    @patch("app.core.storage.settings")
    def test_s3_returns_s3_backend(self, mock_settings):
        """storage_backend='s3' returns S3StorageBackend."""
        mock_settings.storage_backend = "s3"
        mock_settings.s3_bucket = "bucket"
        mock_settings.s3_region = "us-east-1"
        backend = get_storage()
        assert isinstance(backend, S3StorageBackend)

    def test_normalize_strips_data_dir(self):
        """normalize_storage_key() strips data_dir prefix."""
        key = normalize_storage_key("/app/data/uploads/abc.pdf")
        assert key == "uploads/abc.pdf"

    def test_normalize_keeps_relative(self):
        """normalize_storage_key() keeps already-relative paths."""
        key = normalize_storage_key("uploads/abc.pdf")
        assert key == "uploads/abc.pdf"
