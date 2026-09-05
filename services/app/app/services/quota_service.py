"""Quota enforcement service for tier-based feature gating.

Two independent layers:

* **Per-tier limits** bound what one account may consume. They are read from
  config so an operator can retune a beta without editing source, and they are
  skipped in self-hosted mode and for tiers configured as unlimited.
* **The global ceiling** bounds what the *instance* spends in a day. It is an
  operator cost guard rather than a plan feature, so it deliberately applies to
  every tier and in self-hosted mode too — N users times their individual limits
  is otherwise unbounded in aggregate. It is scoped to users on "StudyAIO
  provided": a user running their own provider key costs the operator nothing,
  so neither their spend nor their requests belong in a bill guard. Their
  per-tier limits still apply — those are abuse control, not cost control.

Usage is recorded for everyone regardless. Metering answers "what happened",
enforcement answers "who pays"; conflating them would make a BYO user's work
invisible to admin analytics and to their own tier limits.

Both are enforced at the API edge. The pipeline records usage as it goes but is
never blocked mid-run, so an accepted upload always finishes rather than leaving
an artifact with a summary and no flashcards.
"""

from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import GlobalCeilingError, QuotaExceededError
from app.models.course import Course
from app.models.usage_record import UsageRecord
from app.models.user_settings import UserSettings
from app.services import settings_service

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
    """Sum today's AI calls and tokens spent on the *instance's* credentials.

    `usage_records` is indexed on `record_date`, so this is a cheap aggregate
    and needs no separate counter table.

    Users running their own provider are excluded: their spend is not the
    operator's, and counting it would let one BYO user exhaust the bill guard
    for everybody. A row with no `user_settings`, or none naming a provider,
    is on "StudyAIO provided" — which is the default — so it counts.

    The user's *current* selection decides, which is a deliberate
    simplification: a same-day switch reattributes that day's earlier calls.
    Recording each row's provider would be exact, but a daily counter that
    flips mid-day cannot be made exact without splitting the row, and the
    ceiling is a coarse guard.

    Args:
        session: Database session.

    Returns:
        (ai_calls, total_tokens) for today, instance-funded only.
    """
    selected = UserSettings.settings_json["agent_backend"].astext
    result = await session.execute(
        select(
            func.coalesce(func.sum(UsageRecord.ai_calls_count), 0),
            func.coalesce(func.sum(UsageRecord.ai_tokens_input + UsageRecord.ai_tokens_output), 0),
        )
        .select_from(UsageRecord)
        .outerjoin(UserSettings, UserSettings.user_id == UsageRecord.user_id)
        .where(
            UsageRecord.record_date == date.today(),
            or_(selected.is_(None), selected == settings_service.STUDYAIO_BACKEND),
        )
    )
    calls, tokens = result.one()
    return int(calls), int(tokens)


# ── Global ceiling ───────────────────────────────────────────────────


async def check_global_ai_ceiling(session: AsyncSession) -> None:
    """Check the instance-wide daily AI ceiling.

    Applies to every tier and in self-hosted mode: it protects the operator's
    bill, which a per-user limit cannot do. Callers scope it to users on
    "StudyAIO provided" — see the module docstring.

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
    if await settings_service.uses_instance_provider(session, user_id):
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
    if await settings_service.uses_instance_provider(session, user_id):
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
