"""API routes for spaced repetition study sessions."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.study_schemas import (
    DueCardResponse,
    ReviewRequest,
    ReviewResponse,
    StudyStatsResponse,
)
from app.core.database import get_session
from app.models.flashcard import Flashcard
from app.services import srs_service

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
    session: AsyncSession = Depends(get_session),
) -> list[DueCardResponse]:
    """Get flashcards due for review."""
    cards = await srs_service.get_due_cards(session, course_code, week, limit)
    return [DueCardResponse.model_validate(c) for c in cards]


@router.post(
    "/study/review",
    response_model=ReviewResponse,
    summary="Record a flashcard review",
    description="Records a review with quality rating (0-5) and updates SM-2 scheduling.",
)
async def post_review(
    body: ReviewRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewResponse:
    """Record a flashcard review."""
    # Verify flashcard exists
    result = await session.execute(
        select(Flashcard).where(Flashcard.id == body.flashcard_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Flashcard not found")

    review = await srs_service.record_review(session, body.flashcard_id, body.quality)
    await session.commit()
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
    session: AsyncSession = Depends(get_session),
) -> StudyStatsResponse:
    """Get study statistics for a scope."""
    stats = await srs_service.get_study_stats(session, course_code, week)
    return StudyStatsResponse(
        total=stats.total,
        due_today=stats.due_today,
        mastered=stats.mastered,
        learning=stats.learning,
        new=stats.new,
    )
