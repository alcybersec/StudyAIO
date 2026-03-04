"""Analytics API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analytics_schemas import (
    AnalyticsOverviewResponse,
    ExamReadinessResponse,
    HeatmapResponse,
    MasteryResponse,
    RetentionResponse,
)
from app.api.deps import get_current_user_or_default
from app.core.database import get_session
from app.models.user import User
from app.services import analytics_service

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/analytics/overview",
    response_model=AnalyticsOverviewResponse,
    summary="Get analytics overview",
    description="Returns aggregated study statistics including total hours, mastery, and session counts.",
)
async def get_overview(
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> AnalyticsOverviewResponse:
    """Get aggregated study statistics overview."""
    data = await analytics_service.get_overview(session, user.id)
    return AnalyticsOverviewResponse(**data)


@router.get(
    "/analytics/heatmap",
    response_model=HeatmapResponse,
    summary="Get study heatmap",
    description="Returns daily study totals for heatmap visualization.",
)
async def get_heatmap(
    days: int = Query(default=90, ge=7, le=365),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> HeatmapResponse:
    """Get daily study totals for heatmap display."""
    data = await analytics_service.get_study_heatmap(session, user.id, days=days)
    return HeatmapResponse(days=data)


@router.get(
    "/analytics/retention",
    response_model=RetentionResponse,
    summary="Get retention data",
    description="Returns retention curve data grouped by review interval buckets.",
)
async def get_retention(
    course_code: str | None = Query(default=None),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> RetentionResponse:
    """Get retention curve data."""
    data = await analytics_service.get_retention_data(
        session, user.id, course_code=course_code
    )
    return RetentionResponse(points=data)


@router.get(
    "/analytics/mastery",
    response_model=MasteryResponse,
    summary="Get mastery breakdown",
    description="Returns per-week mastery breakdown with flashcard status counts.",
)
async def get_mastery(
    course_code: str | None = Query(default=None),
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> MasteryResponse:
    """Get per-week mastery breakdown."""
    data = await analytics_service.get_mastery_breakdown(
        session, user.id, course_code=course_code
    )
    return MasteryResponse(weeks=data)


@router.get(
    "/analytics/readiness/{exam_id}",
    response_model=ExamReadinessResponse,
    summary="Get exam readiness",
    description="Returns weighted readiness score for a specific exam.",
)
async def get_readiness(
    exam_id: str,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> ExamReadinessResponse:
    """Get exam readiness score with component breakdown."""
    data = await analytics_service.get_exam_readiness(session, exam_id, user.id)
    if not data:
        raise HTTPException(status_code=404, detail="Exam not found")
    return ExamReadinessResponse(**data)
