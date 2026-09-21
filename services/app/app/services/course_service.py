"""Business logic for Course queries and management."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import get_storage, normalize_storage_key
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.summary import Summary
from app.services import summary_service

logger = structlog.get_logger()


async def list_courses(
    session: AsyncSession,
    user_id: str | None = None,
    include_archived: bool = False,
) -> list[Course]:
    """Get all courses, optionally filtered by user, ordered by code.

    Args:
        session: Database session.
        user_id: Filter by owner user UUID.
        include_archived: If False (default), archived courses are excluded.

    Returns:
        List of courses ordered alphabetically by code.
    """
    query = select(Course)
    if user_id is not None:
        query = query.where(Course.user_id == user_id)
    if not include_archived:
        query = query.where(Course.archived_at.is_(None))
    query = query.order_by(Course.code)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_course_by_code(
    session: AsyncSession, code: str, user_id: str | None = None
) -> Course | None:
    """Get a course by its code, optionally scoped by user.

    Args:
        session: Database session.
        code: Course code (e.g., "CSIT302").
        user_id: If provided, only return course owned by this user.

    Returns:
        Course if found, None otherwise.
    """
    query = select(Course).where(Course.code == code)
    if user_id is not None:
        query = query.where(Course.user_id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_course_by_id(
    session: AsyncSession, course_id: str, user_id: str | None = None
) -> Course | None:
    """Get a course by its id, optionally scoped by user.

    Course *codes* are unique only per user (``uq_courses_code_user``), so
    anything that has to be unique across the whole instance -- a storage key,
    for instance (#92) -- is keyed on the id instead, and needs this getter to
    resolve the owner back out of it.

    Args:
        session: Database session.
        course_id: Course UUID.
        user_id: If provided, only return the course if this user owns it.

    Returns:
        Course if found (and owned, when ``user_id`` is given), None otherwise.
    """
    query = select(Course).where(Course.id == course_id)
    if user_id is not None:
        query = query.where(Course.user_id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_courses_with_stats(
    session: AsyncSession,
    user_id: str | None = None,
    include_archived: bool = False,
) -> list[dict]:
    """Get all courses with aggregate stats in O(1) queries.

    Args:
        session: Database session.
        user_id: Filter by owner user UUID.
        include_archived: If False (default), archived courses are excluded.

    Returns:
        List of dicts with course fields + weeks_covered, total_artifacts.
    """
    courses = await list_courses(session, user_id=user_id, include_archived=include_archived)
    if not courses:
        return []

    course_ids = [c.id for c in courses]

    # Single query: per-course distinct weeks + artifact count
    result = await session.execute(
        select(
            LectureArtifact.course_id,
            func.count(func.distinct(LectureArtifact.week)).label("weeks_covered"),
            func.count(LectureArtifact.id).label("total_artifacts"),
        )
        .where(
            LectureArtifact.course_id.in_(course_ids),
            LectureArtifact.week.isnot(None),
        )
        .group_by(LectureArtifact.course_id)
    )
    stats = {
        row.course_id: {"weeks_covered": row.weeks_covered, "total_artifacts": row.total_artifacts}
        for row in result
    }

    items = []
    for c in courses:
        s = stats.get(c.id, {"weeks_covered": 0, "total_artifacts": 0})
        items.append(
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "term": c.term,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "weeks_covered": s["weeks_covered"],
                "total_artifacts": s["total_artifacts"],
                "last_updated": c.updated_at,
            }
        )

    return items


async def get_course_weeks(session: AsyncSession, course_id: str) -> list[dict]:
    """Get per-week aggregated data for a course.

    Returns a list of dicts with: week, titles (list), artifact_count,
    summary_status, summary_id, flashcard_count, quiz_count.

    Args:
        session: Database session.
        course_id: Course UUID.

    Returns:
        List of per-week summary dicts, ordered by week number.
    """
    # Get artifacts grouped by week
    artifact_rows = await session.execute(
        select(
            LectureArtifact.week,
            func.count(LectureArtifact.id).label("artifact_count"),
            func.array_agg(LectureArtifact.title).label("titles"),
        )
        .where(
            LectureArtifact.course_id == course_id,
            LectureArtifact.week.isnot(None),
        )
        .group_by(LectureArtifact.week)
        .order_by(LectureArtifact.week)
    )
    artifact_data = {
        row.week: {"count": row.artifact_count, "titles": row.titles or []} for row in artifact_rows
    }

    # Get summaries for this course
    summary_rows = await session.execute(
        select(Summary.week, Summary.id).where(Summary.course_id == course_id)
    )
    summary_data = {row.week: row.id for row in summary_rows}

    # Get flashcard counts per week
    fc_rows = await session.execute(
        select(
            Flashcard.week,
            func.count(Flashcard.id).label("fc_count"),
        )
        .where(Flashcard.course_id == course_id)
        .group_by(Flashcard.week)
    )
    flashcard_data = {row.week: row.fc_count for row in fc_rows}

    # Get quiz question counts per week
    qq_rows = await session.execute(
        select(
            QuizQuestion.week,
            func.count(QuizQuestion.id).label("qq_count"),
        )
        .where(QuizQuestion.course_id == course_id)
        .group_by(QuizQuestion.week)
    )
    quiz_data = {row.week: row.qq_count for row in qq_rows}

    # Combine all weeks
    all_weeks = sorted(set(artifact_data.keys()) | set(summary_data.keys()))

    result = []
    for week in all_weeks:
        art = artifact_data.get(week, {"count": 0, "titles": []})
        summary_id = summary_data.get(week)
        result.append(
            {
                "week": week,
                "titles": [t for t in art["titles"] if t],
                "artifact_count": art["count"],
                "summary_status": "generated" if summary_id else "pending",
                "summary_id": summary_id,
                "flashcard_count": flashcard_data.get(week, 0),
                "quiz_count": quiz_data.get(week, 0),
            }
        )

    return result


async def _get_owned_course(session: AsyncSession, user_id: str, code: str) -> Course:
    """Get a user's course by code or raise LookupError.

    Args:
        session: Database session.
        user_id: Owner user UUID (tenant isolation).
        code: Course code.

    Returns:
        The Course.

    Raises:
        LookupError: If the course does not exist for this user.
    """
    result = await session.execute(
        select(Course).where(Course.code == code, Course.user_id == user_id)
    )
    course = result.scalar_one_or_none()
    if not course:
        raise LookupError(f"Course '{code}' not found")
    return course


async def rename_course(
    session: AsyncSession,
    user_id: str,
    code: str,
    new_code: str | None = None,
    name: str | None = None,
) -> Course:
    """Rename a course (code and/or display name).

    Children reference the course by id, so FK integrity is preserved.

    Args:
        session: Database session.
        user_id: Owner user UUID.
        code: Current course code.
        new_code: New course code (must be unique for this user).
        name: New display name.

    Returns:
        The updated Course.

    Raises:
        LookupError: If the course does not exist for this user.
        ValueError: If new_code is already used by another of the user's courses.
    """
    course = await _get_owned_course(session, user_id, code)

    if new_code and new_code != code:
        conflict_result = await session.execute(
            select(Course).where(Course.code == new_code, Course.user_id == user_id)
        )
        conflict = conflict_result.scalar_one_or_none()
        if conflict and conflict.id != course.id:
            raise ValueError(f"Course '{new_code}' already exists")
        course.code = new_code

    if name is not None:
        course.name = name

    course.updated_at = datetime.now(UTC)
    await session.flush()

    logger.info("course_renamed", course_id=course.id, code=course.code)
    return course


async def archive_course(session: AsyncSession, user_id: str, code: str) -> Course:
    """Archive a course (soft hide from default listings).

    Args:
        session: Database session.
        user_id: Owner user UUID.
        code: Course code.

    Returns:
        The archived Course.

    Raises:
        LookupError: If the course does not exist for this user.
    """
    course = await _get_owned_course(session, user_id, code)
    if course.archived_at is None:
        course.archived_at = datetime.now(UTC)
        await session.flush()
        logger.info("course_archived", course_id=course.id, code=code)
    return course


async def delete_course(session: AsyncSession, user_id: str, code: str) -> dict:
    """Delete a course and all its database children.

    Storage blobs (uploads, extractions, summaries on disk) are deliberately
    left untouched — only database rows are removed.

    Args:
        session: Database session.
        user_id: Owner user UUID.
        code: Course code.

    Returns:
        Dict of deleted row counts per entity.

    Raises:
        LookupError: If the course does not exist for this user.
    """
    from app.models.assessment import Assessment
    from app.models.chunk import Chunk
    from app.models.concept import Concept
    from app.models.concept_relation import ConceptRelation
    from app.models.course_document import CourseDocument
    from app.models.deadline import Deadline
    from app.models.exam import Exam
    from app.models.extraction import Extraction
    from app.models.flashcard import Flashcard
    from app.models.flashcard_review import FlashcardReview
    from app.models.pipeline_run import PipelineRun
    from app.models.quiz import QuizQuestion
    from app.models.quiz_attempt import QuizAttempt
    from app.models.review_item import ReviewItem
    from app.models.study_session import StudySession

    course = await _get_owned_course(session, user_id, code)

    artifact_ids_result = await session.execute(
        select(LectureArtifact.id).where(LectureArtifact.course_id == course.id)
    )
    artifact_ids = list(artifact_ids_result.scalars().all())

    counts: dict[str, int] = {"artifacts": len(artifact_ids)}

    quiz_ids_subq = select(QuizQuestion.id).where(QuizQuestion.course_id == course.id)
    flashcard_ids_subq = select(Flashcard.id).where(Flashcard.course_id == course.id)
    concept_ids_subq = select(Concept.id).where(Concept.course_id == course.id)

    # Grandchildren first (FK order)
    await session.execute(
        delete(QuizAttempt).where(QuizAttempt.quiz_question_id.in_(quiz_ids_subq))
    )
    await session.execute(
        delete(FlashcardReview).where(FlashcardReview.flashcard_id.in_(flashcard_ids_subq))
    )
    await session.execute(
        delete(ConceptRelation).where(
            ConceptRelation.source_concept_id.in_(concept_ids_subq)
            | ConceptRelation.target_concept_id.in_(concept_ids_subq)
        )
    )

    # Children keyed by course
    counts["flashcards"] = (
        await session.execute(delete(Flashcard).where(Flashcard.course_id == course.id))
    ).rowcount or 0
    counts["quiz_questions"] = (
        await session.execute(delete(QuizQuestion).where(QuizQuestion.course_id == course.id))
    ).rowcount or 0
    counts["summaries"] = (
        await session.execute(delete(Summary).where(Summary.course_id == course.id))
    ).rowcount or 0
    await session.execute(delete(Concept).where(Concept.course_id == course.id))
    await session.execute(delete(StudySession).where(StudySession.course_id == course.id))
    await session.execute(delete(Exam).where(Exam.course_id == course.id))
    await session.execute(delete(Deadline).where(Deadline.course_id == course.id))
    await session.execute(delete(Assessment).where(Assessment.course_id == course.id))
    await session.execute(delete(CourseDocument).where(CourseDocument.course_id == course.id))

    # Artifact children
    if artifact_ids:
        await session.execute(delete(Chunk).where(Chunk.artifact_id.in_(artifact_ids)))
        await session.execute(delete(Extraction).where(Extraction.artifact_id.in_(artifact_ids)))
        await session.execute(delete(PipelineRun).where(PipelineRun.artifact_id.in_(artifact_ids)))
        await session.execute(delete(ReviewItem).where(ReviewItem.entity_id.in_(artifact_ids)))

    await session.execute(delete(LectureArtifact).where(LectureArtifact.course_id == course.id))
    await session.execute(delete(Course).where(Course.id == course.id))
    await session.flush()

    logger.info("course_deleted", course_id=course.id, code=code, counts=counts)
    return counts


#: Policies for a week whose summary exists in both the source and the target.
#:
#: ``regenerate`` is the default because it is the only one that loses nothing.
#: After the move the target course holds *both* courses' artifacts for that
#: week, so re-running the summarize stage produces one summary covering
#: everything — which is what the old ``suggested_values={"action":
#: "regenerate_week_summary"}`` on the review item said should happen, and never
#: did (#63). The other two exist because regenerating spends AI budget, and a
#: user merging two courses of lecture notes should not be forced to pay for a
#: summary they may not want.
MERGE_CONFLICT_POLICIES = frozenset({"regenerate", "keep_target", "keep_source"})


async def _sync_summary_blob(storage, summary: Summary, course_id: str) -> None:
    """Make the stored markdown match the row, under the key its course implies.

    Called after either half of a summary changes: its course (a moved week) or
    its content (a ``keep_source`` conflict). Both need the same guarantee —
    that ``summaries.file_path``, the key ``course_id`` implies, and the bytes
    actually stored all agree.

    Summary storage keys are derived from ``course_id`` (#92) and ``file_path``
    caches the key rather than a path, so reassigning ``course_id`` alone leaves
    the row in one course and its bytes under another course's prefix. Nothing
    404s immediately — ``file_path`` still points at the old key, and
    ``files._authorize_path`` resolves the old course to the same owner — but
    the row and the blob have diverged, and ``backfill_summary_storage_keys``
    would then "correct" ``file_path`` to a key with nothing behind it, turning
    a working download into a 404.

    The content is always rewritten, never copied: no storage backend here
    exposes a copy primitive, and the row is the source of truth for the
    markdown either way. Writing unconditionally is also what makes this safe
    for a content change whose key does *not* move — skipping the write when
    the keys matched is how the first draft of this left ``keep_source`` with
    the source's text in the row and the target's still on disk.

    Storage failures are logged and swallowed. A merge that has already moved
    every artifact must not be rolled back because one markdown file could not
    be rewritten: the summary text lives in ``content_md``, so the damage is a
    stale download, not lost work.

    Args:
        storage: Storage backend.
        summary: The summary row, already carrying its final course and content.
        course_id: The course the summary now belongs to.
    """
    old_key = normalize_storage_key(summary.file_path or "")
    new_key = summary_service.build_summary_storage_key(course_id, summary.week)
    summary.file_path = new_key
    try:
        await storage.put(new_key, summary.content_md.encode("utf-8"))
        if old_key and old_key != new_key:
            await storage.delete(old_key)
    except Exception:
        logger.warning(
            "summary_blob_sync_failed",
            summary_id=summary.id,
            old_key=old_key,
            new_key=new_key,
            exc_info=True,
        )


async def _discard_summary(session: AsyncSession, storage, summary: Summary) -> None:
    """Delete a summary row and the markdown blob behind it.

    Used for the source side of a resolved merge conflict. The artifacts that
    produced it are untouched — they move to the target with everything else.

    Storage failure is logged and swallowed for the same reason as in
    :func:`_sync_summary_blob`: an orphaned blob is preferable to failing a
    merge that has already moved every artifact, and the account purge sweeps
    the course prefix later regardless (#97).

    Args:
        session: Database session.
        storage: Storage backend.
        summary: The summary to delete.
    """
    key = normalize_storage_key(summary.file_path or "")
    await session.delete(summary)
    if not key:
        return
    try:
        await storage.delete(key)
    except Exception:
        logger.warning("summary_blob_delete_failed", summary_id=summary.id, key=key, exc_info=True)


async def merge_courses(
    session: AsyncSession,
    user_id: str,
    source_code: str,
    into_code: str,
    on_conflict: str = "regenerate",
) -> dict:
    """Merge one course into another, settling week conflicts as we go.

    Moves artifacts, assets, exams, sessions, and CourseOps data to the target,
    then archives the source.

    A week summarized in *both* courses is a conflict, and this function
    resolves it rather than deferring it. It used to file a ``ReviewItem``
    instead, which meant the merge completed while the question stayed open in
    an inbox that had no way to answer it: the resolve endpoint has an
    apply-branch for ``lecture_artifact`` only, so resolving a
    ``merge_week_conflict`` item marked it resolved, reported success, and
    changed nothing (#63). The source summary was also stranded in the archived
    source course on purpose, to keep the review item's entity reachable.

    ``on_conflict`` decides what happens per conflicting week:

    * ``regenerate`` (default) — discard the source summary and re-run the
      summarize stage for that week on the target. The target now holds both
      courses' artifacts, so the result covers everything. Costs AI spend, and
      happens asynchronously: the caller must enqueue the returned
      ``summarize_artifact_ids`` *after* committing.
    * ``keep_target`` — discard the source summary, keep the target's as-is.
      Spends nothing.
    * ``keep_source`` — the source summary's content replaces the target's
      (version bumped, ``source_artifacts`` merged). Spends nothing. The
      target's previous text is lost, but every artifact behind it survives the
      merge, so a later ``regenerate`` can rebuild it.

    A discarded source summary is deleted outright — both the row and its
    stored markdown. Its artifacts are *not* deleted; they move to the target
    like everything else, so nothing that produced the summary is lost.

    Args:
        session: Database session.
        user_id: Owner user UUID.
        source_code: Course code to merge from.
        into_code: Course code to merge into.
        on_conflict: One of :data:`MERGE_CONFLICT_POLICIES`.

    Returns:
        Dict with ``moved_summaries``, ``conflict_weeks``,
        ``conflict_resolution``, ``regenerated_weeks``, and
        ``summarize_artifact_ids`` — the last being work for the caller to
        enqueue post-commit, not part of the API response.

    Raises:
        LookupError: If either course does not exist for this user.
        ValueError: If source and target are the same course, or ``on_conflict``
            is not a known policy.
    """
    from app.models.assessment import Assessment
    from app.models.concept import Concept
    from app.models.course_document import CourseDocument
    from app.models.deadline import Deadline
    from app.models.exam import Exam
    from app.models.study_session import StudySession

    if source_code == into_code:
        raise ValueError("Cannot merge a course into itself")
    if on_conflict not in MERGE_CONFLICT_POLICIES:
        raise ValueError(
            f"Unknown on_conflict policy: {on_conflict}. Valid: {sorted(MERGE_CONFLICT_POLICIES)}"
        )

    source = await _get_owned_course(session, user_id, source_code)
    target = await _get_owned_course(session, user_id, into_code)

    # Summaries for weeks the target already covers, keyed by week so a
    # keep_source conflict can update the row in place.
    target_summaries_result = await session.execute(
        select(Summary).where(Summary.course_id == target.id)
    )
    target_summaries = {s.week: s for s in target_summaries_result.scalars().all()}

    source_summaries_result = await session.execute(
        select(Summary).where(Summary.course_id == source.id)
    )
    source_summaries = list(source_summaries_result.scalars().all())

    # Move the non-summary content first. `regenerate` re-runs the summarize
    # stage, which reads every extraction for the target course+week — so the
    # artifacts have to belong to the target before that task can see them.
    # The task is enqueued by the caller after commit, but ordering the writes
    # this way keeps the intent legible.
    for model, column in (
        (LectureArtifact, LectureArtifact.course_id),
        (Flashcard, Flashcard.course_id),
        (QuizQuestion, QuizQuestion.course_id),
        (Exam, Exam.course_id),
        (StudySession, StudySession.course_id),
        (Deadline, Deadline.course_id),
        (Assessment, Assessment.course_id),
        (CourseDocument, CourseDocument.course_id),
        (Concept, Concept.course_id),
    ):
        await session.execute(update(model).where(column == source.id).values(course_id=target.id))

    storage = get_storage()
    moved_summaries = 0
    conflict_weeks: list[int] = []
    regenerated_weeks: list[int] = []
    summarize_artifact_ids: list[str] = []

    for summary in source_summaries:
        existing = target_summaries.get(summary.week)
        if existing is None:
            summary.course_id = target.id
            await _sync_summary_blob(storage, summary, target.id)
            moved_summaries += 1
            continue

        conflict_weeks.append(summary.week)

        if on_conflict == "keep_source":
            existing.content_md = summary.content_md
            existing.version = existing.version + 1
            existing.source_artifacts = list(
                set((existing.source_artifacts or []) + (summary.source_artifacts or []))
            )
            existing.updated_at = datetime.now(UTC)
            await _sync_summary_blob(storage, existing, target.id)
        elif on_conflict == "regenerate":
            regenerated_weeks.append(summary.week)

        await _discard_summary(session, storage, summary)

    if regenerated_weeks:
        # One artifact per week is enough: the summarize stage summarizes the
        # whole course+week from every extraction, not just the artifact it was
        # handed. Resuming from "summarize" also re-indexes and regenerates
        # assets, which is what we want — the summary they derive from changed.
        for week in regenerated_weeks:
            artifact_id = await session.scalar(
                select(LectureArtifact.id)
                .where(
                    LectureArtifact.course_id == target.id,
                    LectureArtifact.week == week,
                    LectureArtifact.user_id == user_id,
                )
                .order_by(LectureArtifact.created_at.desc())
                .limit(1)
            )
            if artifact_id:
                summarize_artifact_ids.append(artifact_id)
            else:
                # A summary with no surviving artifact for its week. Nothing to
                # summarize from, so the target's summary stands; say so rather
                # than reporting a regeneration that will never run.
                logger.warning(
                    "merge_regenerate_no_artifact",
                    course_id=target.id,
                    week=week,
                )
                regenerated_weeks.remove(week)

    # Archive the emptied source. It is kept rather than deleted so the merge
    # stays auditable and the course code is not silently freed for reuse.
    source.archived_at = datetime.now(UTC)
    await session.flush()

    logger.info(
        "courses_merged",
        source=source_code,
        target=into_code,
        moved_summaries=moved_summaries,
        conflicts=len(conflict_weeks),
        on_conflict=on_conflict,
        regenerating=len(summarize_artifact_ids),
    )

    return {
        "moved_summaries": moved_summaries,
        "conflict_weeks": sorted(conflict_weeks),
        "conflict_resolution": on_conflict,
        "regenerated_weeks": sorted(regenerated_weeks),
        "summarize_artifact_ids": summarize_artifact_ids,
    }
