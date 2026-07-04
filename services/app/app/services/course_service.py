"""Business logic for Course queries and management."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.summary import Summary

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


async def merge_courses(
    session: AsyncSession,
    user_id: str,
    source_code: str,
    into_code: str,
) -> dict:
    """Merge one course into another.

    Moves artifacts, assets, exams, sessions, and CourseOps data to the
    target. Week summaries that collide with an existing target-week summary
    are NOT overwritten — a ReviewItem is created for each conflict instead.
    The source course is archived (not deleted) afterwards.

    Args:
        session: Database session.
        user_id: Owner user UUID.
        source_code: Course code to merge from.
        into_code: Course code to merge into.

    Returns:
        Dict with moved_summaries, conflict_weeks, review_items_created.

    Raises:
        LookupError: If either course does not exist for this user.
        ValueError: If source and target are the same course.
    """
    from app.models.assessment import Assessment
    from app.models.concept import Concept
    from app.models.course_document import CourseDocument
    from app.models.deadline import Deadline
    from app.models.exam import Exam
    from app.models.study_session import StudySession
    from app.services import review_service

    if source_code == into_code:
        raise ValueError("Cannot merge a course into itself")

    source = await _get_owned_course(session, user_id, source_code)
    target = await _get_owned_course(session, user_id, into_code)

    # Weeks already summarized in the target
    target_weeks_result = await session.execute(
        select(Summary.week).where(Summary.course_id == target.id)
    )
    target_weeks = set(target_weeks_result.scalars().all())

    # Source summaries: move clean weeks, flag conflicts
    source_summaries_result = await session.execute(
        select(Summary).where(Summary.course_id == source.id)
    )
    source_summaries = list(source_summaries_result.scalars().all())

    moved_summaries = 0
    conflict_weeks: list[int] = []
    review_items_created = 0

    for summary in source_summaries:
        if summary.week in target_weeks:
            conflict_weeks.append(summary.week)
            await review_service.create_review_item(
                session=session,
                review_type="merge_week_conflict",
                entity_type="summary",
                entity_id=summary.id,
                payload={
                    "source_course": source_code,
                    "target_course": into_code,
                    "week": summary.week,
                    "reason": f"Week {summary.week} already has a summary in {into_code}",
                },
                suggested_values={"action": "regenerate_week_summary"},
            )
            review_items_created += 1
        else:
            summary.course_id = target.id
            moved_summaries += 1

    # Move everything else to the target course
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

    # Archive the source (kept so conflicted summaries retain their FK)
    source.archived_at = datetime.now(UTC)
    await session.flush()

    logger.info(
        "courses_merged",
        source=source_code,
        target=into_code,
        moved_summaries=moved_summaries,
        conflicts=len(conflict_weeks),
    )

    return {
        "moved_summaries": moved_summaries,
        "conflict_weeks": sorted(conflict_weeks),
        "review_items_created": review_items_created,
    }
