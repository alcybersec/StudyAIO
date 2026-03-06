"""Business logic for lecture artifact management."""

from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateFileError
from app.core.storage import get_storage
from app.core.utils import compute_sha256, generate_id, sanitize_filename
from app.models.artifact import LectureArtifact

logger = structlog.get_logger()

SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".pptx": "pptx"}


async def check_duplicate(
    session: AsyncSession, sha256: str, user_id: str
) -> LectureArtifact | None:
    """Check if a file with this SHA-256 hash already exists for this user.

    Args:
        session: Database session.
        sha256: File hash to check.
        user_id: Owner user UUID.

    Returns:
        Existing artifact if found, None otherwise.
    """
    result = await session.execute(
        select(LectureArtifact).where(
            LectureArtifact.sha256 == sha256,
            LectureArtifact.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def ingest_file(
    session: AsyncSession, source_path: str, user_id: str
) -> LectureArtifact:
    """Ingest a file into the system.

    Computes SHA-256 for dedup, copies to uploads via storage backend,
    creates LectureArtifact record.

    Args:
        session: Database session.
        source_path: Path to the source file (local filesystem).
        user_id: Owner user UUID.

    Returns:
        Created (or existing) LectureArtifact.

    Raises:
        DuplicateFileError: If file already exists (same SHA-256 for this user).
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

    # Check for duplicate (per-user)
    existing = await check_duplicate(session, sha256, user_id)
    if existing:
        logger.info(
            "ingest_duplicate_detected",
            file=path.name,
            existing_id=existing.id,
        )
        raise DuplicateFileError(sha256=sha256, existing_artifact_id=existing.id)

    # Generate artifact ID and copy file to uploads via storage backend
    artifact_id = generate_id()
    safe_name = sanitize_filename(path.name)
    dest_filename = f"{artifact_id}_{safe_name}"
    storage_key = f"uploads/{dest_filename}"

    storage = get_storage()
    await storage.ensure_dir("uploads")
    await storage.put_file(storage_key, path)

    file_size = path.stat().st_size
    logger.info(
        "ingest_file_copied",
        artifact_id=artifact_id,
        storage_key=storage_key,
        size=file_size,
    )

    # Create artifact record — store relative storage key
    artifact = LectureArtifact(
        id=artifact_id,
        user_id=user_id,
        original_filename=path.name,
        file_path=storage_key,
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


async def get_artifact(
    session: AsyncSession, artifact_id: str, user_id: str | None = None
) -> LectureArtifact | None:
    """Get a single artifact by ID, optionally scoped by user.

    Args:
        session: Database session.
        artifact_id: Artifact UUID.
        user_id: If provided, only return artifact owned by this user.

    Returns:
        LectureArtifact if found, None otherwise.
    """
    query = select(LectureArtifact).where(LectureArtifact.id == artifact_id)
    if user_id is not None:
        query = query.where(LectureArtifact.user_id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_artifacts(
    session: AsyncSession,
    user_id: str | None = None,
    course_id: str | None = None,
    week: int | None = None,
) -> list[LectureArtifact]:
    """List artifacts with optional filters.

    Args:
        session: Database session.
        user_id: Filter by owner user UUID.
        course_id: Filter by course UUID.
        week: Filter by week number.

    Returns:
        List of matching LectureArtifact records.
    """
    query = select(LectureArtifact)
    if user_id is not None:
        query = query.where(LectureArtifact.user_id == user_id)
    if course_id is not None:
        query = query.where(LectureArtifact.course_id == course_id)
    if week is not None:
        query = query.where(LectureArtifact.week == week)
    query = query.order_by(LectureArtifact.created_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())
