"""Storage backend abstraction — local filesystem or S3-compatible.

Provides a unified interface for all file I/O in the application.
Use `get_storage()` to obtain the configured singleton.
"""

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

import structlog

from app.config import settings

logger = structlog.get_logger()

_storage_instance: "StorageBackend | None" = None


class StorageBackend(ABC):
    """Abstract base for all storage operations.

    Keys are relative paths like ``uploads/abc_lecture.pdf`` or
    ``extractions/id/images/img.png``.  Implementations map these to
    either a local directory tree or an S3 bucket prefix.
    """

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """Write *data* bytes to *key*."""

    @abstractmethod
    async def put_file(self, key: str, source_path: Path) -> None:
        """Copy a local file into storage at *key*."""

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Return the content of *key* as bytes."""

    @abstractmethod
    async def get_to_file(self, key: str, dest: Path) -> None:
        """Download *key* to a local file at *dest*."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if *key* exists in storage."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete *key*. No error if it doesn't exist."""

    @abstractmethod
    def get_url(self, key: str) -> str:
        """Return a URL suitable for serving *key* to clients.

        For local storage this is a relative API path; for S3 it may be
        a CDN URL or a presigned URL.
        """

    @abstractmethod
    async def ensure_dir(self, prefix: str) -> None:
        """Ensure *prefix* exists (meaningful only for local storage)."""

    # ------------------------------------------------------------------
    # Synchronous convenience wrappers for pipeline / extractor code
    # ------------------------------------------------------------------
    def put_sync(self, key: str, data: bytes) -> None:
        """Blocking wrapper around :meth:`put`."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an event loop already — schedule via run_async
            from app.core.database import run_async
            run_async(self.put(key, data))
        else:
            asyncio.run(self.put(key, data))

    def put_file_sync(self, key: str, source_path: Path) -> None:
        """Blocking wrapper around :meth:`put_file`."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            from app.core.database import run_async
            run_async(self.put_file(key, source_path))
        else:
            asyncio.run(self.put_file(key, source_path))

    def get_to_file_sync(self, key: str, dest: Path) -> None:
        """Blocking wrapper around :meth:`get_to_file`."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            from app.core.database import run_async
            run_async(self.get_to_file(key, dest))
        else:
            asyncio.run(self.get_to_file(key, dest))

    def exists_sync(self, key: str) -> bool:
        """Blocking wrapper around :meth:`exists`."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            from app.core.database import run_async
            return run_async(self.exists(key))
        else:
            return asyncio.run(self.exists(key))


# ======================================================================
# Local filesystem backend
# ======================================================================

class LocalStorageBackend(StorageBackend):
    """Store files under a local directory (``settings.data_dir``)."""

    def __init__(self, base_dir: str | None = None) -> None:
        self._base = Path(base_dir or settings.data_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        return self._base / key

    async def put(self, key: str, data: bytes) -> None:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    async def put_file(self, key: str, source_path: Path) -> None:
        dest = self._resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source_path), str(dest))

    async def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    async def get_to_file(self, key: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(self._resolve(key)), str(dest))

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()

    def get_url(self, key: str) -> str:
        # Serve via the /api/files/ endpoint
        return f"/api/files/{key}"

    async def ensure_dir(self, prefix: str) -> None:
        self._resolve(prefix).mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        """Expose the root directory (useful for ``FileResponse``)."""
        return self._base

    def resolve_path(self, key: str) -> Path:
        """Return absolute local path for a key (local-only helper)."""
        return self._resolve(key)


# ======================================================================
# S3-compatible backend
# ======================================================================

class S3StorageBackend(StorageBackend):
    """Store files in an S3-compatible bucket (AWS, MinIO, etc.)."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """Lazy boto3 client init (same pattern as Stripe)."""
        if self._client is None:
            import boto3

            kwargs: dict = {
                "region_name": settings.s3_region,
            }
            if settings.s3_access_key_id:
                kwargs["aws_access_key_id"] = settings.s3_access_key_id
                kwargs["aws_secret_access_key"] = settings.s3_secret_access_key.get_secret_value()
            if settings.s3_endpoint_url:
                kwargs["endpoint_url"] = settings.s3_endpoint_url
            self._client = boto3.client("s3", **kwargs)
        return self._client

    def _full_key(self, key: str) -> str:
        prefix = settings.s3_prefix.strip("/")
        return f"{prefix}/{key}" if prefix else key

    async def put(self, key: str, data: bytes) -> None:
        self._get_client().put_object(
            Bucket=settings.s3_bucket,
            Key=self._full_key(key),
            Body=data,
        )

    async def put_file(self, key: str, source_path: Path) -> None:
        self._get_client().upload_file(
            str(source_path),
            settings.s3_bucket,
            self._full_key(key),
        )

    async def get(self, key: str) -> bytes:
        resp = self._get_client().get_object(
            Bucket=settings.s3_bucket,
            Key=self._full_key(key),
        )
        return resp["Body"].read()

    async def get_to_file(self, key: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._get_client().download_file(
            settings.s3_bucket,
            self._full_key(key),
            str(dest),
        )

    async def exists(self, key: str) -> bool:
        try:
            self._get_client().head_object(
                Bucket=settings.s3_bucket,
                Key=self._full_key(key),
            )
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> None:
        try:
            self._get_client().delete_object(
                Bucket=settings.s3_bucket,
                Key=self._full_key(key),
            )
        except Exception:
            pass

    def get_url(self, key: str) -> str:
        if settings.cdn_base_url:
            return f"{settings.cdn_base_url.rstrip('/')}/{self._full_key(key)}"
        # Fall back to presigned URL (1 hour)
        return self._get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": self._full_key(key)},
            ExpiresIn=3600,
        )

    async def ensure_dir(self, prefix: str) -> None:
        # No-op — S3 doesn't have directories
        pass


# ======================================================================
# Singleton accessor
# ======================================================================

def get_storage() -> StorageBackend:
    """Return the configured storage backend singleton."""
    global _storage_instance
    if _storage_instance is None:
        backend = settings.storage_backend
        if backend == "s3":
            logger.info("storage_backend_init", backend="s3", bucket=settings.s3_bucket)
            _storage_instance = S3StorageBackend()
        else:
            logger.info("storage_backend_init", backend="local", base_dir=settings.data_dir)
            _storage_instance = LocalStorageBackend()
    return _storage_instance


def reset_storage() -> None:
    """Reset the singleton (useful for tests)."""
    global _storage_instance
    _storage_instance = None


def normalize_storage_key(path: str) -> str:
    """Strip the data_dir prefix from an absolute path to get a relative key.

    Handles both ``/app/data/uploads/foo.pdf`` and ``uploads/foo.pdf``.
    """
    data_prefix = settings.data_dir.rstrip("/") + "/"
    if path.startswith(data_prefix):
        return path[len(data_prefix):]
    return path
