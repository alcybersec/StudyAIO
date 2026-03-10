"""Quota enforcement service for tier-based feature gating."""

from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.course import Course
from app.models.usage_record import UsageRecord

logger = structlog.get_logger()

# Free tier limits
FREE_MAX_COURSES = 1
FREE_MAX_UPLOADS_PER_MONTH = 5
FREE_MAX_AI_CALLS_PER_DAY = 20


async def get_usage_today(session: AsyncSession, user_id: str) -> UsageRecord | None:
    """Get today's usage record for a user.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        Today's UsageRecord or None.
    """
    result = await session.execute(
        select(UsageRecord).where(
            UsageRecord.user_id == user_id,
            UsageRecord.record_date == date.today(),
        )
    )
    return result.scalar_one_or_none()


async def get_monthly_upload_count(session: AsyncSession, user_id: str) -> int:
    """Count uploads this calendar month for a user.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        Total uploads this month.
    """
    today = date.today()
    month_start = today.replace(day=1)

    result = await session.execute(
        select(func.coalesce(func.sum(UsageRecord.uploads_count), 0)).where(
            UsageRecord.user_id == user_id,
            UsageRecord.record_date >= month_start,
        )
    )
    return result.scalar_one()


async def get_course_count(session: AsyncSession, user_id: str) -> int:
    """Count courses owned by a user.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        Number of courses.
    """
    result = await session.execute(select(func.count(Course.id)).where(Course.user_id == user_id))
    return result.scalar_one()


async def check_upload_quota(session: AsyncSession, user_id: str, user_tier: str) -> None:
    """Check if user can upload a file.

    Args:
        session: Database session.
        user_id: The user's ID.
        user_tier: The user's tier (free/pro).

    Raises:
        QuotaExceededError: If upload quota exceeded.
    """
    if settings.self_hosted or user_tier == "pro":
        return

    monthly_uploads = await get_monthly_upload_count(session, user_id)
    if monthly_uploads >= FREE_MAX_UPLOADS_PER_MONTH:
        from app.core.exceptions import QuotaExceededError

        raise QuotaExceededError(
            resource="uploads",
            limit=FREE_MAX_UPLOADS_PER_MONTH,
            period="month",
        )


async def check_ai_quota(session: AsyncSession, user_id: str, user_tier: str) -> None:
    """Check if user can make an AI call.

    Args:
        session: Database session.
        user_id: The user's ID.
        user_tier: The user's tier (free/pro).

    Raises:
        QuotaExceededError: If AI call quota exceeded.
    """
    if settings.self_hosted or user_tier == "pro":
        return

    usage = await get_usage_today(session, user_id)
    ai_calls = usage.ai_calls_count if usage else 0
    if ai_calls >= FREE_MAX_AI_CALLS_PER_DAY:
        from app.core.exceptions import QuotaExceededError

        raise QuotaExceededError(
            resource="ai_calls",
            limit=FREE_MAX_AI_CALLS_PER_DAY,
            period="day",
        )


async def check_course_quota(session: AsyncSession, user_id: str, user_tier: str) -> None:
    """Check if user can create a new course.

    Args:
        session: Database session.
        user_id: The user's ID.
        user_tier: The user's tier (free/pro).

    Raises:
        QuotaExceededError: If course quota exceeded.
    """
    if settings.self_hosted or user_tier == "pro":
        return

    count = await get_course_count(session, user_id)
    if count >= FREE_MAX_COURSES:
        from app.core.exceptions import QuotaExceededError

        raise QuotaExceededError(
            resource="courses",
            limit=FREE_MAX_COURSES,
            period="account",
        )
