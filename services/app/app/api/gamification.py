"""API routes for gamification (XP, achievements, challenges, leaderboard)."""

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.api.gamification_schemas import (
    AchievementItem,
    AchievementsListResponse,
    DailyChallengeResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    MarkNotifiedRequest,
    UnnotifiedAchievement,
    XPSummaryResponse,
)
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.user import User
from app.services import achievement_service, challenge_service, xp_service

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/gamification/xp",
    response_model=XPSummaryResponse,
    summary="Get XP summary",
    description="Returns total XP, current level, progress toward next level, and recent XP events.",
)
@limiter.limit("30/minute")
async def get_xp_summary(
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> XPSummaryResponse:
    """Get XP summary for the current user."""
    summary = await xp_service.get_xp_summary(session, user.id)
    return XPSummaryResponse(**summary)


@router.get(
    "/gamification/achievements",
    response_model=AchievementsListResponse,
    summary="Get all achievements",
    description="Returns all achievements with earned/unearned status for the current user.",
)
@limiter.limit("30/minute")
async def get_achievements(
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> AchievementsListResponse:
    """Get all achievements with earned status."""
    items = await achievement_service.get_all_with_status(session, user.id)
    earned_count = sum(1 for i in items if i["earned"])
    return AchievementsListResponse(
        total=len(items),
        earned=earned_count,
        achievements=[AchievementItem(**i) for i in items],
    )


@router.get(
    "/gamification/challenges",
    response_model=DailyChallengeResponse,
    summary="Get today's challenge",
    description="Returns the daily challenge for today with the user's progress.",
)
@limiter.limit("30/minute")
async def get_daily_challenge(
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> DailyChallengeResponse:
    """Get today's challenge with progress."""
    progress = await challenge_service.get_user_challenge_progress(session, user.id)
    return DailyChallengeResponse(**progress)


@router.get(
    "/gamification/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get XP leaderboard",
    description="Returns top users ranked by total XP.",
)
@limiter.limit("30/minute")
async def get_leaderboard(
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> LeaderboardResponse:
    """Get global XP leaderboard."""
    entries = await xp_service.get_leaderboard(session)
    return LeaderboardResponse(
        entries=[LeaderboardEntry(**e) for e in entries],
    )


@router.get(
    "/gamification/achievements/unnotified",
    response_model=list[UnnotifiedAchievement],
    summary="Get unnotified achievements",
    description="Returns achievements earned but not yet shown to the user.",
)
@limiter.limit("30/minute")
async def get_unnotified_achievements(
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> list[UnnotifiedAchievement]:
    """Get unnotified achievements."""
    items = await achievement_service.get_unnotified(session, user.id)
    return [UnnotifiedAchievement(**i) for i in items]


@router.post(
    "/gamification/achievements/mark-notified",
    status_code=204,
    summary="Mark achievements as notified",
    description="Marks the given achievements as shown to the user.",
)
@limiter.limit("30/minute")
async def mark_achievements_notified(
    request: Request,
    body: MarkNotifiedRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Mark achievements as notified."""
    await achievement_service.mark_notified(session, body.user_achievement_ids)
    await session.commit()
