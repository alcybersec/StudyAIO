"""Business logic for Flashcard and QuizQuestion management."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import FlashcardData, QuizQuestionData
from app.core.utils import generate_id
from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.models.quiz import QuizQuestion
from app.services import course_service

logger = structlog.get_logger()

#: ``source_page_ref`` of a user-written item: it cites no lecture page.
USER_ITEM_PAGE_REF = 0
QUIZ_TYPES = ("multiple_choice", "short_answer")
MIN_OPTIONS, MAX_OPTIONS = 2, 8


class ItemNotFoundError(LookupError):
    """The item, course or source artifact is missing or not the caller's."""


class NoSourceArtifactError(Exception):
    """A manual item needs a lecture in that course and week to hang off."""


async def save_flashcards(
    session: AsyncSession,
    course_id: str,
    week: int,
    artifact_id: str,
    flashcards: list[FlashcardData],
) -> list[Flashcard]:
    """Save flashcards for an artifact, replacing any existing ones.

    Archives (``archived_at``) the artifact's active flashcards -- never deletes
    them, so their reviews survive (floor 4) -- computes the next generation
    version, and inserts new records.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.
        artifact_id: Source artifact UUID.
        flashcards: List of FlashcardData from the agent.

    Returns:
        List of created Flashcard records.
    """
    # Retire (not delete) the artifact's active flashcards: their reviews are study history.
    await session.execute(
        update(Flashcard)
        .where(
            Flashcard.source_artifact_id == artifact_id,
            Flashcard.archived_at.is_(None),
            # Targeted practice (ADR 0007) is never retired by a lecture re-run.
            Flashcard.origin == "pipeline",
        )
        .values(archived_at=datetime.now(UTC))
    )

    # Compute next generation version for this course+week
    result = await session.execute(
        select(func.max(Flashcard.generation_version)).where(
            Flashcard.course_id == course_id, Flashcard.week == week
        )
    )
    max_version = result.scalar() or 0
    next_version = max_version + 1

    records: list[Flashcard] = []
    for fc in flashcards:
        record = Flashcard(
            id=generate_id(),
            course_id=course_id,
            week=week,
            front=fc.front,
            back=fc.back,
            tags=fc.tags,
            source_artifact_id=artifact_id,
            source_page_ref=fc.source_page_ref,
            generation_version=next_version,
        )
        session.add(record)
        records.append(record)

    await session.flush()

    logger.info(
        "flashcards_saved",
        course_id=course_id,
        week=week,
        artifact_id=artifact_id,
        count=len(records),
        version=next_version,
    )
    return records


async def save_quiz_questions(
    session: AsyncSession,
    course_id: str,
    week: int,
    artifact_id: str,
    questions: list[QuizQuestionData],
) -> list[QuizQuestion]:
    """Save quiz questions for an artifact, replacing any existing ones.

    Archives (``archived_at``) the artifact's active questions -- never deletes
    them, so their attempts survive (floor 4) -- computes the next generation
    version, and inserts new records.

    Args:
        session: Database session.
        course_id: Course UUID.
        week: Week number.
        artifact_id: Source artifact UUID.
        questions: List of QuizQuestionData from the agent.

    Returns:
        List of created QuizQuestion records.
    """
    # Retire (not delete) the artifact's active questions: their attempts are study history.
    await session.execute(
        update(QuizQuestion)
        .where(
            QuizQuestion.source_artifact_id == artifact_id,
            QuizQuestion.archived_at.is_(None),
            # Targeted practice (ADR 0007) is never retired by a lecture re-run.
            QuizQuestion.origin == "pipeline",
        )
        .values(archived_at=datetime.now(UTC))
    )

    # Compute next generation version for this course+week
    result = await session.execute(
        select(func.max(QuizQuestion.generation_version)).where(
            QuizQuestion.course_id == course_id, QuizQuestion.week == week
        )
    )
    max_version = result.scalar() or 0
    next_version = max_version + 1

    records: list[QuizQuestion] = []
    for q in questions:
        record = QuizQuestion(
            id=generate_id(),
            course_id=course_id,
            week=week,
            question_type=q.question_type,
            question=q.question,
            options_json=q.options,
            correct_answer=q.correct_answer,
            explanation=q.explanation,
            source_artifact_id=artifact_id,
            source_page_ref=q.source_page_ref,
            generation_version=next_version,
        )
        session.add(record)
        records.append(record)

    await session.flush()

    logger.info(
        "quiz_questions_saved",
        course_id=course_id,
        week=week,
        artifact_id=artifact_id,
        count=len(records),
        version=next_version,
    )
    return records


