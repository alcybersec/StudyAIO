"""Business logic for lecture artifact management."""

import shutil
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import DuplicateFileError
from app.core.utils import compute_sha256, generate_id, sanitize_filename
from app.models.artifact import LectureArtifact

logger = structlog.get_logger()

SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".pptx": "pptx"}


async def check_duplicate(session: AsyncSession, sha256: str) -> LectureArtifact | None:
    """Check if a file with this SHA-256 hash already exists.

    Args:
        session: Database session.
        sha256: File hash to check.

    Returns:
        Existing artifact if found, None otherwise.
    """
    result = await session.execute(select(LectureArtifact).where(LectureArtifact.sha256 == sha256))
    return result.scalar_one_or_none()


async def ingest_file(session: AsyncSession, source_path: str) -> LectureArtifact:
    """Ingest a file into the system.

    Computes SHA-256 for dedup, copies to uploads directory, creates
    LectureArtifact record.

    Args:
        session: Database session.
        source_path: Path to the source file.

    Returns:
        Created (or existing) LectureArtifact.

    Raises:
        DuplicateFileError: If file already exists (same SHA-256).
        ValueError: If file type is not supported.
        FileNotFoundError: If source file doesn't exist.
    """
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    # Determine file type
    ext = path.suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(ext)
    if file_type is None:
        raise ValueError(
            f"Unsupported file type: {ext}. Supported: {list(SUPPORTED_EXTENSIONS.keys())}"
        )

    # Compute hash for dedup
    sha256 = compute_sha256(path)
    logger.info("ingest_hash_computed", file=path.name, sha256=sha256[:16])

    # Check for duplicate
    existing = await check_duplicate(session, sha256)
    if existing:
        logger.info(
            "ingest_duplicate_detected",
            file=path.name,
            existing_id=existing.id,
        )
        raise DuplicateFileError(sha256=sha256, existing_artifact_id=existing.id)

    # Generate artifact ID and copy file to uploads
    artifact_id = generate_id()
    safe_name = sanitize_filename(path.name)
    uploads_dir = Path(settings.uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest_filename = f"{artifact_id}_{safe_name}"
    dest_path = uploads_dir / dest_filename
    shutil.copy2(str(path), str(dest_path))

    file_size = dest_path.stat().st_size
    logger.info(
        "ingest_file_copied",
        artifact_id=artifact_id,
        dest=str(dest_path),
        size=file_size,
    )

    # Create artifact record
    artifact = LectureArtifact(
        id=artifact_id,
        original_filename=path.name,
        file_path=str(dest_path),
        file_type=file_type,
        sha256=sha256,
        file_size_bytes=file_size,
        status="ingested",
        pipeline_started_at=datetime.utcnow(),
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)

    logger.info(
        "ingest_artifact_created",
        artifact_id=artifact.id,
        filename=artifact.original_filename,
        status=artifact.status,
    )

    return artifact


async def get_artifact(session: AsyncSession, artifact_id: str) -> LectureArtifact | None:
    """Get a single artifact by ID.

    Args:
        session: Database session.
        artifact_id: Artifact UUID.

    Returns:
        LectureArtifact if found, None otherwise.
    """
    result = await session.execute(select(LectureArtifact).where(LectureArtifact.id == artifact_id))
    return result.scalar_one_or_none()


async def list_artifacts(
    session: AsyncSession,
    course_id: str | None = None,
    week: int | None = None,
) -> list[LectureArtifact]:
    """List artifacts with optional filters.

    Args:
        session: Database session.
        course_id: Filter by course UUID.
        week: Filter by week number.

    Returns:
        List of matching LectureArtifact records.
    """
    query = select(LectureArtifact)
    if course_id is not None:
        query = query.where(LectureArtifact.course_id == course_id)
    if week is not None:
        query = query.where(LectureArtifact.week == week)
    query = query.order_by(LectureArtifact.created_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())
