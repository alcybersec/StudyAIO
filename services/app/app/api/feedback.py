"""Feedback API — one endpoint for users, two for admins."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.config import settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.feedback import FEEDBACK_KINDS, FEEDBACK_STATUSES
from app.models.user import User
from app.services import feedback_service

logger = structlog.get_logger()

router = APIRouter()


class FeedbackRequest(BaseModel):
    """What the reporter sends."""

    kind: str = Field(description=f"One of: {', '.join(FEEDBACK_KINDS)}")
    message: str = Field(
        min_length=1,
        max_length=feedback_service.MAX_MESSAGE_LENGTH,
        description="What they want to say.",
    )
    #: Supplied by the client because the server cannot know which view they
    #: were looking at — the request lands on /api/feedback either way.
    route: str | None = Field(default=None, max_length=500)
    app_version: str | None = Field(default=None, max_length=64)


class FeedbackResponse(BaseModel):
    """One piece of feedback."""

    id: str
    kind: str
    message: str
    route: str | None
    app_version: str | None
    status: str
    created_at: str | None
    #: Admin listings only. Absent on the submitter's own acknowledgement,
    #: which does not need to tell them who they are.
    user_email: str | None = None


class FeedbackListResponse(BaseModel):
    """A page of feedback, newest first."""

    items: list[FeedbackResponse]
    total: int
    offset: int
    limit: int
    #: Per-status totals, so the admin UI can show how much is unread without a
    #: second request.
    counts: dict[str, int]


class FeedbackStatusRequest(BaseModel):
    """Move one piece through triage."""

    status: str = Field(description=f"One of: {', '.join(FEEDBACK_STATUSES)}")


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=201,
    summary="Send feedback",
    description=(
        "Report a bug, suggest something, or say what was confusing. "
        "Rate limited. Linked admins are pinged on Telegram, best effort."
    ),
)
@limiter.limit(lambda: settings.rate_limit_feedback)
async def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FeedbackResponse:
    """Record feedback from the current user."""
    try:
        entry = await feedback_service.submit_feedback(
            session,
            user.id,
            kind=body.kind,
            message=body.message,
            route=body.route,
            app_version=body.app_version,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await session.commit()

    # After the commit, so a Telegram outage cannot roll back stored feedback —
    # and so the ping can never arrive describing something that was not saved.
    await feedback_service.notify_admins(session, entry, user.email)

    return FeedbackResponse(
        id=entry.id,
        kind=entry.kind,
        message=entry.message,
        route=entry.route,
        app_version=entry.app_version,
        status=entry.status,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
    )


@router.get(
    "/admin/feedback",
    response_model=FeedbackListResponse,
    summary="List feedback",
    description="Everything users have sent, newest first. Admin only.",
)
async def list_feedback(
    status: str | None = Query(None, description=f"Filter: {', '.join(FEEDBACK_STATUSES)}"),
    kind: str | None = Query(None, description=f"Filter: {', '.join(FEEDBACK_KINDS)}"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> FeedbackListResponse:
    """List feedback (admin only)."""
    rows, total = await feedback_service.list_feedback(
        session, status=status, kind=kind, offset=offset, limit=limit
    )
    return FeedbackListResponse(
        items=[
            FeedbackResponse(
                id=r.id,
                kind=r.kind,
                message=r.message,
                route=r.route,
                app_version=r.app_version,
                status=r.status,
                created_at=r.created_at.isoformat() if r.created_at else None,
                user_email=r.user.email if r.user else None,
            )
            for r in rows
        ],
        total=total,
        offset=offset,
        limit=limit,
        counts=await feedback_service.count_by_status(session),
    )


@router.patch(
    "/admin/feedback/{feedback_id}",
    response_model=FeedbackResponse,
    summary="Triage feedback",
    description="Move one piece of feedback to triaged or closed. Admin only.",
)
async def set_feedback_status(
    feedback_id: str,
    body: FeedbackStatusRequest,
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> FeedbackResponse:
    """Change a feedback item's triage status (admin only)."""
    try:
        entry = await feedback_service.set_status(session, feedback_id, body.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if entry is None:
        raise HTTPException(status_code=404, detail="Feedback not found")

    await session.commit()
    return FeedbackResponse(
        id=entry.id,
        kind=entry.kind,
        message=entry.message,
        route=entry.route,
        app_version=entry.app_version,
        status=entry.status,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
    )
