"""Adaptive study schedule generation based on exam proximity."""

from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam
from app.models.flashcard import Flashcard
from app.models.flashcard_review import FlashcardReview
from app.services.exam_service import get_weak_topics

logger = structlog.get_logger()

# Priority multipliers for card targets based on days remaining
PRIORITY_THRESHOLDS = [
    (3, "critical", 2.0),
    (7, "high", 1.5),
    (14, "medium", 1.2),
    (float("inf"), "low", 1.0),
]

BASE_QUIZ_TARGET = 5


def _get_priority(days_remaining: int) -> tuple[str, float]:
    """Get priority label and multiplier based on days remaining."""
    for threshold, label, multiplier in PRIORITY_THRESHOLDS:
        if days_remaining <= threshold:
            return label, multiplier
    return "low", 1.0


async def generate_study_schedule(
    session: AsyncSession,
    exam_id: str,
    days_ahead: int = 7,
) -> list[dict] | None:
    """Generate an adaptive daily study plan for the next N days.

    Algorithm:
    - Priority based on days_remaining (critical/high/medium/low)
    - Base cards = min(30, total_due / days_remaining + 5), scaled by priority
    - focus_weeks = weak topics first, then round-robin remaining weeks
    - Quiz target: base 5, scaled by priority

    Args:
        session: Database session.
        exam_id: Exam UUID.
        days_ahead: Number of days to plan (default 7).

    Returns:
        List of daily plan dicts, or None if exam not found.
    """
    result = await session.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    if not exam:
        return None

    now = datetime.utcnow()
    days_remaining = max(0, (exam.exam_date - now).days)

    # Total due cards in scope
    due_count_result = await session.execute(
        select(func.count(Flashcard.id))
        .outerjoin(FlashcardReview, Flashcard.id == FlashcardReview.flashcard_id)
        .where(
            Flashcard.course_id == exam.course_id,
            Flashcard.week.in_(exam.weeks_scope),
            (FlashcardReview.id.is_(None)) | (FlashcardReview.next_review_at <= now),
        )
    )
    total_due = due_count_result.scalar() or 0

    # Weak topics
    weak_topics = await get_weak_topics(session, exam.course_id, exam.weeks_scope)
    weak_weeks = [w["week"] for w in weak_topics]
    strong_weeks = [w for w in exam.weeks_scope if w not in weak_weeks]

    schedule = []
    today = date.today()

    for day_offset in range(days_ahead):
        plan_date = today + timedelta(days=day_offset)
        days_until_exam = max(0, (exam.exam_date.date() - plan_date).days)

        priority_label, multiplier = _get_priority(days_until_exam)

        # Calculate card target
        if days_until_exam > 0:
            base_cards = min(30, total_due // days_until_exam + 5)
        else:
            base_cards = min(30, total_due + 5)
        card_target = round(base_cards * multiplier)

        # Quiz target
        quiz_target = round(BASE_QUIZ_TARGET * multiplier)

        # Focus weeks: rotate through weak weeks first, then strong
        if weak_weeks:
            week_idx = day_offset % len(weak_weeks)
            focus = [weak_weeks[week_idx]]
            # Add a second weak week if critical
            if priority_label in ("critical", "high") and len(weak_weeks) > 1:
                focus.append(weak_weeks[(week_idx + 1) % len(weak_weeks)])
        elif strong_weeks:
            focus = [strong_weeks[day_offset % len(strong_weeks)]]
        else:
            focus = list(exam.weeks_scope[:2]) if exam.weeks_scope else []

        schedule.append({
            "date": plan_date.isoformat(),
            "days_until_exam": days_until_exam,
            "priority": priority_label,
            "card_target": card_target,
            "quiz_target": quiz_target,
            "focus_weeks": focus,
        })

    return schedule


async def get_daily_study_plan(
    session: AsyncSession,
    exam_id: str,
) -> dict | None:
    """Get today's study plan for an exam.

    Args:
        session: Database session.
        exam_id: Exam UUID.

    Returns:
        Today's plan dict, or None if exam not found.
    """
    schedule = await generate_study_schedule(session, exam_id, days_ahead=1)
    if not schedule:
        return None
    return schedule[0]
