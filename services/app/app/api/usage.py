"""Usage events API — client view events and the admin retention readout (GL#37)."""

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default, require_role
from app.config import settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.user import User
from app.services import course_service, usage_service

logger = structlog.get_logger()

router = APIRouter()


class UsageEventRequest(BaseModel):
    """A view event reported by the client. Nothing else is accepted."""

    model_config = ConfigDict(extra="forbid")

    event: Literal["summary_viewed", "study_plan_viewed"]
    course_id: str | None = Field(default=None, max_length=36)


class CohortRow(BaseModel):
    """One weekly signup cohort. A checkpoint is null until it can be known."""

    week_start: str
    signups: int
    d1: int | None
    d7: int | None
    d30: int | None


class FeatureRow(BaseModel):
    """Distinct users who used one feature in one week."""

    week_start: str
    event: str
    active_users: int


class PlanArm(BaseModel):
    """One arm of the plan split. A checkpoint is null until it can be known."""

    signups: int
    d7: int | None
    d30: int | None


class PlanSplitRow(BaseModel):
    """D7/D30 of a signup cohort's users with a study plan against those without."""

    week_start: str
    with_plan: PlanArm
    without_plan: PlanArm


class RetentionResponse(BaseModel):
    """Cohort retention, weekly active users per feature, and the plan split."""

    cohorts: list[CohortRow]
    features: list[FeatureRow]
    plan_split: list[PlanSplitRow] = []


@router.post(
    "/usage-events",
    status_code=204,
    summary="Report a view event",
    description="Records summary_viewed or study_plan_viewed for the caller. Rate limited.",
)
@limiter.limit(lambda: settings.rate_limit_usage_events)
async def post_usage_event(
    request: Request,
    body: UsageEventRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Record a client-reported view event."""
    if body.course_id is not None and not await course_service.get_course_by_id(
        session, body.course_id, user_id=user.id
    ):
        raise HTTPException(status_code=404, detail="Course not found")

    await usage_service.record(session, user.id, body.event, course_id=body.course_id)
    await session.commit()
    return Response(status_code=204)


@router.get(
    "/admin/usage/retention",
    response_model=RetentionResponse,
    summary="Retention readout",
    description=(
        "Weekly signup cohorts with D1/D7/D30 activity, and weekly active users per feature. "
        "Admin only; admin and demo accounts are excluded."
    ),
)
async def retention(
    weeks: int = Query(8, ge=1, le=26),
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> RetentionResponse:
    """Cohort retention readout (admin only)."""
    readout = await usage_service.retention_readout(session, weeks=weeks)
    split = await usage_service.plan_split_readout(session, weeks=weeks)
    return RetentionResponse(**readout, plan_split=split)