async def get_items_by_ids(
    session: AsyncSession,
    flashcard_ids: list[str],
    quiz_question_ids: list[str],
    *,
    user_id: str,
) -> tuple[list[Flashcard], list[QuizQuestion]]:
    """Fetch the caller's active cards and questions by id.

    Foreign, archived and missing ids are silently omitted, so the result is no
    oracle for whether an id exists.

    Args:
        session: Database session.
        flashcard_ids: Flashcard ids to load.
        quiz_question_ids: Quiz question ids to load.
        user_id: Owner user UUID; rows are joined to ``courses.user_id``.

    Returns:
        (flashcards, quiz_questions), each ordered by creation time then id.
    """
    cards: list[Flashcard] = []
    questions: list[QuizQuestion] = []
    if flashcard_ids:
        result = await session.execute(
            select(Flashcard)
            .join(Course, Flashcard.course_id == Course.id)
            .where(
                Flashcard.id.in_(flashcard_ids),
                Flashcard.archived_at.is_(None),
                Course.user_id == user_id,
            )
            .order_by(Flashcard.created_at, Flashcard.id)
        )
        cards = list(result.scalars().all())
    if quiz_question_ids:
        result = await session.execute(
            select(QuizQuestion)
            .join(Course, QuizQuestion.course_id == Course.id)
            .where(
                QuizQuestion.id.in_(quiz_question_ids),
                QuizQuestion.archived_at.is_(None),
                Course.user_id == user_id,
            )
            .order_by(QuizQuestion.created_at, QuizQuestion.id)
        )
        questions = list(result.scalars().all())
    return cards, questions


# ── user-authored items (GL#48) ──────────────────────────────────
#
# Floor 4: nothing below issues a SQL DELETE. Deleting archives; editing
# archives the original and inserts an ``origin="user"`` copy, so the AI text and
# its study history (reviews, attempts) are never lost.


def validate_quiz_shape(question_type: str, options: list[str] | None, correct_answer: str) -> None:
    """Check a quiz question's type, options and answer agree.

    Args:
        question_type: ``multiple_choice`` or ``short_answer``.
        options: Option strings (multiple choice only).
        correct_answer: An option's text, or its letter (``"B"``) for multiple choice.

    Raises:
        ValueError: When the combination is not a coherent question.
    """
    if question_type not in QUIZ_TYPES:
        raise ValueError(f"question_type must be one of {QUIZ_TYPES}")
    answer = correct_answer.strip()
    if not answer:
        raise ValueError("correct_answer is required")
    if question_type == "short_answer":
        if options:
            raise ValueError("short_answer questions take no options")
        return
    if not options or not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise ValueError(f"multiple_choice needs {MIN_OPTIONS}-{MAX_OPTIONS} options")
    if any(not o.strip() for o in options):
        raise ValueError("options must not be blank")
    letters = [chr(ord("A") + i) for i in range(len(options))]
    if answer not in [o.strip() for o in options] and answer.upper() not in letters:
        raise ValueError("correct_answer must be one of the options or its letter")


