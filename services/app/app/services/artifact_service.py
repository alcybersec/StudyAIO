"""Business logic for lecture artifact management."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateFileError
from app.core.storage import get_storage
from app.core.utils import compute_sha256, generate_id, sanitize_filename
from app.models.artifact import LectureArtifact
from app.models.course import Course

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


async def ingest_file(session: AsyncSession, source_path: str, user_id: str) -> LectureArtifact:
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
    storage = get_storage()
    path = storage.resolve_path(source_path)
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
        pipeline_started_at=datetime.now(UTC),
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


async def ingest_text_capture(
    session: AsyncSession,
    text: str,
    title: str | None,
    user_id: str,
) -> LectureArtifact:
    """Ingest a quick text capture as a mini artifact.

    Stores the text as a .txt blob, dedupes on the SHA-256 of the text,
    and creates a LectureArtifact with source_type="capture".

    Args:
        session: Database session.
        text: Captured text content.
        title: Optional display title (used for the filename).
        user_id: Owner user UUID.

    Returns:
        Created LectureArtifact.

    Raises:
        DuplicateFileError: If the same text was already captured by this user.
    """
    import hashlib

    content = text.encode("utf-8")
    sha256 = hashlib.sha256(content).hexdigest()

    existing = await check_duplicate(session, sha256, user_id)
    if existing:
        logger.info("capture_duplicate_detected", existing_id=existing.id)
        raise DuplicateFileError(sha256=sha256, existing_artifact_id=existing.id)

    display_title = (title or "Quick capture").strip() or "Quick capture"
    original_filename = f"{display_title}.txt"
    safe_name = sanitize_filename(original_filename) or "capture.txt"

    artifact_id = generate_id()
    storage_key = f"uploads/{artifact_id}_{safe_name}"

    storage = get_storage()
    await storage.ensure_dir("uploads")
    await storage.put(storage_key, content)

    artifact = LectureArtifact(
        id=artifact_id,
        user_id=user_id,
        title=display_title,
        original_filename=original_filename,
        file_path=storage_key,
        file_type="txt",
        source_type="capture",
        sha256=sha256,
        file_size_bytes=len(content),
        status="ingested",
        pipeline_started_at=datetime.now(UTC),
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)

    logger.info(
        "capture_artifact_created",
        artifact_id=artifact.id,
        title=display_title,
        size=len(content),
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


async def apply_classification(
    session: AsyncSession,
    artifact: LectureArtifact,
    course_code: str | None = None,
    week: int | None = None,
    title: str | None = None,
    user_id: str | None = None,
) -> Course | None:
    """Apply classification fields to an artifact (shared move logic).

    Used by review-item resolution and reclassification. Resolves the
    course by code (optionally scoped to a user) and updates the artifact's
    course/week/title in place.

    Args:
        session: Database session.
        artifact: The artifact to update.
        course_code: Target course code (skipped if not found).
        week: Target week number.
        title: New display title.
        user_id: If provided, the course lookup is scoped to this user.

    Returns:
        The resolved Course, or None if course_code was absent/not found.
    """
    course = None
    if course_code:
        query = select(Course).where(Course.code == course_code)
        if user_id is not None:
            query = query.where(Course.user_id == user_id)
        result = await session.execute(query)
        course = result.scalar_one_or_none()
        if course:
            artifact.course_id = course.id

    if week is not None:
        artifact.week = week
    if title is not None:
        artifact.title = title

    return course


# Statuses in which an artifact may be reclassified (not mid-pipeline)
RECLASSIFIABLE_STATUSES = {"processed", "failed", "waiting_review"}


async def reclassify(
    session: AsyncSession,
    artifact_id: str,
    user_id: str,
    course_code: str,
    week: int,
) -> dict:
    """Move an artifact (and its flashcards/quiz questions) to another course/week.

    Transactional: updates the artifact plus child asset FKs. Chunks follow
    the artifact automatically (they reference artifact_id only). The caller
    is responsible for re-enqueueing summarize for both affected weeks.

    Args:
        session: Database session.
        artifact_id: Artifact UUID.
        user_id: Requesting user UUID (tenant isolation).
        course_code: Target course code (must exist for this user).
        week: Target week number.

    Returns:
        Dict with artifact, old_course_id, old_week, and source_artifact_id
        (a remaining artifact in the source week to regenerate its summary,
        or None if the source week is now empty).

    Raises:
        LookupError: If the artifact is not found for this user.
        ArtifactBusyError: If the artifact is still mid-pipeline.
        ValueError: If the target course is not found for this user.
    """
    from sqlalchemy import update

    from app.core.exceptions import ArtifactBusyError
    from app.models.flashcard import Flashcard
    from app.models.quiz import QuizQuestion

    artifact = await get_artifact(session, artifact_id, user_id=user_id)
    if not artifact:
        raise LookupError(f"Artifact {artifact_id} not found")

    if artifact.status not in RECLASSIFIABLE_STATUSES:
        raise ArtifactBusyError(
            f"Artifact {artifact_id} is still processing (status: {artifact.status})"
        )

    old_course_id = artifact.course_id
    old_week = artifact.week

    course = await apply_classification(
        session, artifact, course_code=course_code, week=week, user_id=user_id
    )
    if not course:
        raise ValueError(f"Course '{course_code}' not found")

    # Move child assets to the target course/week
    await session.execute(
        update(Flashcard)
        .where(Flashcard.source_artifact_id == artifact_id)
        .values(course_id=course.id, week=week)
    )
    await session.execute(
        update(QuizQuestion)
        .where(QuizQuestion.source_artifact_id == artifact_id)
        .values(course_id=course.id, week=week)
    )

    # Find a remaining artifact in the source week for summary regeneration
    source_artifact_id = None
    if old_course_id and old_week is not None:
        remaining = await session.execute(
            select(LectureArtifact.id)
            .where(
                LectureArtifact.course_id == old_course_id,
                LectureArtifact.week == old_week,
                LectureArtifact.id != artifact_id,
            )
            .limit(1)
        )
        source_artifact_id = remaining.scalar_one_or_none()

    await session.flush()

    logger.info(
        "artifact_reclassified",
        artifact_id=artifact_id,
        old_course_id=old_course_id,
        old_week=old_week,
        new_course_id=course.id,
        new_week=week,
    )

    return {
        "artifact": artifact,
        "old_course_id": old_course_id,
        "old_week": old_week,
        "source_artifact_id": source_artifact_id,
    }


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
