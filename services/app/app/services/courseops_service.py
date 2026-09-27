"""CourseOps service — upload, extract, and manage course documents, assessments, and deadlines."""

from datetime import UTC, date, datetime

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.agents.base import CourseOpsResult
from app.core.exceptions import CourseOpsError
from app.core.storage import StorageBackend, get_storage
from app.core.utils import generate_id
from app.models.assessment import Assessment
from app.models.course import Course
from app.models.course_document import CourseDocument
from app.models.deadline import Deadline
from app.models.exam import Exam
from app.services import course_service

logger = structlog.get_logger()

#: Storage prefix for every course/assessment document blob.
COURSEOPS_PREFIX = "courseops"


def courseops_key(user_id: str, sha256: str, safe_name: str) -> str:
    """Build the storage key for a course document blob.

    ``courseops/<user_id>/<sha256[:16]>_<safe_name>``.

    The key used to be ``courseops/<sha256[:16]>_<safe_name>`` — content
    addressed with **no owner** — so two users who uploaded the same course
    handbook wrote to one blob. Nothing was corrupted (the same key means the
    same bytes, which is what content addressing buys) but the *lifecycle* was
    broken: `account_service.purge_user_storage` could not delete it, because
    removing one user's copy would pull the file out from under another user's
    still-live `CourseDocument` row. So closing an account left files behind
    (issue #107 / GL#4).

    Per-user keys trade that deduplication away, and it is worth very little
    here — a handful of shared handbooks — against a deletion path that would
    otherwise need cross-user reference counting, taken inside the deleting
    transaction, to avoid two concurrent closures each seeing the other's
    reference and neither deleting.

    The hash stays in the key even though it no longer has to be unique across
    users: within one user it still collapses a re-upload of the same file onto
    one blob, and it keeps two documents with the same filename but different
    content apart.

    Args:
        user_id: Owner of the document.
        sha256: Full hex digest of the content; only the first 16 chars are used.
        safe_name: Filename already through `sanitize_filename`, which strips
            everything but alphanumerics and ``" ._-()"`` — so it cannot
            introduce a path separator and the key always has exactly three
            segments.

    Returns:
        The storage key.
    """
    return f"{COURSEOPS_PREFIX}/{user_id}/{sha256[:16]}_{safe_name}"


def courseops_key_prefix_for_user(user_id: str) -> str:
    """Prefix covering every courseops blob owned by one user.

    Lives beside `courseops_key` so the writer and
    `account_service.purge_user_storage` cannot disagree about the shape — the
    same reason `summary_service.summary_key_prefix_for_course` and
    `preview_service.preview_keys_for_artifact` exist.

    No trailing slash, matching the other prefixes the purge sweeps. That is
    only safe because `generate_id` is UUID7 and every id is the same length,
    so no user id can be a string prefix of another. `LocalStorageBackend`
    resolves a prefix to a directory either way, but S3's ``list_objects_v2``
    matches on the raw string.

    Args:
        user_id: Owner whose blobs the prefix covers.

    Returns:
        The storage prefix.
    """
    return f"{COURSEOPS_PREFIX}/{user_id}"