async def _owned_item(session: AsyncSession, model, item_id: str, user_id: str):
    """Load the caller's active item, or raise ItemNotFoundError (no oracle)."""
    result = await session.execute(
        select(model)
        .join(Course, model.course_id == Course.id)
        .where(model.id == item_id, model.archived_at.is_(None), Course.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise ItemNotFoundError(item_id)
    return item


async def _resolve_manual_target(
    session: AsyncSession,
    *,
    user_id: str,
    course_code: str,
    week: int,
    source_artifact_id: str | None,
) -> tuple[str, str]:
    """Return (course_id, source_artifact_id) for a manual item, owner-scoped."""
    course = await course_service.get_course_by_code(session, course_code, user_id=user_id)
    if course is None:
        raise ItemNotFoundError(course_code)
    query = select(LectureArtifact.id).where(
        LectureArtifact.user_id == user_id,
        LectureArtifact.course_id == course.id,
        LectureArtifact.week == week,
    )
    if source_artifact_id is not None:
        query = query.where(LectureArtifact.id == source_artifact_id)
    result = await session.execute(
        query.order_by(LectureArtifact.created_at.desc(), LectureArtifact.id.desc()).limit(1)
    )
    artifact_id = result.scalar_one_or_none()
    if artifact_id is None:
        if source_artifact_id is not None:
            raise ItemNotFoundError(source_artifact_id)
        raise NoSourceArtifactError
    return course.id, artifact_id


async def create_flashcard(
    session: AsyncSession,
    *,
    user_id: str,
    course_code: str,
    week: int,
    front: str,
    back: str,
    tags: list[str] | None = None,
    source_artifact_id: str | None = None,
) -> Flashcard:
    """Create a manual flashcard (``origin="user"``) in the caller's course and week.

    Raises:
        ItemNotFoundError: Course or explicit source artifact is not the caller's.
        NoSourceArtifactError: The course has no lecture in that week.
    """
    course_id, artifact_id = await _resolve_manual_target(
        session,
        user_id=user_id,
        course_code=course_code,
        week=week,
        source_artifact_id=source_artifact_id,
    )
    card = Flashcard(
        id=generate_id(),
        course_id=course_id,
        week=week,
        front=front,
        back=back,
        tags=tags or [],
        source_artifact_id=artifact_id,
        source_page_ref=USER_ITEM_PAGE_REF,
        generation_version=1,
        origin="user",
    )
    session.add(card)
    await session.commit()
    await session.refresh(card)
    logger.info("flashcard_created_by_user", flashcard_id=card.id, course_id=course_id, week=week)
    return card


async def update_flashcard(
    session: AsyncSession,
    flashcard_id: str,
    *,
    user_id: str,
    front: str | None = None,
    back: str | None = None,
    tags: list[str] | None = None,
) -> Flashcard:
    """Edit a card by archiving the original and inserting an edited ``user`` copy.

    The SRS schedule is copied to the new card so an edit does not reset
    progress; the original keeps its review row as history.

    Raises:
        ItemNotFoundError: Not the caller's, missing, or already archived.
    """
    original = await _owned_item(session, Flashcard, flashcard_id, user_id)
    review = (
        await session.execute(
            select(FlashcardReview).where(
                FlashcardReview.flashcard_id == original.id, FlashcardReview.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    copy = Flashcard(
        id=generate_id(),
        course_id=original.course_id,
        week=original.week,
        front=original.front if front is None else front,
        back=original.back if back is None else back,
        tags=original.tags if tags is None else tags,
        source_artifact_id=original.source_artifact_id,
        source_page_ref=original.source_page_ref,
        generation_version=original.generation_version,
        origin="user",
        focus_topic=original.focus_topic,
    )
    original.archived_at = datetime.now(UTC)
    session.add(copy)
    await session.flush()
    if review is not None:
        session.add(
            FlashcardReview(
                id=generate_id(),
                user_id=user_id,
                flashcard_id=copy.id,
                ease_factor=review.ease_factor,
                interval_days=review.interval_days,
                repetition_count=review.repetition_count,
                next_review_at=review.next_review_at,
                last_reviewed_at=review.last_reviewed_at,
            )
        )
    await session.commit()
    await session.refresh(copy)
    logger.info("flashcard_edited_by_user", archived_id=original.id, new_id=copy.id)
    return copy


async def archive_flashcard(session: AsyncSession, flashcard_id: str, *, user_id: str) -> None:
    """Soft-delete the caller's flashcard (sets ``archived_at``; reviews stay).

    Raises:
        ItemNotFoundError: Not the caller's, missing, or already archived.
    """
    card = await _owned_item(session, Flashcard, flashcard_id, user_id)
    card.archived_at = datetime.now(UTC)
    await session.commit()
    logger.info("flashcard_archived_by_user", flashcard_id=flashcard_id)


async def create_quiz_question(
    session: AsyncSession,
    *,
    user_id: str,
    course_code: str,
    week: int,
    question_type: str,
    question: str,
    options: list[str] | None,
    correct_answer: str,
    explanation: str = "",
    source_artifact_id: str | None = None,
) -> QuizQuestion:
    """Create a manual quiz question (``origin="user"``).

    Raises:
        ValueError: Incoherent type/options/answer.
        ItemNotFoundError: Course or explicit source artifact is not the caller's.
        NoSourceArtifactError: The course has no lecture in that week.
    """
    validate_quiz_shape(question_type, options, correct_answer)
    course_id, artifact_id = await _resolve_manual_target(
        session,
        user_id=user_id,
        course_code=course_code,
        week=week,
        source_artifact_id=source_artifact_id,
    )
    record = QuizQuestion(
        id=generate_id(),
        course_id=course_id,
        week=week,
        question_type=question_type,
        question=question,
        options_json=options if question_type == "multiple_choice" else None,
        correct_answer=correct_answer.strip(),
        explanation=explanation,
        source_artifact_id=artifact_id,
        source_page_ref=USER_ITEM_PAGE_REF,
        generation_version=1,
        origin="user",
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    logger.info("quiz_question_created_by_user", question_id=record.id, course_id=course_id)
    return record


async def update_quiz_question(
    session: AsyncSession,
    question_id: str,
    *,
    user_id: str,
    question: str | None = None,
    options: list[str] | None = None,
    correct_answer: str | None = None,
    explanation: str | None = None,
) -> QuizQuestion:
    """Edit a question by archiving the original and inserting an edited ``user`` copy.

    Attempts stay on the archived original.

    Raises:
        ItemNotFoundError: Not the caller's, missing, or already archived.
        ValueError: The edited question is incoherent.
    """
    original = await _owned_item(session, QuizQuestion, question_id, user_id)
    new_options = original.options_json if options is None else options
    new_answer = original.correct_answer if correct_answer is None else correct_answer.strip()
    validate_quiz_shape(original.question_type, new_options, new_answer)
    copy = QuizQuestion(
        id=generate_id(),
        course_id=original.course_id,
        week=original.week,
        question_type=original.question_type,
        question=original.question if question is None else question,
        options_json=new_options,
        correct_answer=new_answer,
        explanation=original.explanation if explanation is None else explanation,
        source_artifact_id=original.source_artifact_id,
        source_page_ref=original.source_page_ref,
        generation_version=original.generation_version,
        origin="user",
        focus_topic=original.focus_topic,
    )
    original.archived_at = datetime.now(UTC)
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    logger.info("quiz_question_edited_by_user", archived_id=original.id, new_id=copy.id)
    return copy


async def archive_quiz_question(session: AsyncSession, question_id: str, *, user_id: str) -> None:
    """Soft-delete the caller's quiz question (sets ``archived_at``; attempts stay).

    Raises:
        ItemNotFoundError: Not the caller's, missing, or already archived.
    """
    record = await _owned_item(session, QuizQuestion, question_id, user_id)
    record.archived_at = datetime.now(UTC)
    await session.commit()
    logger.info("quiz_question_archived_by_user", question_id=question_id)


def _course_scope(*conditions, user_id: str):
    """Append the course-owner filter to a set of where() conditions.

    Course codes are unique per user, not globally, so any query that
    resolves a course by code must also pin the owner or it will match
    another user's course of the same code.
    """
    return (*conditions, Course.user_id == user_id)


async def get_flashcards_for_week(
    session: AsyncSession, course_code: str, week: int, *, user_id: str
) -> list[Flashcard]:
    """Get all flashcards for a specific course week.

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        week: Week number.
        user_id: Owner user UUID; only the course this user owns matches.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching assets by a caller-supplied code MUST
            pass this; omitting it returns every user's assets for that code.

    Returns:
        List of Flashcard records ordered by creation time.
    """
    result = await session.execute(
        select(Flashcard)
        .join(Course, Flashcard.course_id == Course.id)
        .where(
            Flashcard.archived_at.is_(None),
            *_course_scope(Course.code == course_code, Flashcard.week == week, user_id=user_id),
        )
        .order_by(Flashcard.created_at)
    )
    return list(result.scalars().all())


async def get_quiz_questions_for_week(
    session: AsyncSession, course_code: str, week: int, *, user_id: str
) -> list[QuizQuestion]:
    """Get all quiz questions for a specific course week.

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        week: Week number.
        user_id: Owner user UUID; only the course this user owns matches.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching assets by a caller-supplied code MUST
            pass this; omitting it returns every user's assets for that code.

    Returns:
        List of QuizQuestion records ordered by creation time.
    """
    result = await session.execute(
        select(QuizQuestion)
        .join(Course, QuizQuestion.course_id == Course.id)
        .where(
            QuizQuestion.archived_at.is_(None),
            *_course_scope(Course.code == course_code, QuizQuestion.week == week, user_id=user_id),
        )
        .order_by(QuizQuestion.created_at)
    )
    return list(result.scalars().all())


async def get_flashcards_for_course(
    session: AsyncSession, course_code: str, *, user_id: str
) -> list[Flashcard]:
    """Get all flashcards for a course (all weeks).

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        user_id: Owner user UUID; only the course this user owns matches.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching assets by a caller-supplied code MUST
            pass this; omitting it returns every user's assets for that code.

    Returns:
        List of Flashcard records ordered by week then creation time.
    """
    result = await session.execute(
        select(Flashcard)
        .join(Course, Flashcard.course_id == Course.id)
        .where(
            Flashcard.archived_at.is_(None),
            *_course_scope(Course.code == course_code, user_id=user_id),
        )
        .order_by(Flashcard.week, Flashcard.created_at)
    )
    return list(result.scalars().all())


async def get_quiz_questions_for_course(
    session: AsyncSession, course_code: str, *, user_id: str
) -> list[QuizQuestion]:
    """Get all quiz questions for a course (all weeks).

    Args:
        session: Database session.
        course_code: Course code (e.g., "CSIT302").
        user_id: Owner user UUID; only the course this user owns matches.
            Course codes are unique *per user* (uq_courses_code_user), so a
            code like "CSIT302" resolves to a different course for every
            user. Endpoints reaching assets by a caller-supplied code MUST
            pass this; omitting it returns every user's assets for that code.

    Returns:
        List of QuizQuestion records ordered by week then creation time.
    """
    result = await session.execute(
        select(QuizQuestion)
        .join(Course, QuizQuestion.course_id == Course.id)
        .where(
            QuizQuestion.archived_at.is_(None),
            *_course_scope(Course.code == course_code, user_id=user_id),
        )
        .order_by(QuizQuestion.week, QuizQuestion.created_at)
    )
    return list(result.scalars().all())
