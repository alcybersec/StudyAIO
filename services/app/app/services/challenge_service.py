"""Daily challenge service."""

from datetime import date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import generate_id
from app.models.daily_challenge import DailyChallenge
from app.models.user_daily_challenge import UserDailyChallenge

logger = structlog.get_logger()

CHALLENGE_TEMPLATES = [
    {"type": "review_cards", "desc": "Review {target} flashcards", "target": 10, "xp": 25},
    {"type": "quiz_correct", "desc": "Get {target} quiz questions correct", "target": 5, "xp": 30},
    {"type": "study_minutes", "desc": "Study for {target} minutes", "target": 15, "xp": 20},
    {"type": "review_cards", "desc": "Review {target} flashcards", "target": 25, "xp": 45},
    {"type": "quiz_correct", "desc": "Get {target} quiz questions correct", "target": 10, "xp": 50},
    {"type": "study_minutes", "desc": "Study for {target} minutes", "target": 30, "xp": 35},
    {"type": "perfect_quiz", "desc": "Get a perfect score on any quiz", "target": 1, "xp": 50},
]


async def get_or_create_daily_challenge(
    session: AsyncSession,
    target_date: date | None = None,
) -> DailyChallenge:
    """Get or create the daily challenge for a given date.

    Uses a deterministic hash of the date ordinal to select a template,
    ensuring the same challenge is generated for a given date.

    Args:
        session: Database session.
        target_date: Date for the challenge (defaults to today).

    Returns:
        The DailyChallenge record.
    """
    target_date = target_date or date.today()

    result = await session.execute(
        select(DailyChallenge).where(DailyChallenge.challenge_date == target_date)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    # Deterministic template selection
    template_idx = hash(target_date.toordinal()) % len(CHALLENGE_TEMPLATES)
    template = CHALLENGE_TEMPLATES[template_idx]

    challenge = DailyChallenge(
        id=generate_id(),
        challenge_date=target_date,
        challenge_type=template["type"],
        target=template["target"],
        description=template["desc"].format(target=template["target"]),
        xp_reward=template["xp"],
    )
    session.add(challenge)
    await session.flush()

    logger.info(
        "daily_challenge_created",
        date=target_date.isoformat(),
        challenge_type=template["type"],
        target=template["target"],
    )

    return challenge


async def get_user_challenge_progress(
    session: AsyncSession,
    user_id: str,
    target_date: date | None = None,
) -> dict:
    """Get today's challenge and user's progress.

    Args:
        session: Database session.
        user_id: User UUID.
        target_date: Date for the challenge (defaults to today).

    Returns:
        Dict with challenge info and user progress.
    """
    challenge = await get_or_create_daily_challenge(session, target_date)

    result = await session.execute(
        select(UserDailyChallenge).where(
            UserDailyChallenge.user_id == user_id,
            UserDailyChallenge.daily_challenge_id == challenge.id,
        )
    )
    user_challenge = result.scalar_one_or_none()

    return {
        "challenge_id": challenge.id,
        "challenge_date": challenge.challenge_date.isoformat(),
        "challenge_type": challenge.challenge_type,
        "target": challenge.target,
        "description": challenge.description,
        "xp_reward": challenge.xp_reward,
        "progress": user_challenge.progress if user_challenge else 0,
        "completed": user_challenge.completed_at is not None if user_challenge else False,
        "completed_at": (
            user_challenge.completed_at.isoformat()
            if user_challenge and user_challenge.completed_at
            else None
        ),
    }


async def update_challenge_progress(
    session: AsyncSession,
    user_id: str,
    challenge_type: str,
    increment: int = 1,
) -> UserDailyChallenge | None:
    """Update progress on today's challenge if it matches the given type.

    Args:
        session: Database session.
        user_id: User UUID.
        challenge_type: The type of activity (review_cards, quiz_correct, etc.).
        increment: Amount to add to progress.

    Returns:
        Updated UserDailyChallenge if matched, None otherwise.
    """
    challenge = await get_or_create_daily_challenge(session)

    if challenge.challenge_type != challenge_type:
        return None

    # Get or create user challenge progress
    result = await session.execute(
        select(UserDailyChallenge).where(
            UserDailyChallenge.user_id == user_id,
            UserDailyChallenge.daily_challenge_id == challenge.id,
        )
    )
    user_challenge = result.scalar_one_or_none()

    if not user_challenge:
        user_challenge = UserDailyChallenge(
            id=generate_id(),
            user_id=user_id,
            daily_challenge_id=challenge.id,
            progress=0,
        )
        session.add(user_challenge)

    # Don't increment if already completed
    if user_challenge.completed_at is not None:
        return user_challenge

    user_challenge.progress += increment

    # Check completion
    if user_challenge.progress >= challenge.target:
        user_challenge.completed_at = datetime.utcnow()

        # Award challenge XP
        from app.services import xp_service

        await xp_service.award_xp(
            session,
            user_id,
            "challenge_completed",
            xp_amount=challenge.xp_reward,
            metadata={"challenge_id": challenge.id},
        )

        logger.info(
            "daily_challenge_completed",
            user_id=user_id,
            challenge_type=challenge_type,
            xp_reward=challenge.xp_reward,
        )

    await session.flush()
    return user_challenge