async def _get_course_owned(
    session: AsyncSession,
    model: type[Assessment] | type[Deadline],
    object_id: str,
    user_id: str | None,
) -> Assessment | Deadline | None:
    """Resolve an Assessment or Deadline by id, pinned to its course's owner.

    Neither model carries a ``user_id`` column of its own -- the owner of one
    is the owner of the Course it hangs off -- so scoping means joining Course
    rather than adding a column filter. Stated once here so the eleven call
    sites in the courseops router do not each grow their own join.

    Args:
        session: Database session.
        model: Assessment or Deadline.
        object_id: UUID of the row, as supplied by the caller.
        user_id: If provided, only return the row when the course it belongs
            to is owned by this user. Endpoints reaching one of these by id
            MUST pass this to enforce object-level authorization; omitting it
            returns the row regardless of owner and is only appropriate for
            trusted internal callers such as the extraction pipeline.

    Returns:
        The row, or None when it does not exist or is owned by someone else.
    """
    if user_id is None:
        return await session.get(model, object_id)

    result = await session.execute(
        select(model)
        .join(Course, model.course_id == Course.id)
        .where(model.id == object_id, Course.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upload_course_document(
    session: AsyncSession,
    course_code: str,
    document_type: str,
    original_filename: str,
    file_path: str,
    file_type: str,
    sha256: str,
    file_size_bytes: int,
    user_id: str | None = None,
) -> CourseDocument:
    """Upload a course document with SHA-256 dedup.

    Args:
        session: Database session.
        course_code: Course code to associate with.
        document_type: Type of document (outline, rubric, handbook, other).
        original_filename: Original filename.
        file_path: Stored file path.
        file_type: File extension (pdf, docx).
        sha256: SHA-256 hash of the file.
        file_size_bytes: File size in bytes.

    Returns:
        The created CourseDocument.

    Raises:
        CourseOpsError: If course not found or document is a duplicate.
    """
    # Look up course
    course = await course_service.get_course_by_code(session, course_code, user_id=user_id)
    if not course:
        raise CourseOpsError(f"Course {course_code} not found")

    # Check for duplicate
    existing = await session.execute(
        select(CourseDocument).where(
            CourseDocument.course_id == course.id,
            CourseDocument.sha256 == sha256,
        )
    )
    if existing.scalar_one_or_none():
        raise CourseOpsError(
            f"Document with SHA-256 {sha256[:16]}... already uploaded for {course_code}"
        )

    doc = CourseDocument(
        id=generate_id(),
        user_id=user_id or course.user_id,
        course_id=course.id,
        document_type=document_type,
        title=original_filename,
        original_filename=original_filename,
        file_path=file_path,
        file_type=file_type,
        sha256=sha256,
        file_size_bytes=file_size_bytes,
        status="pending",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    logger.info(
        "course_document_uploaded",
        document_id=doc.id,
        course_code=course_code,
        document_type=document_type,
        filename=original_filename,
    )
    return doc


async def process_course_document(
    session: AsyncSession,
    document_id: str,
    extracted_text: str,
    ai_result: CourseOpsResult,
) -> dict:
    """Persist AI-extracted assessments and deadlines for a course document.

    Args:
        session: Database session.
        document_id: UUID of the course document.
        extracted_text: Raw text extracted from the document.
        ai_result: CourseOpsResult from the AI agent.

    Returns:
        Dict with counts of created assessments and deadlines.

    Raises:
        CourseOpsError: If document not found.
    """
    doc = await session.get(CourseDocument, document_id)
    if not doc:
        raise CourseOpsError(f"CourseDocument {document_id} not found")

    doc.extracted_text = extracted_text
    doc.status = "processed"

    # Update course info if available
    course = await session.get(Course, doc.course_id)
    if course and ai_result.course_info:
        if not course.name and ai_result.course_info.get("course_name"):
            course.name = ai_result.course_info["course_name"]
        if not course.term and ai_result.course_info.get("term"):
            course.term = ai_result.course_info["term"]

    # Create assessments
    assessment_count = 0
    assessment_map: dict[str, str] = {}  # title -> assessment_id for linking deadlines
    for a_data in ai_result.assessments:
        assessment = Assessment(
            id=generate_id(),
            course_id=doc.course_id,
            source_document_id=document_id,
            title=a_data.title,
            assessment_type=a_data.assessment_type,
            weight_pct=a_data.weight_pct,
            description=a_data.description,
            weeks_relevant=a_data.weeks_relevant if a_data.weeks_relevant else None,
        )
        session.add(assessment)
        assessment_map[a_data.title.lower()] = assessment.id
        assessment_count += 1

    # Create deadlines
    deadline_count = 0
    for d_data in ai_result.deadlines:
        if not d_data.due_date:
            continue
        try:
            due_date = date.fromisoformat(d_data.due_date)
        except ValueError:
            logger.warning("invalid_deadline_date", date_str=d_data.due_date, title=d_data.title)
            continue

        # Try to link to an assessment by matching title
        assessment_id = None
        for a_title, a_id in assessment_map.items():
            if a_title in d_data.title.lower() or d_data.title.lower() in a_title:
                assessment_id = a_id
                break

        deadline = Deadline(
            id=generate_id(),
            course_id=doc.course_id,
            assessment_id=assessment_id,
            source_document_id=document_id,
            title=d_data.title,
            due_date=due_date,
            deadline_type=d_data.deadline_type,
            description=d_data.description,
            is_confirmed=False,
        )
        session.add(deadline)
        deadline_count += 1

    await session.commit()

    logger.info(
        "course_document_processed",
        document_id=document_id,
        assessments=assessment_count,
        deadlines=deadline_count,
        confidence=ai_result.confidence,
    )

    return {
        "document_id": document_id,
        "assessment_count": assessment_count,
        "deadline_count": deadline_count,
        "confidence": ai_result.confidence,
    }


async def list_course_documents(
    session: AsyncSession,
    course_code: str,
    user_id: str | None = None,
) -> list[CourseDocument]:
    """List all course documents for a course.

    Args:
        session: Database session.
        course_code: Course code.
        user_id: If provided, only match the course owned by this user.

    Returns:
        List of CourseDocument objects.
    """
    course = await course_service.get_course_by_code(session, course_code, user_id=user_id)
    if not course:
        return []

    docs_result = await session.execute(
        select(CourseDocument)
        .where(CourseDocument.course_id == course.id)
        .order_by(CourseDocument.created_at.desc())
    )
    return list(docs_result.scalars().all())


async def get_course_document(
    session: AsyncSession,
    document_id: str,
    user_id: str | None = None,
) -> CourseDocument | None:
    """Get a single course document by ID, optionally scoped by owner.

    Args:
        session: Database session.
        document_id: UUID of the document.
        user_id: If provided, only return the document when it is owned by
            this user. Endpoints exposing documents by id MUST pass this to
            enforce object-level authorization; omitting it returns the
            document regardless of owner and is only appropriate for trusted
            internal callers.

    Returns:
        CourseDocument or None.
    """
    query = (
        select(CourseDocument)
        .options(
            joinedload(CourseDocument.assessments),
            joinedload(CourseDocument.deadlines),
        )
        .where(CourseDocument.id == document_id)
    )
    if user_id is not None:
        query = query.where(CourseDocument.user_id == user_id)
    result = await session.execute(query)
    return result.unique().scalar_one_or_none()


async def create_assessment(
    session: AsyncSession,
    *,
    course_code: str,
    title: str,
    assessment_type: str = "other",
    weight_pct: float | None = None,
    description: str | None = None,
    weeks_relevant: list[int] | None = None,
    user_id: str | None = None,
) -> Assessment | None:
    """Manually create an assessment for a course.

    Args:
        session: Database session.
        course_code: Course code the assessment belongs to.
        title: Assessment title.
        assessment_type: Type (exam, assignment, quiz, project, lab, presentation, other).
        weight_pct: Grade weight percentage, if known.
        description: Optional free-text description.
        weeks_relevant: Optional list of relevant week numbers.
        user_id: If provided, only match the course owned by this user.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching a course by a caller-supplied code MUST
            pass this; omitting it matches whichever user's course the code
            happens to hit first.

    Returns:
        The created Assessment, or None if the course code is unknown or the
        course is owned by someone else.
    """
    course = await course_service.get_course_by_code(session, course_code, user_id=user_id)
    if not course:
        return None

    assessment = Assessment(
        id=generate_id(),
        course_id=course.id,
        source_document_id=None,
        title=title,
        assessment_type=assessment_type,
        weight_pct=weight_pct,
        description=description,
        weeks_relevant=weeks_relevant,
    )
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    logger.info("assessment_created_manually", course_code=course_code, title=title)
    return assessment


async def update_assessment(
    session: AsyncSession,
    assessment_id: str,
    *,
    title: str | None = None,
    assessment_type: str | None = None,
    weight_pct: float | None = None,
    description: str | None = None,
    weeks_relevant: list[int] | None = None,
    user_id: str | None = None,
) -> Assessment | None:
    """Edit an assessment's info. Only provided fields are changed.

    Args:
        user_id: If provided, only edit the assessment when it belongs to a
            course owned by this user. Endpoints MUST pass this; see
            ``_get_course_owned``.

    Returns:
        The updated Assessment, or None if not found or owned by someone else.
    """
    assessment = await _get_course_owned(session, Assessment, assessment_id, user_id)
    if not assessment:
        return None

    if title is not None:
        assessment.title = title
    if assessment_type is not None:
        assessment.assessment_type = assessment_type
    if weight_pct is not None:
        assessment.weight_pct = weight_pct
    if description is not None:
        assessment.description = description
    if weeks_relevant is not None:
        assessment.weeks_relevant = weeks_relevant

    assessment.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(assessment)
    logger.info("assessment_updated", assessment_id=assessment_id)
    return assessment


async def list_assessment_documents(
    session: AsyncSession,
    assessment_id: str,
    user_id: str | None = None,
) -> list[CourseDocument]:
    """List documents attached to a specific assessment.

    Args:
        session: Database session.
        assessment_id: UUID of the assessment.
        user_id: If provided, only return documents owned by this user -- the
            same column ``get_course_document`` filters on. Endpoints MUST
            pass this; omitting it lists another user's attachments for any
            guessed assessment id.

    Returns:
        List of CourseDocument objects, empty when the assessment is unknown
        or belongs to someone else.
    """
    query = select(CourseDocument).where(CourseDocument.assessment_id == assessment_id)
    if user_id is not None:
        query = query.where(CourseDocument.user_id == user_id)
    result = await session.execute(query.order_by(CourseDocument.created_at))
    return list(result.scalars().all())


async def attach_assessment_document(
    session: AsyncSession,
    *,
    assessment_id: str,
    document_type: str,
    original_filename: str,
    file_path: str,
    file_type: str,
    sha256: str,
    file_size_bytes: int,
    user_id: str | None = None,
) -> CourseDocument | None:
    """Attach a reference document (brief, rubric, guideline, …) to an assessment.

    Unlike a course outline upload, this does NOT trigger AI extraction — it is a
    reference file linked to the assessment.

    Returns:
        The created CourseDocument, or None if the assessment does not exist.
    """
    assessment = await session.get(Assessment, assessment_id)
    if not assessment:
        return None

    owner_id = user_id
    if owner_id is None:
        course = await session.get(Course, assessment.course_id)
        owner_id = course.user_id if course else None

    doc = CourseDocument(
        id=generate_id(),
        user_id=owner_id,
        course_id=assessment.course_id,
        assessment_id=assessment_id,
        document_type=document_type,
        title=original_filename,
        original_filename=original_filename,
        file_path=file_path,
        file_type=file_type,
        sha256=sha256,
        file_size_bytes=file_size_bytes,
        status="processed",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    logger.info(
        "assessment_document_attached", assessment_id=assessment_id, document_type=document_type
    )
    return doc


async def _delete_blob_if_unreferenced(
    session: AsyncSession,
    owner_id: str,
    storage_key: str,
    storage: StorageBackend | None = None,
) -> bool:
    """Delete a courseops blob once no row of the same owner points at it.

    A user who uploads one handbook to two courses gets two `CourseDocument`
    rows and — because the key carries the content hash — **one** blob. So
    deleting a row cannot unconditionally delete the file.

    Refuses any key not under this owner's own prefix. That is what keeps a
    pre-#107 row safe: a legacy ``courseops/<sha256[:16]>_<name>`` key may be
    shared with *another user*, and a count over this user's rows says nothing
    about theirs. Those blobs stay until `scripts/backfill_courseops_files.py`
    gives each owner their own copy, which is the same "residue beats
    destroying someone else's data" trade the shared blob was left under
    before.

    Concurrency resolves in the safe direction. Two simultaneous deletions of
    two rows sharing a blob can both still see the other's row and both skip,
    leaving an orphan — residue. They cannot leave a surviving row pointing at
    a deleted blob, because the count runs after this deletion has committed.
    The one narrow exception is a delete racing a *fresh upload* of the same
    bytes: the upload's `put` precedes its row insert, so the blob can be
    removed between the two and that new document 404s. Not worth a lock; the
    blob is re-uploadable and nothing is disclosed.

    Args:
        session: Database session, after the row deletion has committed.
        owner_id: Owner of the document that was deleted.
        storage_key: The deleted row's ``file_path``.
        storage: Storage backend, defaulting to the configured singleton.

    Returns:
        True if the blob was deleted.
    """
    if not storage_key.startswith(f"{courseops_key_prefix_for_user(owner_id)}/"):
        return False

    remaining = (
        await session.execute(
            select(func.count(CourseDocument.id)).where(
                CourseDocument.user_id == owner_id,
                CourseDocument.file_path == storage_key,
            )
        )
    ).scalar_one()
    if remaining:
        return False

    store = storage if storage is not None else get_storage()
    try:
        if await store.exists(storage_key):
            await store.delete(storage_key)
            return True
    except Exception:
        # The row is already gone; a stuck blob must not turn a successful
        # delete into a 500. The account purge sweeps the prefix regardless.
        logger.warning("courseops_blob_delete_failed", key=storage_key, exc_info=True)
    return False


async def delete_course_document(
    session: AsyncSession,
    document_id: str,
    user_id: str | None = None,
    storage: StorageBackend | None = None,
) -> bool:
    """Delete a course document, and its blob when nothing else needs it.

    Resolves the document through the same owner-scoped getter #50 added for
    the read path, so the delete beside it can no longer destroy another
    user's document.

    The blob half only became safe with #107's per-user keys: while the key was
    content-addressed across users, this method deliberately deleted the row
    only, and every deleted document left its file on disk forever.

    Args:
        session: Database session.
        document_id: UUID of the document.
        user_id: If provided, only delete the document when it is owned by
            this user. Endpoints MUST pass this.
        storage: Storage backend, defaulting to the configured singleton.

    Returns:
        True if it existed and, when ``user_id`` is given, is owned by them.
    """
    doc = await get_course_document(session, document_id, user_id=user_id)
    if not doc:
        return False
    owner_id, storage_key = doc.user_id, doc.file_path
    await session.delete(doc)
    await session.commit()
    blob_deleted = await _delete_blob_if_unreferenced(session, owner_id, storage_key, storage)
    logger.info("course_document_deleted", document_id=document_id, blob_deleted=blob_deleted)
    return True


async def create_deadline(
    session: AsyncSession,
    *,
    course_code: str,
    title: str,
    due_date: date,
    deadline_type: str = "other",
    description: str | None = None,
    user_id: str | None = None,
) -> Deadline | None:
    """Manually create a deadline for a course.

    Manually entered deadlines are confirmed by default (unlike AI-extracted
    ones, which start unconfirmed and go through the review flow).

    Args:
        session: Database session.
        course_code: Course code the deadline belongs to.
        title: Deadline title.
        due_date: Date the deadline is due.
        deadline_type: Type (assignment, exam, quiz, project, other).
        description: Optional free-text description.
        user_id: If provided, only match the course owned by this user.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching a course by a caller-supplied code MUST
            pass this; omitting it matches whichever user's course the code
            happens to hit first.

    Returns:
        The created Deadline, or None if the course code is unknown or the
        course is owned by someone else.
    """
    course = await course_service.get_course_by_code(session, course_code, user_id=user_id)
    if not course:
        return None

    deadline = Deadline(
        id=generate_id(),
        course_id=course.id,
        assessment_id=None,
        source_document_id=None,
        title=title,
        due_date=due_date,
        deadline_type=deadline_type,
        description=description,
        is_confirmed=True,
    )
    session.add(deadline)
    await session.commit()
    await session.refresh(deadline)
    logger.info("deadline_created_manually", course_code=course_code, title=title)
    return deadline


async def list_assessments(
    session: AsyncSession,
    course_code: str,
    user_id: str | None = None,
) -> list[Assessment]:
    """List all assessments for a course.

    Args:
        session: Database session.
        course_code: Course code.
        user_id: If provided, only match the course owned by this user.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching a course by a caller-supplied code MUST
            pass this; omitting it matches whichever user's course the code
            happens to hit first.

    Returns:
        List of Assessment objects, empty when the code resolves to no course
        owned by ``user_id``.
    """
    course = await course_service.get_course_by_code(session, course_code, user_id=user_id)
    if not course:
        return []

    assessments_result = await session.execute(
        select(Assessment)
        .where(Assessment.course_id == course.id)
        .order_by(Assessment.assessment_type, Assessment.title)
    )
    return list(assessments_result.scalars().all())


async def list_deadlines(
    session: AsyncSession,
    course_code: str,
    upcoming_only: bool = False,
    user_id: str | None = None,
) -> list[Deadline]:
    """List deadlines for a course.

    Args:
        session: Database session.
        course_code: Course code.
        upcoming_only: If True, only return future deadlines.
        user_id: If provided, only match the course owned by this user.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching a course by a caller-supplied code MUST
            pass this; omitting it matches whichever user's course the code
            happens to hit first.

    Returns:
        List of Deadline objects, empty when the code resolves to no course
        owned by ``user_id``.
    """
    course = await course_service.get_course_by_code(session, course_code, user_id=user_id)
    if not course:
        return []

    query = select(Deadline).where(Deadline.course_id == course.id)
    if upcoming_only:
        query = query.where(Deadline.due_date >= date.today())
    query = query.order_by(Deadline.due_date)

    deadlines_result = await session.execute(query)
    return list(deadlines_result.scalars().all())


async def update_deadline(
    session: AsyncSession,
    deadline_id: str,
    title: str | None = None,
    due_date: date | None = None,
    deadline_type: str | None = None,
    description: str | None = None,
    is_confirmed: bool | None = None,
    user_id: str | None = None,
) -> Deadline | None:
    """Update a deadline.

    Args:
        session: Database session.
        deadline_id: UUID of the deadline.
        title: New title (optional).
        due_date: New due date (optional).
        deadline_type: New type (optional).
        description: New description (optional).
        is_confirmed: New confirmed status (optional).
        user_id: If provided, only update the deadline when it belongs to a
            course owned by this user. Endpoints MUST pass this; see
            ``_get_course_owned``.

    Returns:
        Updated Deadline, or None if not found or owned by someone else.
    """
    deadline = await _get_course_owned(session, Deadline, deadline_id, user_id)
    if not deadline:
        return None

    if title is not None:
        deadline.title = title
    if due_date is not None:
        deadline.due_date = due_date
    if deadline_type is not None:
        deadline.deadline_type = deadline_type
    if description is not None:
        deadline.description = description
    if is_confirmed is not None:
        deadline.is_confirmed = is_confirmed

    deadline.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(deadline)
    return deadline


async def delete_deadline(
    session: AsyncSession,
    deadline_id: str,
    user_id: str | None = None,
) -> bool:
    """Delete a deadline.

    Args:
        session: Database session.
        deadline_id: UUID of the deadline.
        user_id: If provided, only delete the deadline when it belongs to a
            course owned by this user. Endpoints MUST pass this; see
            ``_get_course_owned``.

    Returns:
        True if deleted, False if not found or owned by someone else.
    """
    deadline = await _get_course_owned(session, Deadline, deadline_id, user_id)
    if not deadline:
        return False

    await session.delete(deadline)
    await session.commit()
    return True


async def create_exam_from_deadline(
    session: AsyncSession,
    deadline_id: str,
    user_id: str | None = None,
) -> Exam | None:
    """Create an Exam from a deadline.

    Args:
        session: Database session.
        deadline_id: UUID of the deadline.
        user_id: If provided, only resolve a deadline whose course is owned by
            this user, and use it as the new exam's owner. Before #55 it was
            only the latter -- the deadline itself was fetched unscoped, so a
            caller could build an exam out of another user's deadline and flip
            that deadline's is_confirmed. The scoping guard could not see it,
            because the call site already passed user_id=user.id for the other
            purpose.

    Returns:
        Created Exam, or None if the deadline is not found or is owned by
        someone else.

    Raises:
        CourseOpsError: If deadline type is not exam-compatible.
    """
    deadline = await _get_course_owned(session, Deadline, deadline_id, user_id)
    if not deadline:
        return None

    # Determine weeks_scope from linked assessment
    weeks_scope: list[int] = []
    if deadline.assessment_id:
        assessment = await session.get(Assessment, deadline.assessment_id)
        if assessment and assessment.weeks_relevant:
            weeks_scope = assessment.weeks_relevant

    due_datetime = datetime.combine(deadline.due_date, datetime.min.time())

    # Resolve user_id from deadline's course if not provided
    if not user_id:
        course = await session.get(Course, deadline.course_id)
        user_id = course.user_id if course else ""

    exam = Exam(
        id=generate_id(),
        user_id=user_id,
        course_id=deadline.course_id,
        title=deadline.title,
        exam_date=due_datetime,
        weeks_scope=weeks_scope or [1],
        status="active",
    )
    session.add(exam)

    # Mark deadline as confirmed
    deadline.is_confirmed = True
    deadline.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(exam)

    logger.info(
        "exam_created_from_deadline",
        exam_id=exam.id,
        deadline_id=deadline_id,
        title=exam.title,
    )
    return exam


async def get_upcoming_deadlines_all_courses(
    session: AsyncSession,
    limit: int = 5,
    user_id: str | None = None,
) -> list[dict]:
    """Get upcoming deadlines across all courses for the dashboard.

    Args:
        session: Database session.
        limit: Max deadlines to return.

    Returns:
        List of deadline dicts with course_code.
    """
    query = (
        select(Deadline, Course.code)
        .join(Course, Deadline.course_id == Course.id)
        .where(Deadline.due_date >= date.today())
    )
    if user_id:
        query = query.where(Course.user_id == user_id)
    query = query.order_by(Deadline.due_date).limit(limit)
    result = await session.execute(query)

    deadlines = []
    for deadline, course_code in result.all():
        deadlines.append(
            {
                "id": deadline.id,
                "title": deadline.title,
                "due_date": deadline.due_date.isoformat(),
                "deadline_type": deadline.deadline_type,
                "course_code": course_code,
                "is_confirmed": deadline.is_confirmed,
            }
        )
    return deadlines


async def backfill_courseops_storage_keys(
    session: AsyncSession,
    storage: StorageBackend | None = None,
    *,
    delete_legacy: bool = True,
    dry_run: bool = False,
) -> dict[str, int]:
    """Give every existing course document its own per-user blob (#107).

    Alembic revision ``4f1c7a2e9b63`` rewrites the ``file_path`` column. This
    does the storage half, which a migration cannot: it runs where the blobs
    are (a mounted volume, or S3).

    Two entrypoints call this: ``python -m app.cli backfill-courseops-keys``,
    which is the one to use inside a container, and
    ``scripts/backfill_courseops_files.py`` for a host checkout. The CLI exists
    because repo-root ``scripts/`` is in neither the image nor any compose mount,
    so the script is unreachable from a deployed container.

    Per row still holding a legacy ``courseops/<sha256[:16]>_<name>`` key:

        1. **copies** the blob to ``courseops/<user_id>/<same basename>``
        2. points ``file_path`` at the new key
        3. deletes the legacy blob, once no row references it any more

    It copies rather than moves because several users may reference one legacy
    blob and each needs their own. That is safe here for the same reason the
    bug was benign: the key is content-addressed, so every referrer wants those
    identical bytes. #92's backfill had to do the opposite — there the single
    file held *one* user's content under both rows' key, so copying it would
    have been the disclosure.

    A legacy blob that is already missing is not an error: the row is still
    re-keyed, so it agrees with the migration either way, and it is counted
    separately so a surprising number is visible rather than silent.

    Idempotent and order-independent with respect to the migration: both derive
    the same key from the same columns, and a row already on the new shape is
    skipped. Only keys under ``courseops/`` that some row actually points at are
    read or deleted.

    The caller commits.

    Args:
        session: Database session.
        storage: Storage backend, defaulting to the configured singleton.
        delete_legacy: Delete each legacy blob once nothing references it.
        dry_run: Count what would change and write nothing.

    Returns:
        Counts: ``rows``, ``blobs_copied``, ``paths_updated``,
        ``legacy_missing``, ``legacy_deleted``.
    """
    store = storage if storage is not None else get_storage()

    rows = (
        await session.execute(
            select(CourseDocument.id, CourseDocument.user_id, CourseDocument.file_path)
        )
    ).all()

    counts = {
        "rows": len(rows),
        "blobs_copied": 0,
        "paths_updated": 0,
        "legacy_missing": 0,
        "legacy_deleted": 0,
    }
    legacy_keys: set[str] = set()

    for doc_id, user_id, file_path in rows:
        if not file_path:
            continue
        parts = file_path.split("/")
        if not (len(parts) == 2 and parts[0] == COURSEOPS_PREFIX):
            continue  # already per-user, or not a courseops key at all

        new_key = f"{courseops_key_prefix_for_user(user_id)}/{parts[1]}"
        legacy_keys.add(file_path)

        if await store.exists(file_path):
            if not await store.exists(new_key):
                counts["blobs_copied"] += 1
                if not dry_run:
                    await store.put(new_key, await store.get(file_path))
        else:
            counts["legacy_missing"] += 1

        counts["paths_updated"] += 1
        if not dry_run:
            await session.execute(
                update(CourseDocument).where(CourseDocument.id == doc_id).values(file_path=new_key)
            )

    if delete_legacy:
        for key in sorted(legacy_keys):
            if not await store.exists(key):
                continue
            if dry_run:
                # Nothing was rewritten, so every row still points here and the
                # reference count below would veto every deletion. The loop
                # rewrites *every* legacy-shaped row, so a real run leaves none
                # referenced — report it as deletable.
                counts["legacy_deleted"] += 1
                continue
            # Re-read the column rather than trusting the loop: a row inserted
            # concurrently, or one whose shape the loop declined to touch, may
            # still point here. Residue beats deleting a live document's file.
            still_referenced = (
                await session.execute(
                    select(func.count(CourseDocument.id)).where(CourseDocument.file_path == key)
                )
            ).scalar_one()
            if still_referenced:
                continue
            await store.delete(key)
            counts["legacy_deleted"] += 1

    logger.info("courseops_backfill", dry_run=dry_run, **counts)
    return counts
