"""AI feedback API — thumbs up/down on summaries, answers, cards and quiz items (GL#36)."""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default, require_role
from app.core.database import get_session
from app.models.ai_feedback import AI_FEEDBACK_REASONS, AI_FEEDBACK_TARGET_TYPES, AIFeedback
from app.models.user import User
from app.services import ai_feedback_service, usage_service

logger = structlog.get_logger()

router = APIRouter()

MAX_LOOKUP_IDS = 100


class VoteRequest(BaseModel):
    """The caller's vote on one target."""

    target_type: str = Field(description=f"One of: {', '.join(AI_FEEDBACK_TARGET_TYPES)}")
    target_id: str = Field(min_length=1, max_length=36)
    rating: int = Field(description="1 for thumbs up, -1 for thumbs down")
    reason: str | None = Field(
        default=None,
        description=f"Thumbs-down only. One of: {', '.join(AI_FEEDBACK_REASONS)}",
    )
    comment: str | None = Field(default=None, max_length=ai_feedback_service.MAX_COMMENT_LENGTH)


class VoteResponse(BaseModel):
    """A stored vote."""

    target_type: str
    target_id: str
    rating: int
    reason: str | None
    comment: str | None
    course_id: str | None
    updated_at: datetime | None


class VoteListResponse(BaseModel):
    """The caller's votes for a set of targets."""

    items: list[VoteResponse]


class AdminAIFeedbackResponse(BaseModel):
    """Aggregates over everyone's votes. Carries no user identifiers."""

    total: int
    by_target_type: dict[str, dict[str, int]]
    by_reason: dict[str, int]
    by_rating: dict[str, int]
    recent_negative: list[dict]


def _vote_response(vote: AIFeedback) -> VoteResponse:
    return VoteResponse(
        target_type=vote.target_type,
        target_id=vote.target_id,
        rating=vote.rating,
        reason=vote.reason,
        comment=vote.comment,
        course_id=vote.course_id,
        updated_at=vote.updated_at,
    )


@router.put(
    "/feedback",
    response_model=VoteResponse,
    summary="Rate AI output",
    description=(
        "Upsert the caller's thumbs up/down on a summary, answer, flashcard, quiz question "
        "or chat message. 404 when the target is not the caller's."
    ),
)
async def put_vote(
    body: VoteRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> VoteResponse:
    """Store the caller's vote, replacing any earlier one on the same target."""
    try:
        vote = await ai_feedback_service.upsert_vote(
            session,
            user_id=user.id,
            target_type=body.target_type,
            target_id=body.target_id,
            rating=body.rating,
            reason=body.reason,
            comment=body.comment,
        )
    except ai_feedback_service.FeedbackTargetNotFoundError:
        raise HTTPException(status_code=404, detail="Target not found") from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Never the comment: it is free text.
    await usage_service.record(
        session,
        user.id,
        "feedback_given",
        course_id=vote.course_id,
        properties={"rating": vote.rating, "target_type": vote.target_type},
    )
    await session.commit()
    return _vote_response(vote)


@router.delete(
    "/feedback/{target_type}/{target_id}",
    status_code=204,
    summary="Remove a rating",
    description="Remove the caller's own vote on a target. 404 when there is none.",
)
async def delete_vote(
    target_type: str,
    target_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Remove the caller's own vote."""
    try:
        removed = await ai_feedback_service.delete_vote(
            session, user_id=user.id, target_type=target_type, target_id=target_id
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not removed:
        raise HTTPException(status_code=404, detail="Vote not found")
    await session.commit()
    return Response(status_code=204)


@router.get(
    "/feedback/mine",
    response_model=VoteListResponse,
    summary="List own ratings",
    description="The caller's votes on the given targets, so the UI can show state.",
)
async def list_my_votes(
    target_type: str = Query(...),
    target_ids: list[str] = Query(default=[], max_length=MAX_LOOKUP_IDS),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> VoteListResponse:
    """The caller's own votes for a set of targets."""
    try:
        votes = await ai_feedback_service.list_votes(
            session, user_id=user.id, target_type=target_type, target_ids=target_ids
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return VoteListResponse(items=[_vote_response(v) for v in votes])


@router.get(
    "/admin/ai-feedback",
    response_model=AdminAIFeedbackResponse,
    summary="AI feedback aggregates",
    description="Counts per target type, reason and rating, plus recent thumbs-down comments. Admin only.",
)
async def admin_ai_feedback(
    days: int = Query(30, ge=1, le=365),
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> AdminAIFeedbackResponse:
    """Aggregate AI feedback across users (admin only)."""
    summary = await ai_feedback_service.admin_summary(session, days=days)
    return AdminAIFeedbackResponse(**summary)
