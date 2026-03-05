"""API routes for spaced repetition study sessions."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.api.study_schemas import (
    DueCardResponse,
    QuizAttemptRequest,
    QuizAttemptResponse,
    ReviewRequest,
    ReviewResponse,
    StreakResponse,
    StudyStatsResponse,
    TimedPlanRequest,
    TimedPlanResponse,
)
from app.core.database import get_session
from app.models.flashcard import Flashcard
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services import (
    challenge_service,
    exam_service,
    srs_service,
    streak_service,
    timed_session_service,
    xp_service,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/study/due",
    response_model=list[DueCardResponse],
    summary="Get cards due for review",
    description="Returns flashcards due for spaced repetition review, with new cards first.",
)
async def get_due_cards(
    course_code: str | None = Query(None, description="Course code filter"),
    week: int | None = Query(None, description="Week number filter"),
    limit: int = Query(20, ge=1, le=100, description="Max cards to return"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[DueCardResponse]:
    """Get flashcards due for review."""
    cards = await srs_service.get_due_cards(session, course_code, week, limit, user_id=user.id)
    return [DueCardResponse.model_validate(c) for c in cards]


@router.post(
    "/study/review",
    response_model=ReviewResponse,
    summary="Record a flashcard review",
    description="Records a review with quality rating (0-5) and updates SM-2 scheduling.",
)
async def post_review(
    body: ReviewRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ReviewResponse:
    """Record a flashcard review."""
    # Verify flashcard exists
    result = await session.execute(
        select(Flashcard).where(Flashcard.id == body.flashcard_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Flashcard not found")

    review = await srs_service.record_review(session, body.flashcard_id, body.quality, user_id=user.id)
    await session.commit()

    # Award XP (best-effort)
    try:
        await xp_service.award_xp(session, user.id, "card_reviewed")
        await challenge_service.update_challenge_progress(session, user.id, "review_cards")
    except Exception:
        logger.warning("gamification_xp_failed", exc_info=True)

    return ReviewResponse.model_validate(review)


@router.get(
    "/study/stats",
    response_model=StudyStatsResponse,
    summary="Get study statistics",
    description="Returns study statistics (total, due, mastered, learning, new) for a scope.",
)
async def get_stats(
    course_code: str | None = Query(None, description="Course code filter"),
    week: int | None = Query(None, description="Week number filter"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> StudyStatsResponse:
    """Get study statistics for a scope."""
    stats = await srs_service.get_study_stats(session, course_code, week, user_id=user.id)
    return StudyStatsResponse(
        total=stats.total,
        due_today=stats.due_today,
        mastered=stats.mastered,
        learning=stats.learning,
        new=stats.new,
    )


@router.post(
    "/study/quiz-attempt",
    response_model=QuizAttemptResponse,
    status_code=201,
    summary="Record a quiz attempt",
    description="Records an answer to a quiz question with correctness tracking.",
)
async def post_quiz_attempt(
    body: QuizAttemptRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> QuizAttemptResponse:
    """Record a quiz attempt."""
    # Verify quiz question exists
    result = await session.execute(
        select(QuizQuestion).where(QuizQuestion.id == body.quiz_question_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Quiz question not found")

    attempt = await exam_service.record_quiz_attempt(
        session,
        quiz_question_id=body.quiz_question_id,
        selected_answer=body.selected_answer,
        is_correct=body.is_correct,
        exam_id=body.exam_id,
        time_spent_ms=body.time_spent_ms,
    )
    await session.commit()

    # Award XP for correct answers (best-effort)
    try:
        if body.is_correct:
            await xp_service.award_xp(session, user.id, "quiz_correct")
            await challenge_service.update_challenge_progress(session, user.id, "quiz_correct")
    except Exception:
        logger.warning("gamification_xp_failed", exc_info=True)

    return QuizAttemptResponse.model_validate(attempt)


@router.get(
    "/study/streak",
    response_model=StreakResponse,
    summary="Get study streak",
    description="Returns current and longest study streak data.",
)
async def get_streak(
    course_id: str | None = Query(None, description="Optional course ID filter"),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> StreakResponse:
    """Get study streak data."""
    data = await streak_service.get_streak(session, course_id, user_id=user.id)
    return StreakResponse(**data)


@router.post(
    "/study/timed-plan",
    response_model=TimedPlanResponse,
    summary="Generate a timed study plan",
    description="Given N minutes, generates an optimal mix of flashcards and quiz questions.",
)
async def generate_timed_plan(
    body: TimedPlanRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> TimedPlanResponse:
    """Generate a time-budgeted study plan."""
    plan = await timed_session_service.generate_timed_plan(
        session,
        total_minutes=body.minutes,
        course_code=body.course_code,
        exam_id=body.exam_id,
    )
    return TimedPlanResponse(
        total_minutes=plan.total_minutes,
        card_ids=plan.card_ids,
        quiz_ids=plan.quiz_ids,
        estimated_card_minutes=plan.estimated_card_minutes,
        estimated_quiz_minutes=plan.estimated_quiz_minutes,
        course_code=plan.course_code,
        exam_id=plan.exam_id,
    )
