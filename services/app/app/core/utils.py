"""Shared utility functions."""

import hashlib
from pathlib import Path

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


def sanitize_filename(filename: str) -> str:
    """Remove problematic characters from a filename."""
    keepchars = " ._-()"
    return "".join(c for c in filename if c.isalnum() or c in keepchars).strip()
