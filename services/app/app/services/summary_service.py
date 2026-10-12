"""Business logic for Summary management."""

from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import ExtractionData
from app.core.storage import StorageBackend, get_storage, normalize_storage_key
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.extraction import Extraction
from app.models.summary import Summary
from app.models.summary_version import SummaryVersion

logger = structlog.get_logger()

# Every summary storage key lives under this prefix. ``app.api.files`` serves
# it, and the backfill below is scoped to it.
SUMMARY_KEY_PREFIX = "summaries"


async def get_week_extractions(
    session: AsyncSession, course_id: str, week: int
) -> list[Extraction]:
    """Get all extractions for a course+week.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.

    Returns:
        List of Extraction records for the week.
    """
    result = await session.execute(
        select(Extraction)
        .join(LectureArtifact, Extraction.artifact_id == LectureArtifact.id)
        .where(
            LectureArtifact.course_id == course_id,
            LectureArtifact.week == week,
        )
    )
    return list(result.scalars().all())


def merge_extractions(extractions: list[Extraction]) -> ExtractionData:
    """Merge multiple extractions into a single ExtractionData.

    Concatenates all pages from each extraction's manifest_json.

    Args:
        extractions: List of Extraction records.

    Returns:
        Merged ExtractionData with all pages and combined metadata.
    """
    all_pages: list[dict] = []
    artifact_ids: list[str] = []

    for extraction in extractions:
        manifest = extraction.manifest_json
        pages = manifest.get("pages", [])
        all_pages.extend(pages)
        artifact_ids.append(extraction.artifact_id)

    return ExtractionData(
        pages=all_pages,
        metadata={
            "artifact_ids": artifact_ids,
            "extraction_count": len(extractions),
        },
    )


async def get_existing_summary(session: AsyncSession, course_id: str, week: int) -> Summary | None:
    """Get existing summary for a course+week if it exists.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.

    Returns:
        Existing Summary or None.
    """
    result = await session.execute(
        select(Summary).where(
            Summary.course_id == course_id,
            Summary.week == week,
        )
    )
    return result.scalar_one_or_none()


