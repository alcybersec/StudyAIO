"""Generate cached PDF previews for Office documents (PPTX/DOCX).

Browsers can't render PowerPoint/Word inline, so we convert them to PDF with
LibreOffice headless and serve the PDF with the existing viewer. Conversions are
cached in storage (regeneratable) and hardened against untrusted input.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import get_storage, normalize_storage_key
from app.services import artifact_service

logger = structlog.get_logger()

# File types we can convert to PDF for inline preview.
CONVERTIBLE_TYPES = {"pptx", "docx", "ppt", "doc"}

# Hard limits to bound resource use on untrusted documents.
CONVERT_TIMEOUT_SECONDS = 60
MAX_CONVERT_BYTES = 60 * 1024 * 1024  # 60 MB


# Bump when conversion output changes (e.g. new fonts) so cached previews are
# regenerated instead of serving stale/mis-rendered PDFs.
PREVIEW_CACHE_VERSION = 2


def _preview_key(artifact_id: str) -> str:
    return f"previews/v{PREVIEW_CACHE_VERSION}/{artifact_id}.pdf"


async def _convert_to_pdf(src: Path, out_dir: Path) -> Path | None:
    """Run LibreOffice headless to convert ``src`` to a PDF in ``out_dir``.

    Hardened: argument list (no shell), isolated disposable user profile + HOME
    (macros stay off in headless convert), and a hard timeout with process kill.
    Returns the produced PDF path, or None on any failure.
    """
    profile = out_dir / "lo-profile"
    proc = await asyncio.create_subprocess_exec(
        "libreoffice",
        f"-env:UserInstallation=file://{profile}",
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(src),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={"HOME": str(out_dir), "PATH": "/usr/bin:/bin"},
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=CONVERT_TIMEOUT_SECONDS)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("preview_conversion_timeout", src=src.name)
        return None

    if proc.returncode != 0:
        logger.warning("preview_conversion_failed", src=src.name, stderr=stderr.decode()[:500])
        return None

    out_pdf = out_dir / f"{src.stem}.pdf"
    return out_pdf if out_pdf.exists() else None


async def ensure_preview_pdf(
    session: AsyncSession,
    artifact_id: str,
    user_id: str | None = None,
) -> str | None:
    """Return a storage key for the artifact's preview PDF, converting if needed.

    - Non-convertible types → None.
    - Cached preview exists → return it (no re-conversion).
    - Otherwise convert with LibreOffice, cache, and return the key.

    Args:
        session: Database session.
        artifact_id: Artifact to preview.
        user_id: Tenant scope (only the owner's artifact is previewed).

    Returns:
        Storage key of the preview PDF, or None if it can't be produced.
    """
    artifact = await artifact_service.get_artifact(session, artifact_id, user_id=user_id)
    if not artifact or artifact.file_type not in CONVERTIBLE_TYPES:
        return None
    if artifact.file_size_bytes and artifact.file_size_bytes > MAX_CONVERT_BYTES:
        logger.info(
            "preview_skip_too_large", artifact_id=artifact_id, size=artifact.file_size_bytes
        )
        return None

    storage = get_storage()
    key = _preview_key(artifact_id)
    if await storage.exists(key):
        return key

    src_key = normalize_storage_key(artifact.file_path)
    with tempfile.TemporaryDirectory(prefix="preview-") as tmp:
        tmp_dir = Path(tmp)
        # Controlled input name — the user's filename never reaches the command line.
        src = tmp_dir / f"input.{artifact.file_type}"
        await storage.get_to_file(src_key, src)

        out_pdf = await _convert_to_pdf(src, tmp_dir)
        if not out_pdf:
            return None

        await storage.put_file(key, out_pdf)
        logger.info("preview_generated", artifact_id=artifact_id, file_type=artifact.file_type)
    return key
