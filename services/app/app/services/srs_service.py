"""SM-2 spaced repetition algorithm and study session queries."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.utils import generate_id
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview

logger = structlog.get_logger()


@dataclass
class SM2Result:
    """Result of an SM-2 calculation."""

    ease_factor: float
    interval_days: int
    repetition_count: int


@dataclass
class StudyStats:
    """Aggregated study statistics."""

    total: int
    due_today: int
    mastered: int
    learning: int
    new: int


def calculate_sm2(
    quality: int,
    ease_factor: float = 2.5,
    interval_days: int = 0,
    repetition_count: int = 0,
) -> SM2Result:
    """Apply the SM-2 algorithm to compute next review parameters.

    Args:
        quality: Rating 0-5 (0=complete blackout, 5=perfect).
        ease_factor: Current ease factor (min 1.3).
        interval_days: Current interval in days.
        repetition_count: Number of consecutive correct reviews.

    Returns:
        SM2Result with updated ease_factor, interval_days, repetition_count.
    """
    quality = max(0, min(5, quality))

    # Update ease factor
    new_ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ef = max(1.3, new_ef)

    if quality < 3:
        # Failed: reset
        new_interval = 1
        new_reps = 0
    else:
        new_reps = repetition_count + 1
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 6
        else:
            new_interval = round(interval_days * new_ef)

    return SM2Result(
        ease_factor=round(new_ef, 4),
        interval_days=new_interval,
        repetition_count=new_reps,
    )


async def get_due_cards(
    session: AsyncSession,
    course_code: str | None = None,
    week: int | None = None,
    limit: int = 20,
    user_id: str | None = None,
) -> list[Flashcard]:
    """Get flashcards due for review.

    Returns cards that have never been reviewed (new) or are overdue,
    ordered with new cards first, then most overdue.

    Args:
        session: Database session.
        course_code: Optional course code filter.
        week: Optional week filter.
        limit: Maximum cards to return.

    Returns:
        List of Flashcard objects due for review.
    """
    now = datetime.utcnow()

    query = (
        select(Flashcard)
        .outerjoin(FlashcardReview, Flashcard.id == FlashcardReview.flashcard_id)
        .join(Course, Flashcard.course_id == Course.id)
        .where(
            (FlashcardReview.id.is_(None)) | (FlashcardReview.next_review_at <= now)
        )
        .order_by(
            # New cards (no review) first, then most overdue
            FlashcardReview.next_review_at.asc().nulls_first()
        )
        .limit(limit)
    )

    if user_id:
        query = query.where(Course.user_id == user_id)
    if course_code:
        query = query.where(Course.code == course_code)
    if week is not None:
        query = query.where(Flashcard.week == week)

    result = await session.execute(query)
    return list(result.scalars().all())


async def record_review(
    session: AsyncSession,
    flashcard_id: str,
    quality: int,
    user_id: str | None = None,
) -> FlashcardReview:
    """Record a flashcard review and update scheduling via SM-2.

    Creates a new FlashcardReview if first review, or updates existing.

    Args:
        session: Database session.
        flashcard_id: The flashcard being reviewed.
        quality: Rating 0-5.

    Returns:
        Updated FlashcardReview record.
    """
    now = datetime.utcnow()

    # Find existing review
    result = await session.execute(
        select(FlashcardReview).where(FlashcardReview.flashcard_id == flashcard_id)
    )
    review = result.scalar_one_or_none()

    if review:
        sm2 = calculate_sm2(quality, review.ease_factor, review.interval_days, review.repetition_count)
        review.ease_factor = sm2.ease_factor
        review.interval_days = sm2.interval_days
        review.repetition_count = sm2.repetition_count
        review.next_review_at = now + timedelta(days=sm2.interval_days)
        review.last_reviewed_at = now
        review.updated_at = now
    else:
        sm2 = calculate_sm2(quality)
        review = FlashcardReview(
            id=generate_id(),
            user_id=user_id or "",
            flashcard_id=flashcard_id,
            ease_factor=sm2.ease_factor,
            interval_days=sm2.interval_days,
            repetition_count=sm2.repetition_count,
            next_review_at=now + timedelta(days=sm2.interval_days),
            last_reviewed_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(review)

    await session.flush()

    logger.info(
        "review_recorded",
        flashcard_id=flashcard_id,
        quality=quality,
        interval_days=sm2.interval_days,
        ease_factor=sm2.ease_factor,
        repetition_count=sm2.repetition_count,
    )
    return review


async def get_study_stats(
    session: AsyncSession,
    course_code: str | None = None,
    week: int | None = None,
    user_id: str | None = None,
) -> StudyStats:
    """Get study statistics for a scope.

    Args:
        session: Database session.
        course_code: Optional course code filter.
        week: Optional week filter.

    Returns:
        StudyStats with total, due_today, mastered, learning, new counts.
    """
    now = datetime.utcnow()

    # Base query for total flashcards in scope
    base = select(Flashcard).join(Course, Flashcard.course_id == Course.id)
    if user_id:
        base = base.where(Course.user_id == user_id)
    if course_code:
        base = base.where(Course.code == course_code)
    if week is not None:
        base = base.where(Flashcard.week == week)

    # Total
    total_result = await session.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar() or 0

    # Cards with reviews
    reviewed_base = (
        select(Flashcard.id, FlashcardReview.interval_days, FlashcardReview.next_review_at)
        .join(FlashcardReview, Flashcard.id == FlashcardReview.flashcard_id)
        .join(Course, Flashcard.course_id == Course.id)
    )
    if user_id:
        reviewed_base = reviewed_base.where(Course.user_id == user_id)
    if course_code:
        reviewed_base = reviewed_base.where(Course.code == course_code)
    if week is not None:
        reviewed_base = reviewed_base.where(Flashcard.week == week)

    reviewed_result = await session.execute(reviewed_base)
    reviewed_rows = reviewed_result.all()

    mastered = 0
    learning = 0
    due_today = 0

    for _fid, interval, next_review in reviewed_rows:
        if interval > 21:
            mastered += 1
        else:
            learning += 1
        if next_review <= now:
            due_today += 1

    new_count = total - len(reviewed_rows)
    # New cards are also due
    due_today += new_count

    return StudyStats(
        total=total,
        due_today=due_today,
        mastered=mastered,
        learning=learning,
        new=new_count,
    )


async def get_global_study_stats(
    session: AsyncSession, user_id: str | None = None
) -> StudyStats:
    """Get study statistics across all courses.

    Returns:
        StudyStats aggregated across the entire flashcard pool.
    """
    return await get_study_stats(session, user_id=user_id)


async def get_per_course_due_counts(
    session: AsyncSession,
    user_id: str | None = None,
) -> list[dict]:
    """Get due card counts grouped by course.

    Returns:
        List of dicts with course_code and due_count.
    """
    now = datetime.utcnow()

    # New cards (no review record) per course
    new_query = (
        select(Course.code, func.count(Flashcard.id))
        .join(Flashcard, Course.id == Flashcard.course_id)
        .outerjoin(FlashcardReview, Flashcard.id == FlashcardReview.flashcard_id)
        .where(FlashcardReview.id.is_(None))
    )
    if user_id:
        new_query = new_query.where(Course.user_id == user_id)
    new_query = new_query.group_by(Course.code)
    new_result = await session.execute(new_query)
    new_counts = {code: count for code, count in new_result.all()}

    # Overdue cards per course
    overdue_query = (
        select(Course.code, func.count(Flashcard.id))
        .join(Flashcard, Course.id == Flashcard.course_id)
        .join(FlashcardReview, Flashcard.id == FlashcardReview.flashcard_id)
        .where(FlashcardReview.next_review_at <= now)
    )
    if user_id:
        overdue_query = overdue_query.where(Course.user_id == user_id)
    overdue_query = overdue_query.group_by(Course.code)
    overdue_result = await session.execute(overdue_query)
    overdue_counts = {code: count for code, count in overdue_result.all()}

    all_codes = set(new_counts.keys()) | set(overdue_counts.keys())
    return [
        {"course_code": code, "due_count": new_counts.get(code, 0) + overdue_counts.get(code, 0)}
        for code in sorted(all_codes)
    ]
