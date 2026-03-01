"""API routes for study assets (flashcards and quiz questions)."""

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import FlashcardResponse, QuizQuestionResponse
from app.core.database import get_session
from app.services import asset_service

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/assets/flashcards",
    response_model=list[FlashcardResponse],
    summary="Get flashcards",
    description="Get flashcards for a course, optionally filtered by week.",
)
async def get_flashcards(
    course_code: str = Query(..., description="Course code (e.g. CSIT302)"),
    week: int | None = Query(None, description="Week number (omit for all weeks)"),
    session: AsyncSession = Depends(get_session),
) -> list[FlashcardResponse]:
    """Get flashcards for a course, optionally filtered by week."""
    if week is not None:
        flashcards = await asset_service.get_flashcards_for_week(session, course_code, week)
    else:
        flashcards = await asset_service.get_flashcards_for_course(session, course_code)

    return [FlashcardResponse.model_validate(fc) for fc in flashcards]


@router.get(
    "/assets/quiz",
    response_model=list[QuizQuestionResponse],
    summary="Get quiz questions",
    description="Get quiz questions for a course, optionally filtered by week.",
)
async def get_quiz_questions(
    course_code: str = Query(..., description="Course code (e.g. CSIT302)"),
    week: int | None = Query(None, description="Week number (omit for all weeks)"),
    session: AsyncSession = Depends(get_session),
) -> list[QuizQuestionResponse]:
    """Get quiz questions for a course, optionally filtered by week."""
    if week is not None:
        questions = await asset_service.get_quiz_questions_for_week(session, course_code, week)
    else:
        questions = await asset_service.get_quiz_questions_for_course(session, course_code)

    return [QuizQuestionResponse.model_validate(q) for q in questions]
