"""API routes for study assets (flashcards and quiz questions)."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.asset_item_schemas import (
    FlashcardCreate,
    FlashcardUpdate,
    QuizQuestionCreate,
    QuizQuestionUpdate,
)
from app.api.deps import get_current_user_or_default
from app.api.schemas import FlashcardResponse, QuizQuestionResponse
from app.core.database import get_session
from app.models.user import User
from app.services import asset_service
from app.services.asset_service import ItemNotFoundError, NoSourceArtifactError

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
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[FlashcardResponse]:
    """Get flashcards for a course, optionally filtered by week."""
    if week is not None:
        flashcards = await asset_service.get_flashcards_for_week(
            session, course_code, week, user_id=user.id
        )
    else:
        flashcards = await asset_service.get_flashcards_for_course(
            session, course_code, user_id=user.id
        )

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
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[QuizQuestionResponse]:
    """Get quiz questions for a course, optionally filtered by week."""
    if week is not None:
        questions = await asset_service.get_quiz_questions_for_week(
            session, course_code, week, user_id=user.id
        )
    else:
        questions = await asset_service.get_quiz_questions_for_course(
            session, course_code, user_id=user.id
        )

    return [QuizQuestionResponse.model_validate(q) for q in questions]


# ── user-authored items (GL#48) ──────────────────────────────────


def _not_found() -> HTTPException:
    """One 404 for every miss: foreign, missing and archived are indistinguishable."""
    return HTTPException(status_code=404, detail="Not found")


@router.post(
    "/assets/flashcards",
    response_model=FlashcardResponse,
    status_code=201,
    summary="Add a flashcard",
    description="Creates a manual flashcard (origin=user) in the caller's course and week.",
)
async def create_flashcard(
    body: FlashcardCreate,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> FlashcardResponse:
    """Create a manual flashcard."""
    try:
        card = await asset_service.create_flashcard(session, user_id=user.id, **body.model_dump())
    except ItemNotFoundError:
        raise _not_found() from None
    except NoSourceArtifactError:
        raise HTTPException(status_code=409, detail="no_source_artifact") from None
    return FlashcardResponse.model_validate(card)


@router.patch(
    "/assets/flashcards/{flashcard_id}",
    response_model=FlashcardResponse,
    summary="Edit a flashcard",
    description=(
        "Archives the original and returns an edited copy (new id, origin=user). "
        "Nothing is destroyed; the SRS schedule carries over."
    ),
)
async def update_flashcard(
    flashcard_id: str,
    body: FlashcardUpdate,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> FlashcardResponse:
    """Edit a flashcard (archive and copy)."""
    try:
        card = await asset_service.update_flashcard(
            session, flashcard_id, user_id=user.id, **body.model_dump(exclude_unset=True)
        )
    except ItemNotFoundError:
        raise _not_found() from None
    return FlashcardResponse.model_validate(card)


@router.delete(
    "/assets/flashcards/{flashcard_id}",
    status_code=204,
    summary="Delete a flashcard",
    description="Archives the flashcard (soft delete); its review history is kept.",
)
async def delete_flashcard(
    flashcard_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Archive a flashcard."""
    try:
        await asset_service.archive_flashcard(session, flashcard_id, user_id=user.id)
    except ItemNotFoundError:
        raise _not_found() from None
    return Response(status_code=204)


@router.post(
    "/assets/quiz",
    response_model=QuizQuestionResponse,
    status_code=201,
    summary="Add a quiz question",
    description="Creates a manual quiz question (origin=user) in the caller's course and week.",
)
async def create_quiz_question(
    body: QuizQuestionCreate,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> QuizQuestionResponse:
    """Create a manual quiz question."""
    try:
        question = await asset_service.create_quiz_question(
            session, user_id=user.id, **body.model_dump()
        )
    except ItemNotFoundError:
        raise _not_found() from None
    except NoSourceArtifactError:
        raise HTTPException(status_code=409, detail="no_source_artifact") from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return QuizQuestionResponse.model_validate(question)


@router.patch(
    "/assets/quiz/{question_id}",
    response_model=QuizQuestionResponse,
    summary="Edit a quiz question",
    description=(
        "Archives the original and returns an edited copy (new id, origin=user). "
        "Attempts stay on the archived original."
    ),
)
async def update_quiz_question(
    question_id: str,
    body: QuizQuestionUpdate,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> QuizQuestionResponse:
    """Edit a quiz question (archive and copy)."""
    try:
        question = await asset_service.update_quiz_question(
            session, question_id, user_id=user.id, **body.model_dump(exclude_unset=True)
        )
    except ItemNotFoundError:
        raise _not_found() from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return QuizQuestionResponse.model_validate(question)


@router.delete(
    "/assets/quiz/{question_id}",
    status_code=204,
    summary="Delete a quiz question",
    description="Archives the question (soft delete); its attempts are kept.",
)
async def delete_quiz_question(
    question_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Archive a quiz question."""
    try:
        await asset_service.archive_quiz_question(session, question_id, user_id=user.id)
    except ItemNotFoundError:
        raise _not_found() from None
    return Response(status_code=204)
