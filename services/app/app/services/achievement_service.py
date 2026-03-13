"""Achievement checking and management service."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import generate_id
from app.models.achievement import Achievement
from app.models.user_achievement import UserAchievement
from app.models.user_xp import UserXP
from app.models.xp_event import XPEvent

logger = structlog.get_logger()


async def _evaluate_criteria(
    session: AsyncSession,
    user_id: str,
    criteria: dict,
) -> bool:
    """Evaluate whether a user meets achievement criteria.

    Args:
        session: Database session.
        user_id: User UUID.
        criteria: Criteria dict with type and threshold.

    Returns:
        True if criteria are met.
    """
    criteria_type = criteria.get("type")
    threshold = criteria.get("threshold", 0)

    if criteria_type == "count":
        event_type = criteria.get("event_type", "")
        result = await session.execute(
            select(func.count(XPEvent.id)).where(
                XPEvent.user_id == user_id, XPEvent.event_type == event_type
            )
        )
        count = result.scalar() or 0
        return count >= threshold

    elif criteria_type == "streak":
        from app.services import streak_service

        streak_data = await streak_service.get_streak(session, user_id=user_id)
        return streak_data.get("current_streak", 0) >= threshold

    elif criteria_type == "total_xp":
        result = await session.execute(select(UserXP.total_xp).where(UserXP.user_id == user_id))
        total = result.scalar() or 0
        return total >= threshold

    elif criteria_type == "level":
        result = await session.execute(select(UserXP.level).where(UserXP.user_id == user_id))
        level = result.scalar() or 1
        return level >= threshold

    return False


async def check_achievements(
    session: AsyncSession,
    user_id: str,
    event_type: str,
) -> list[UserAchievement]:
    """Check for newly unlockable achievements after an XP event.

    Args:
        session: Database session.
        user_id: User UUID.
        event_type: The event type that just occurred.

    Returns:
        List of newly earned UserAchievement records.
    """
    # Get all achievements the user has NOT yet earned
    earned_subq = select(UserAchievement.achievement_id).where(UserAchievement.user_id == user_id)
    result = await session.execute(select(Achievement).where(Achievement.id.not_in(earned_subq)))
    unearned = result.scalars().all()

    newly_earned: list[UserAchievement] = []

    for achievement in unearned:
        criteria = achievement.criteria_json
        if await _evaluate_criteria(session, user_id, criteria):
            ua = UserAchievement(
                id=generate_id(),
                user_id=user_id,
                achievement_id=achievement.id,
                earned_at=datetime.now(UTC),
                notified=False,
            )
            session.add(ua)
            newly_earned.append(ua)

            # Award bonus XP for the achievement (if any)
            if achievement.xp_reward > 0:
                from app.models.user_xp import UserXP as UserXPModel
                from app.models.xp_event import XPEvent as XPEventModel
                from app.services.xp_service import calculate_level

                bonus_event = XPEventModel(
                    id=generate_id(),
                    user_id=user_id,
                    event_type="achievement_bonus",
                    xp_amount=achievement.xp_reward,
                    metadata_json={"achievement_code": achievement.code},
                )
                session.add(bonus_event)

                # Update user XP
                xp_result = await session.execute(
                    select(UserXPModel).where(UserXPModel.user_id == user_id)
                )
                user_xp = xp_result.scalar_one_or_none()
                if user_xp:
                    user_xp.total_xp += achievement.xp_reward
                    user_xp.level = calculate_level(user_xp.total_xp)

            logger.info(
                "achievement_unlocked",
                user_id=user_id,
                achievement_code=achievement.code,
                xp_reward=achievement.xp_reward,
            )

    if newly_earned:
        await session.flush()

    return newly_earned


async def get_all_with_status(session: AsyncSession, user_id: str) -> list[dict]:
    """Get all achievements with earned status for a user.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        List of achievement dicts with earned_at field (None if unearned).
    """
    result = await session.execute(select(Achievement).order_by(Achievement.category))
    achievements = result.scalars().all()

    # Get user's earned achievements
    earned_result = await session.execute(
        select(UserAchievement).where(UserAchievement.user_id == user_id)
    )
    earned_map = {ua.achievement_id: ua for ua in earned_result.scalars().all()}

    items = []
    for a in achievements:
        ua = earned_map.get(a.id)
        items.append(
            {
                "id": a.id,
                "code": a.code,
                "title": a.title,
                "description": a.description,
                "icon": a.icon,
                "category": a.category,
                "xp_reward": a.xp_reward,
                "earned": ua is not None,
                "earned_at": ua.earned_at.isoformat() if ua else None,
            }
        )

    return items


async def get_unnotified(session: AsyncSession, user_id: str) -> list[dict]:
    """Get achievements earned but not yet shown to the user.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        List of dicts with achievement info and user_achievement_id.
    """
    result = await session.execute(
        select(UserAchievement, Achievement)
        .join(Achievement, UserAchievement.achievement_id == Achievement.id)
        .where(
            UserAchievement.user_id == user_id,
            UserAchievement.notified == False,  # noqa: E712
        )
    )
    rows = result.all()

    return [
        {
            "user_achievement_id": ua.id,
            "code": ach.code,
            "title": ach.title,
            "description": ach.description,
            "icon": ach.icon,
            "xp_reward": ach.xp_reward,
            "earned_at": ua.earned_at.isoformat(),
        }
        for ua, ach in rows
    ]


async def mark_notified(session: AsyncSession, user_achievement_ids: list[str]) -> None:
    """Mark achievements as notified.

    Args:
        session: Database session.
        user_achievement_ids: List of UserAchievement IDs to mark.
    """
    if not user_achievement_ids:
        return

    result = await session.execute(
        select(UserAchievement).where(UserAchievement.id.in_(user_achievement_ids))
    )
    for ua in result.scalars().all():
        ua.notified = True
    await session.flush()