async def get_owned_summary(
    session: AsyncSession, course_id: str, week: int, *, user_id: str
) -> Summary | None:
    """Get the caller's summary for a course id + week.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.
        user_id: The caller; the course must belong to them.

    Returns:
        Summary if the caller owns the course and it has one, else None.
    """
    from app.models.course import Course as CourseModel

    result = await session.execute(
        select(Summary)
        .join(CourseModel, Summary.course_id == CourseModel.id)
        .where(
            Summary.course_id == course_id,
            Summary.week == week,
            CourseModel.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def snapshot_summary(
    session: AsyncSession, summary: Summary, storage: StorageBackend | None = None
) -> SummaryVersion:
    """Retain the current state of ``summary`` as an immutable ``SummaryVersion``.

    Floor 4: a re-summarize (or a merge ``keep_source``) never destroys the
    version it replaces. Call this *before* mutating ``summary``. The row is
    the source of truth for the text, so the blob is (re)written from
    ``content_md`` to ``Week<N>.v<version>.md`` -- even when the pipeline has
    already overwritten the unversioned key the row points at. An existing
    key is never put over.

    Args:
        session: Database session.
        summary: The summary about to be replaced, still holding its old state.
        storage: Storage backend, defaulting to the configured singleton.

    Returns:
        The snapshot row (added to the session, not committed).
    """
    store = storage if storage is not None else get_storage()
    owner = await session.scalar(select(Course.user_id).where(Course.id == summary.course_id))
    key = build_summary_storage_key(summary.course_id, summary.week, version=summary.version)
    try:
        if not await store.exists(key):
            await store.put(key, (summary.content_md or "").encode("utf-8"))
    except Exception:
        # The text is retained in the row below; a missing blob copy is
        # recoverable from it, a failed re-summarize is not worth that.
        logger.warning("summary_version_blob_failed", summary_id=summary.id, key=key, exc_info=True)

    snapshot = SummaryVersion(
        id=generate_id(),
        user_id=owner,
        course_id=summary.course_id,
        week=summary.week,
        version=summary.version,
        content_md=summary.content_md,
        file_path=key,
        source_artifacts=list(summary.source_artifacts or []),
        generated_at=summary.updated_at,
    )
    session.add(snapshot)
    logger.info(
        "summary_version_retained",
        course_id=summary.course_id,
        week=summary.week,
        version=summary.version,
    )
    return snapshot


async def create_or_update_summary(
    session: AsyncSession,
    course_id: str,
    week: int,
    content_md: str,
    file_path: str,
    source_artifact_ids: list[str],
) -> Summary:
    """Create a new summary or update an existing one.

    If a summary already exists for the course+week, the old state is first
    retained as a ``SummaryVersion`` (see :func:`snapshot_summary`), then the
    version is incremented and the content updated. Otherwise creates a new one.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.
        content_md: Generated markdown content.
        file_path: Path where the markdown file is saved.
        source_artifact_ids: List of artifact IDs that contributed.

    Returns:
        The created or updated Summary.
    """
    existing = await get_existing_summary(session, course_id, week)

    if existing:
        await snapshot_summary(session, existing)

        # Merge source artifact IDs (avoid duplicates)
        current_sources = existing.source_artifacts or []
        merged_sources = list(set(current_sources + source_artifact_ids))

        existing.content_md = content_md
        existing.file_path = file_path
        existing.version = existing.version + 1
        existing.source_artifacts = merged_sources
        existing.updated_at = datetime.now(UTC)

        await session.flush()
        logger.info(
            "summary_updated",
            course_id=course_id,
            week=week,
            version=existing.version,
        )
        return existing

    summary = Summary(
        id=generate_id(),
        course_id=course_id,
        week=week,
        content_md=content_md,
        file_path=file_path,
        version=1,
        source_artifacts=source_artifact_ids,
    )
    session.add(summary)
    await session.flush()

    logger.info(
        "summary_created",
        summary_id=summary.id,
        course_id=course_id,
        week=week,
    )
    return summary


async def get_summary_by_id(
    session: AsyncSession, summary_id: str, *, user_id: str
) -> Summary | None:
    """Get a summary by its ID, scoped to its owner.

    Summary has no user_id column of its own; ownership runs through the
    course it belongs to.

    Args:
        session: Database session.
        summary_id: Summary UUID.
        user_id: Owner user UUID (required). Only a summary whose course
            belongs to this user is returned.

    Returns:
        Summary if found, None otherwise.
    """
    query = (
        select(Summary)
        .join(Course, Summary.course_id == Course.id)
        .where(Summary.id == summary_id, Course.user_id == user_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_summary_for_week(
    session: AsyncSession, course_code: str, week: int, *, user_id: str
) -> Summary | None:
    """Get the summary for a specific course code + week.

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        week: Week number.
        user_id: The caller. Course codes are unique per user, not globally,
            so the code alone can match several users' summaries.

    Returns:
        Summary if found, None otherwise.
    """
    from app.models.course import Course as CourseModel

    query = (
        select(Summary)
        .join(CourseModel, Summary.course_id == CourseModel.id)
        .where(
            CourseModel.code == course_code,
            Summary.week == week,
            CourseModel.user_id == user_id,
        )
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_course_summaries(session: AsyncSession, course_id: str) -> list[Summary]:
    """Get all summaries for a course.

    Args:
        session: Database session.
        course_id: Course UUID.

    Returns:
        List of Summary records ordered by week.
    """
    result = await session.execute(
        select(Summary).where(Summary.course_id == course_id).order_by(Summary.week)
    )
    return list(result.scalars().all())


def build_summary_file_path(summaries_dir: str, course_id: str, week: int) -> Path:
    """Build the local file path for a summary markdown file.

    Args:
        summaries_dir: Base directory for summaries.
        course_id: Course UUID (**not** the course code -- see
            :func:`build_summary_storage_key`).
        week: Week number.

    Returns:
        Path like <summaries_dir>/<course_id>/Week<N>.md
    """
    course_dir = Path(summaries_dir) / course_id
    course_dir.mkdir(parents=True, exist_ok=True)
    return course_dir / f"Week{week}.md"


def summary_key_prefix_for_course(course_id: str) -> str:
    """The storage prefix holding every summary file for one course.

    Summary keys are scoped by **course**, never by artifact. The account
    purge enumerates from this rather than writing the shape out a second
    time: deletion silently retained every summary file for the life of the
    feature because it swept ``summaries/<artifact_id>``, a prefix no summary
    key has ever had (#97).

    Args:
        course_id: Course UUID.

    Returns:
        Prefix like ``summaries/0192c4d5-...``
    """
    return f"{SUMMARY_KEY_PREFIX}/{course_id}"


def build_summary_storage_key(course_id: str, week: int, version: int | None = None) -> str:
    """Build the storage key for a summary markdown file.

    Keyed on the course **id**, not its code (#92). Course codes are unique
    only per user (``uq_courses_code_user``), so the old
    ``summaries/<CODE>/<CODE>_Week<N>.md`` shape gave two users who both take
    ``CSIT302`` byte-identical keys: the second pipeline run silently
    overwrote the first user's file, and both ``summaries`` rows then pointed
    at it. ``courses.id`` is a per-user primary key, so the collision cannot
    happen; it also survives a course rename (``rename_course``), which a
    code-shaped key does not, and it keeps a user-supplied string out of a
    filesystem path.

    ``app.api.files._authorize_path`` resolves the owner back out of the first
    segment, so the segment must stay something ``course_service`` can look up
    scoped to a user.

    Args:
        course_id: Course UUID.
        week: Week number.
        version: When given, the key of that specific version
            (``Week<N>.v<version>.md``). Versioned keys are written once and
            never put over, which is how a superseded summary's blob survives.

    Returns:
        Key like ``summaries/0192c4d5-.../Week3.md`` (or ``.../Week3.v2.md``).
    """
    suffix = f".v{version}" if version is not None else ""
    return f"{summary_key_prefix_for_course(course_id)}/Week{week}{suffix}.md"


async def backfill_summary_storage_keys(
    session: AsyncSession,
    storage: StorageBackend | None = None,
    *,
    delete_legacy: bool = True,
    dry_run: bool = False,
) -> dict[str, int]:
    """Re-derive every summary's storage key from its course id and rewrite it.

    The #92 fix changes the key shape, so every existing row points at a key
    of the old, colliding shape. This moves them, but deliberately does *not*
    move the file: on an instance where two users shared a course code, the
    single file at the old key holds whichever pipeline ran last, so copying
    it would hand one user the other's content. ``summaries.content_md`` is
    per-user and correct -- the row is the source of truth -- so each new file
    is **written from the column**.

    Idempotent: re-running rewrites the same bytes to the same keys, and the
    legacy keys are already gone. Only keys under ``summaries/`` that some row
    actually points at are deleted; nothing else in the data directory is
    touched.

    The caller commits.

    Args:
        session: Database session.
        storage: Storage backend, defaulting to the configured singleton.
        delete_legacy: Delete the old-shape files once every row has been
            rewritten. They are unreachable afterwards either way -- the files
            route no longer resolves that shape -- but they are also stale, and
            possibly the wrong user's content.
        dry_run: Report what would happen; write, update and delete nothing.

    Returns:
        Counts: ``rows``, ``files_written``, ``paths_updated``,
        ``legacy_deleted``.
    """
    store = storage if storage is not None else get_storage()

    result = await session.execute(select(Summary).order_by(Summary.course_id, Summary.week))
    rows = list(result.scalars().all())

    new_keys: set[str] = set()
    legacy_keys: set[str] = set()
    paths_updated = 0

    for summary in rows:
        new_key = build_summary_storage_key(summary.course_id, summary.week)
        new_keys.add(new_key)

        current = normalize_storage_key(summary.file_path or "")
        if current != new_key:
            paths_updated += 1
            # Only ever a summary key: a row pointing somewhere else entirely
            # is not ours to delete.
            if current.startswith(f"{SUMMARY_KEY_PREFIX}/"):
                legacy_keys.add(current)

        if not dry_run:
            await store.put(new_key, (summary.content_md or "").encode("utf-8"))
            summary.file_path = new_key

    # A legacy key can never equal a new one (a course code is not a course
    # id), but an instance that has already been backfilled must not be able
    # to delete what it just wrote.
    stale = sorted(legacy_keys - new_keys)

    deleted = 0
    if not dry_run:
        await session.flush()
        if delete_legacy:
            for key in stale:
                await store.delete(key)
                deleted += 1

    # Counts describe the work, so a dry run reports what a real run would do.
    counts = {
        "rows": len(rows),
        "files_written": len(rows),
        "paths_updated": paths_updated,
        "legacy_deleted": deleted if not dry_run else (len(stale) if delete_legacy else 0),
    }
    logger.info("summary_storage_key_backfill", dry_run=dry_run, **counts)
    return counts
