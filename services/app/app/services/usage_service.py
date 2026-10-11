"""Per-feature usage events for retention (M33-S1-BACKEND-016, GL#37).

Events carry no content and no PII: the event name comes from a fixed
allowlist, and `properties` is restricted to a few scalar values under an
allowlisted key set, so a call site cannot smuggle lecture text, an answer, an
email or a free-form note into the table. `record` never raises into the
caller's request: a failure is logged and counted, and the request carries on.
"""

import math
import re
from datetime import UTC, date, datetime, timedelta

import structlog
from prometheus_client import Counter
from sqlalchemy import Date, Integer, cast, func, literal_column, select, type_coerce
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.usage_event import UsageEvent
from app.models.user import User

logger = structlog.get_logger()

USAGE_EVENTS = frozenset(
    {
        "summary_viewed",
        "study_plan_viewed",
        "quiz_answered",
        "quiz_completed",
        "flashcard_reviewed",
        "chat_message_sent",
        "upload_completed",
        "feedback_given",
    }
)
#: The only events a client may report: pure views, which no server action implies.
CLIENT_EVENTS = frozenset({"summary_viewed", "study_plan_viewed"})

ALLOWED_PROPERTY_KEYS = frozenset(
    {
        "week",
        "count",
        "correct",
        "quality",
        "is_correct",
        "duration_seconds",
        "target_type",
        "rating",
        "stream",
    }
)
MAX_PROPERTY_KEYS = 6
_TOKEN = re.compile(r"[a-z0-9_.-]{1,40}")

#: Accounts that are not real users of the product.
_EXCLUDED_ROLES = ("admin", "demo")
#: Retention checkpoints, in days after signup.
RETENTION_DAYS = (1, 7, 30)

# Label is a fixed enum: recorded | rejected | error.
USAGE_EVENTS_TOTAL = Counter("studyaio_usage_events_total", "Usage events by outcome.", ["outcome"])


def _valid_properties(properties: dict) -> bool:
    if len(properties) > MAX_PROPERTY_KEYS:
        return False
    for key, value in properties.items():
        if key not in ALLOWED_PROPERTY_KEYS:
            return False
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            continue
        if isinstance(value, float) and math.isfinite(value):
            continue
        if isinstance(value, str) and _TOKEN.fullmatch(value):
            continue
        return False
    return True


async def record(
    session: AsyncSession,
    user_id: str,
    event: str,
    *,
    course_id: str | None = None,
    properties: dict | None = None,
) -> bool:
    """Append one usage event. Never raises.

    The row is flushed inside a savepoint, so a failure cannot poison the
    caller's transaction. The caller owns the commit.

    Args:
        session: Database session.
        user_id: The acting user.
        event: A member of `USAGE_EVENTS`.
        course_id: The course the action concerned, if any.
        properties: Small scalar values under `ALLOWED_PROPERTY_KEYS`.

    Returns:
        True if the event was stored, False if it was rejected or failed.
    """
    props = properties or {}
    if event not in USAGE_EVENTS or not _valid_properties(props):
        USAGE_EVENTS_TOTAL.labels(outcome="rejected").inc()
        logger.warning("usage_event_rejected", event_name=event if event in USAGE_EVENTS else None)
        return False
    try:
        async with session.begin_nested():
            session.add(
                UsageEvent(user_id=user_id, event=event, course_id=course_id, properties=props)
            )
            await session.flush()
    except Exception:
        USAGE_EVENTS_TOTAL.labels(outcome="error").inc()
        logger.warning("usage_event_failed", event_name=event, exc_info=True)
        return False
    USAGE_EVENTS_TOTAL.labels(outcome="recorded").inc()
    return True


# ── Retention readout ────────────────────────────────────────────────


def week_start(moment: datetime | date) -> date:
    """The Monday (UTC) of the week containing `moment`."""
    day = moment.astimezone(UTC).date() if isinstance(moment, datetime) else moment
    return day - timedelta(days=day.weekday())


def build_cohorts(
    signups: list[tuple[date, int]],
    active: dict[date, dict[int, int]],
    *,
    today: date,
) -> list[dict]:
    """Combine signup counts and per-day active counts into cohort rows.

    A checkpoint is reported as None (unknown) until the cohort's first day has
    reached it: zero would claim nobody came back when the question is not yet
    answerable.

    Args:
        signups: (week_start, signups) per cohort.
        active: week_start -> {day offset -> distinct users with any event}.
        today: The current UTC date.

    Returns:
        Cohort dicts, oldest first.
    """
    rows = []
    for start, count in sorted(signups):
        counts = active.get(start, {})
        row: dict = {"week_start": start.isoformat(), "signups": count}
        for days in RETENTION_DAYS:
            known = start + timedelta(days=days) <= today
            row[f"d{days}"] = counts.get(days, 0) if known else None
        rows.append(row)
    return rows


def _utc(column):
    """The column as a UTC wall-clock timestamp (`AT TIME ZONE 'UTC'`)."""
    return column.op("AT TIME ZONE")(literal_column("'UTC'"))


def _utc_date(column):
    return cast(_utc(column), Date)


async def retention_readout(session: AsyncSession, *, weeks: int = 8) -> dict:
    """Weekly signup cohorts with D1/D7/D30 activity, and weekly active users per feature.

    Admin and demo accounts are excluded. "Active on day N" means any event on
    the calendar day (UTC) N days after the signup date.
    """
    today = utc_today()
    first_week = week_start(today) - timedelta(weeks=weeks - 1)
    window_start = datetime(first_week.year, first_week.month, first_week.day, tzinfo=UTC)
    real_user = User.role.not_in(_EXCLUDED_ROLES)

    cohort_week = func.date_trunc("week", _utc(User.created_at))
    signup_rows = (
        await session.execute(
            select(cast(cohort_week, Date), func.count())
            .where(real_user, User.created_at >= window_start)
            .group_by(cohort_week)
        )
    ).all()

    offset = type_coerce(_utc_date(UsageEvent.occurred_at) - _utc_date(User.created_at), Integer)
    active_rows = (
        await session.execute(
            select(
                cast(cohort_week, Date),
                offset,
                func.count(func.distinct(UsageEvent.user_id)),
            )
            .join(User, User.id == UsageEvent.user_id)
            .where(
                real_user,
                User.created_at >= window_start,
                UsageEvent.occurred_at >= window_start,
                offset.in_(RETENTION_DAYS),
            )
            .group_by(cohort_week, offset)
        )
    ).all()
    active: dict[date, dict[int, int]] = {}
    for wk, days, users in active_rows:
        active.setdefault(wk, {})[days] = users

    event_week = func.date_trunc("week", _utc(UsageEvent.occurred_at))
    feature_rows = (
        await session.execute(
            select(
                cast(event_week, Date),
                UsageEvent.event,
                func.count(func.distinct(UsageEvent.user_id)),
            )
            .join(User, User.id == UsageEvent.user_id)
            .where(real_user, UsageEvent.occurred_at >= window_start)
            .group_by(event_week, UsageEvent.event)
            .order_by(event_week, UsageEvent.event)
        )
    ).all()

    return {
        "cohorts": build_cohorts([(wk, n) for wk, n in signup_rows], active, today=today),
        "features": [
            {"week_start": wk.isoformat(), "event": event, "active_users": users}
            for wk, event, users in feature_rows
        ],
    }
