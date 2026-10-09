"""Local-day bounds in UTC (ADR 0006 Decision 3).

A "due today" style question is answered by comparing stored UTC instants with
the UTC instants of the user's local-day boundary; the column is never cast.
"""

from datetime import UTC, datetime, time, timedelta

from app.core.clock import user_now, user_today


def local_day_end_utc(tz: str | None) -> datetime:
    """Return the UTC instant at which the user's current local day ends.

    Args:
        tz: IANA time zone of the user (UTC if None/invalid).

    Returns:
        Aware UTC datetime of the next local midnight (exclusive upper bound).
    """
    next_midnight = datetime.combine(
        user_today(tz) + timedelta(days=1), time.min, tzinfo=user_now(tz).tzinfo
    )
    return next_midnight.astimezone(UTC)
