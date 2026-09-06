"""Shared utility functions."""

import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile
from uuid_extensions import uuid7


def generate_id() -> str:
    """Generate a time-sortable UUID7 as a string."""
    return str(uuid7())


def compute_sha256(file_path: str | Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_sha256_from_bytes(data: bytes) -> str:
    """Compute SHA-256 hash from bytes."""
    return hashlib.sha256(data).hexdigest()


def sanitize_filename(filename: str) -> str:
    """Remove problematic characters from a filename."""
    keepchars = " ._-()"
    return "".join(c for c in filename if c.isalnum() or c in keepchars).strip()


# Leading-byte signatures accepted for each supported extension. A PDF starts
# with "%PDF"; DOCX/PPTX are ZIP archives, so they start with one of the three
# valid ZIP signatures: a local file header (the usual case), an empty archive,
# or a spanned/split marker.
_ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_CONTENT_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".docx": _ZIP_MAGIC,
    ".pptx": _ZIP_MAGIC,
}


def validate_upload_content(ext: str, content: bytes) -> None:
    """Reject a file whose leading bytes do not match its extension.

    The extension check alone lets a shell script or HTML named ``evil.pdf``
    through; this checks the magic bytes so a mislabelled file is rejected at
    the edge instead of failing deep in the pipeline. ``ext`` must already be
    lowercased. Raises the same 400 the extension check uses; an extension with
    no known signature is left untouched.
    """
    signatures = _CONTENT_SIGNATURES.get(ext)
    if signatures is None:
        return
    if not content.startswith(signatures):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. File content does not match its extension.",
        )


async def read_upload_with_limit(file: UploadFile, max_bytes: int) -> bytes:
    """Read an uploaded file in chunks, raising 413 if it exceeds max_bytes.

    Args:
        file: The uploaded file.
        max_bytes: Maximum allowed size in bytes.

    Returns:
        The file content as bytes.

    Raises:
        HTTPException: 413 if file exceeds max_bytes.
    """
    chunks: list[bytes] = []
    total = 0
    chunk_size = 1024 * 1024  # 1 MB

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum upload size is {max_bytes // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)

    return b"".join(chunks)
