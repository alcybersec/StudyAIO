"""Quota enforcement service for tier-based feature gating.

Two independent layers:

* **Per-tier limits** bound what one account may consume. They are read from
  config so an operator can retune a beta without editing source, and they are
  skipped in self-hosted mode and for tiers configured as unlimited.
* **The global ceiling** bounds what the *instance* spends in a day. It is an
  operator cost guard rather than a plan feature, so it deliberately applies to
  every tier and in self-hosted mode too — N users times their individual limits
  is otherwise unbounded in aggregate.

Both are enforced at the API edge. The pipeline records usage as it goes but is
never blocked mid-run, so an accepted upload always finishes rather than leaving
an artifact with a summary and no flashcards.
"""

from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import GlobalCeilingError, QuotaExceededError
from app.models.course import Course
from app.models.usage_record import UsageRecord

logger = structlog.get_logger()

#: AI calls a single upload costs once the pipeline runs: classify, summarize,
#: flashcards, quiz. Used to check a user can afford a whole run before the
#: upload is accepted, rather than failing a stage halfway through.
PIPELINE_AI_CALLS_PER_UPLOAD = 4


def _limit_for(tier: str, resource: str) -> int:
    """Resolve a configured limit for a tier.

    Args:
        tier: "free" or "pro". Unknown tiers fall back to the free limits.
        resource: "courses", "uploads_per_month" or "ai_calls_per_day".

    Returns:
        The limit; 0 means unlimited.
    """
    prefix = "pro" if tier == "pro" else "free"
    return int(getattr(settings, f"{prefix}_max_{resource}", 0) or 0)


def _seconds_until_utc_midnight() -> int:
    """Seconds until the daily counters reset."""
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


# ── Usage reads ──────────────────────────────────────────────────────


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


async def get_global_usage_today(session: AsyncSession) -> tuple[int, int]:
    """Sum AI calls and tokens across every user for today.

    `usage_records` is indexed on `record_date`, so this is a cheap aggregate
    and needs no separate counter table.

    Args:
        session: Database session.

    Returns:
        (ai_calls, total_tokens) for today.
    """
    result = await session.execute(
        select(
            func.coalesce(func.sum(UsageRecord.ai_calls_count), 0),
            func.coalesce(func.sum(UsageRecord.ai_tokens_input + UsageRecord.ai_tokens_output), 0),
        ).where(UsageRecord.record_date == date.today())
    )
    calls, tokens = result.one()
    return int(calls), int(tokens)


# ── Global ceiling ───────────────────────────────────────────────────


async def check_global_ai_ceiling(session: AsyncSession) -> None:
    """Check the instance-wide daily AI ceiling.

    Applies to every tier and in self-hosted mode: it protects the operator's
    bill, which a per-user limit cannot do.

    Args:
        session: Database session.

    Raises:
        GlobalCeilingError: If the call or token ceiling is reached.
    """
    call_ceiling = int(settings.global_max_ai_calls_per_day or 0)
    token_ceiling = int(settings.global_max_ai_tokens_per_day or 0)
    if call_ceiling <= 0 and token_ceiling <= 0:
        return

    calls, tokens = await get_global_usage_today(session)

    if call_ceiling > 0 and calls >= call_ceiling:
        logger.warning("global_ai_ceiling_reached", resource="AI call", used=calls)
        raise GlobalCeilingError("AI call", call_ceiling, _seconds_until_utc_midnight())

    if token_ceiling > 0 and tokens >= token_ceiling:
        logger.warning("global_ai_ceiling_reached", resource="AI token", used=tokens)
        raise GlobalCeilingError("AI token", token_ceiling, _seconds_until_utc_midnight())


# ── Per-tier quotas ──────────────────────────────────────────────────


async def check_upload_quota(session: AsyncSession, user_id: str, user_tier: str) -> None:
    """Check if a user can upload a file.

    Args:
        session: Database session.
        user_id: The user's ID.
        user_tier: The user's tier (free/pro).

    Raises:
        GlobalCeilingError: If the instance-wide ceiling is reached.
        QuotaExceededError: If the user's upload quota is exceeded.
    """
    await check_global_ai_ceiling(session)

    limit = _limit_for(user_tier, "uploads_per_month")
    if settings.self_hosted or limit <= 0:
        return

    monthly_uploads = await get_monthly_upload_count(session, user_id)
    if monthly_uploads >= limit:
        raise QuotaExceededError(resource="uploads", limit=limit, period="month")


async def check_ai_quota(
    session: AsyncSession, user_id: str, user_tier: str, calls: int = 1
) -> None:
    """Check if a user can make AI calls.

    Args:
        session: Database session.
        user_id: The user's ID.
        user_tier: The user's tier (free/pro).
        calls: How many calls the caller is about to spend. Uploads pass
            `PIPELINE_AI_CALLS_PER_UPLOAD` so a whole pipeline run is checked up
            front instead of failing a stage partway through.

    Raises:
        GlobalCeilingError: If the instance-wide ceiling is reached.
        QuotaExceededError: If the user's daily AI quota is exceeded.
    """
    await check_global_ai_ceiling(session)

    limit = _limit_for(user_tier, "ai_calls_per_day")
    if settings.self_hosted or limit <= 0:
        return

    usage = await get_usage_today(session, user_id)
    ai_calls = usage.ai_calls_count if usage else 0
    if ai_calls + calls > limit:
        raise QuotaExceededError(resource="ai_calls", limit=limit, period="day")


async def check_course_quota(session: AsyncSession, user_id: str, user_tier: str) -> None:
    """Check if a user can create a new course.

    Args:
        session: Database session.
        user_id: The user's ID.
        user_tier: The user's tier (free/pro).

    Raises:
        QuotaExceededError: If the course quota is exceeded.
    """
    limit = _limit_for(user_tier, "courses")
    if settings.self_hosted or limit <= 0:
        return

    count = await get_course_count(session, user_id)
    if count >= limit:
        raise QuotaExceededError(resource="courses", limit=limit, period="account")
