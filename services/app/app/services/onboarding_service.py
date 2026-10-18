"""First-run onboarding status (`api.onboarding v1`, M34-S3-BACKEND-012).

Only the checklist preference is stored (``users.onboarding_checklist``);
every step is derived on read from the caller's own rows. Every query here is
filtered on the caller (floor 1): ``quiz_attempts`` has no ``user_id``, so that
branch is scoped through ``quiz_questions`` to ``courses.user_id``.
"""

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.flashcard_review import FlashcardReview
from app.models.quiz import QuizQuestion
from app.models.quiz_attempt import QuizAttempt
from app.models.summary import Summary
from app.models.usage_event import UsageEvent
from app.models.user import User

ONBOARDING_CHECKLIST_STATES = ("auto", "dismissed", "pinned")
ONBOARDING_PHASES = ("new", "processing", "has_summary", "done")
ONBOARDING_STEP_STATUSES = ("done", "active", "locked")


@dataclass(frozen=True)
class SummaryTarget:
    course_id: str
    course_code: str
    week: int


@dataclass(frozen=True)
class OnboardingStatus:
    phase: str
    upload: str
    summary: str
    check_in: str
    summary_target: SummaryTarget | None
    checklist: str
    visible: bool


def derive_status(
    *,
    uploaded: bool,
    summary_target: SummaryTarget | None,
    summary_read: bool,
    check_in_done: bool,
    checklist: str,
) -> OnboardingStatus:
    """Turn the caller's facts into the checklist state (pure).

    Args:
        uploaded: The caller has any lecture artifact.
        summary_target: The first summary the caller can open, if any.
        summary_read: The caller has viewed a summary.
        check_in_done: The caller has reviewed a card or answered a quiz question.
        checklist: The stored preference (auto, dismissed, pinned).

    Returns:
        The derived status.
    """
    if check_in_done:
        phase = "done"
        upload = summary = check_in = "done"
    elif summary_target is not None:
        phase = "has_summary"
        upload = "done"
        summary = "done" if summary_read else "active"
        check_in = "active"
    elif uploaded:
        phase = "processing"
        upload, summary, check_in = "done", "locked", "locked"
    else:
        phase = "new"
        upload, summary, check_in = "active", "locked", "locked"
    visible = checklist != "dismissed" and (phase != "done" or checklist == "pinned")
    return OnboardingStatus(
        phase=phase,
        upload=upload,
        summary=summary,
        check_in=check_in,
        summary_target=summary_target,
        checklist=checklist,
        visible=visible,
    )


async def get_status(session: AsyncSession, *, user_id: str) -> OnboardingStatus:
    """Derive the caller's onboarding status from their own rows.

    Args:
        session: Database session.
        user_id: The caller; every query is filtered on it.

    Returns:
        The caller's status.
    """
    checklist = await session.scalar(select(User.onboarding_checklist).where(User.id == user_id))
    uploaded = bool(
        await session.scalar(
            select(LectureArtifact.id).where(LectureArtifact.user_id == user_id).limit(1)
        )
    )
    target_row = (
        await session.execute(
            select(Course.id, Course.code, Summary.week)
            .join(Course, Course.id == Summary.course_id)
            .where(Course.user_id == user_id, Course.archived_at.is_(None))
            .order_by(Course.code, Summary.week)
            .limit(1)
        )
    ).first()
    target = (
        SummaryTarget(course_id=target_row[0], course_code=target_row[1], week=target_row[2])
        if target_row
        else None
    )
    summary_read = bool(
        await session.scalar(
            select(UsageEvent.id)
            .where(UsageEvent.user_id == user_id, UsageEvent.event == "summary_viewed")
            .limit(1)
        )
    )
    reviewed = await session.scalar(
        select(FlashcardReview.id).where(FlashcardReview.user_id == user_id).limit(1)
    )
    attempted = reviewed or await session.scalar(
        select(QuizAttempt.id)
        .join(QuizQuestion, QuizQuestion.id == QuizAttempt.quiz_question_id)
        .join(Course, Course.id == QuizQuestion.course_id)
        .where(Course.user_id == user_id)
        .limit(1)
    )
    return derive_status(
        uploaded=uploaded or target is not None,
        summary_target=target,
        summary_read=summary_read,
        check_in_done=bool(attempted),
        checklist=checklist if checklist in ONBOARDING_CHECKLIST_STATES else "auto",
    )


async def set_checklist(session: AsyncSession, *, user_id: str, checklist: str) -> OnboardingStatus:
    """Store the caller's checklist preference and return the new status.

    Args:
        session: Database session.
        user_id: The caller; the only row written.
        checklist: One of ``ONBOARDING_CHECKLIST_STATES``.

    Returns:
        The caller's status after the change.

    Raises:
        ValueError: ``checklist`` is not an allowed state.
    """
    if checklist not in ONBOARDING_CHECKLIST_STATES:
        raise ValueError(f"unknown checklist state: {checklist!r}")
    await session.execute(
        update(User).where(User.id == user_id).values(onboarding_checklist=checklist)
    )
    await session.commit()
    return await get_status(session, user_id=user_id)
