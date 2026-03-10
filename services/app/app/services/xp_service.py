"""XP and leveling service."""

from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import generate_id
from app.models.user import User
from app.models.user_xp import UserXP
from app.models.xp_event import XPEvent

logger = structlog.get_logger()

# Level thresholds: index = level, value = XP needed to reach that level
LEVEL_THRESHOLDS = [0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500]

# Default XP amounts per event type
XP_AMOUNTS: dict[str, int] = {
    "card_reviewed": 5,
    "quiz_correct": 10,
    "streak_day": 20,
    "upload": 15,
    "challenge_completed": 0,  # challenge XP comes from the challenge itself
    "achievement_bonus": 0,  # achievement XP comes from the achievement itself
}


def calculate_level(total_xp: int) -> int:
    """Calculate level from total XP.

    Args:
        total_xp: Total accumulated XP.

    Returns:
        Current level (1-based, uncapped above max threshold).
    """
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if total_xp >= threshold:
            level = i + 1
        else:
            break
    return level


def xp_for_next_level(level: int) -> tuple[int, int | None]:
    """Get XP thresholds for current and next level.

    Args:
        level: Current level.

    Returns:
        Tuple of (current_level_threshold, next_level_threshold or None if max).
    """
    idx = level - 1
    current = LEVEL_THRESHOLDS[idx] if idx < len(LEVEL_THRESHOLDS) else LEVEL_THRESHOLDS[-1]
    next_idx = idx + 1
    next_threshold = LEVEL_THRESHOLDS[next_idx] if next_idx < len(LEVEL_THRESHOLDS) else None
    return current, next_threshold


async def get_or_create_user_xp(session: AsyncSession, user_id: str) -> UserXP:
    """Get or create the UserXP record for a user.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        The UserXP record.
    """
    result = await session.execute(select(UserXP).where(UserXP.user_id == user_id))
    user_xp = result.scalar_one_or_none()

    if not user_xp:
        user_xp = UserXP(
            id=generate_id(),
            user_id=user_id,
            total_xp=0,
            level=1,
        )
        session.add(user_xp)
        await session.flush()

    return user_xp


async def award_xp(
    session: AsyncSession,
    user_id: str,
    event_type: str,
    xp_amount: int | None = None,
    metadata: dict | None = None,
) -> tuple[UserXP, XPEvent, list]:
    """Award XP to a user, update level, and check achievements.

    Args:
        session: Database session.
        user_id: User UUID.
        event_type: Type of event (card_reviewed, quiz_correct, etc.).
        xp_amount: Override XP amount (uses default if None).
        metadata: Optional metadata for the event.

    Returns:
        Tuple of (updated UserXP, new XPEvent, list of newly earned UserAchievements).
    """
    from app.services import achievement_service

    amount = xp_amount if xp_amount is not None else XP_AMOUNTS.get(event_type, 0)

    # Create the XP event
    event = XPEvent(
        id=generate_id(),
        user_id=user_id,
        event_type=event_type,
        xp_amount=amount,
        metadata_json=metadata,
    )
    session.add(event)

    # Update user XP total and level
    user_xp = await get_or_create_user_xp(session, user_id)
    user_xp.total_xp += amount
    old_level = user_xp.level
    user_xp.level = calculate_level(user_xp.total_xp)
    user_xp.updated_at = datetime.utcnow()
    await session.flush()

    if user_xp.level > old_level:
        logger.info(
            "level_up",
            user_id=user_id,
            old_level=old_level,
            new_level=user_xp.level,
        )

    # Check for newly unlocked achievements
    new_achievements = await achievement_service.check_achievements(session, user_id, event_type)

    await session.commit()

    logger.info(
        "xp_awarded",
        user_id=user_id,
        event_type=event_type,
        xp_amount=amount,
        total_xp=user_xp.total_xp,
        level=user_xp.level,
        new_achievements=len(new_achievements),
    )

    return user_xp, event, new_achievements


async def get_xp_summary(session: AsyncSession, user_id: str) -> dict:
    """Get XP summary for a user.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        Dict with total_xp, level, progress_pct, current_threshold,
        next_threshold, and recent_events.
    """
    user_xp = await get_or_create_user_xp(session, user_id)
    current_threshold, next_threshold = xp_for_next_level(user_xp.level)

    # Calculate progress percentage toward next level
    if next_threshold is not None:
        range_xp = next_threshold - current_threshold
        progress_xp = user_xp.total_xp - current_threshold
        progress_pct = round((progress_xp / range_xp) * 100, 1) if range_xp > 0 else 100.0
    else:
        progress_pct = 100.0

    # Get recent events (last 10)
    result = await session.execute(
        select(XPEvent)
        .where(XPEvent.user_id == user_id)
        .order_by(XPEvent.created_at.desc())
        .limit(10)
    )
    recent = result.scalars().all()

    return {
        "total_xp": user_xp.total_xp,
        "level": user_xp.level,
        "progress_pct": progress_pct,
        "current_threshold": current_threshold,
        "next_threshold": next_threshold,
        "recent_events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "xp_amount": e.xp_amount,
                "created_at": e.created_at.isoformat(),
            }
            for e in recent
        ],
    }


async def get_leaderboard(session: AsyncSession, limit: int = 10) -> list[dict]:
    """Get top users by XP.

    Args:
        session: Database session.
        limit: Max entries to return.

    Returns:
        List of dicts with user_id, username, total_xp, level.
    """
    result = await session.execute(
        select(UserXP, User.username)
        .join(User, UserXP.user_id == User.id)
        .order_by(UserXP.total_xp.desc())
        .limit(limit)
    )
    rows = result.all()

    return [
        {
            "user_id": row[0].user_id,
            "username": row[1],
            "total_xp": row[0].total_xp,
            "level": row[0].level,
            "rank": idx + 1,
        }
        for idx, row in enumerate(rows)
    ]
