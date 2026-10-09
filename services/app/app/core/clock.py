"""Single source of wall-clock time (ADR 0006, R-023 clock policy).

Stored timestamps are always UTC. "Today" for user-facing features (streaks,
study history, daily challenge, due-today, exam countdown, per-user analytics)
is the user's local day, derived from ``user_settings.timezone``. Quota,
billing and admin/platform stats use the UTC day.

Nothing outside this module may call ``date.today()``, naive
``datetime.now()``, ``datetime.utcnow()`` or ``datetime.today()``.
"""

from datetime import UTC, date, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"


def utc_now() -> datetime:
    """Return the current instant as an aware UTC datetime."""
    return datetime.now(UTC)


def utc_today() -> date:
    """Return today's date in UTC."""
    return utc_now().date()


def _zone(tz: str | None) -> tzinfo:
    """Resolve an IANA name to a zone; None or invalid falls back to UTC."""
    if not valid_timezone(tz or ""):
        return UTC
    return ZoneInfo(tz or "")


def user_now(tz: str | None) -> datetime:
    """Return the current instant as an aware datetime in the user's zone."""
    return utc_now().astimezone(_zone(tz))


def user_today(tz: str | None) -> date:
    """Return today's date in the user's zone (UTC when tz is None/invalid)."""
    return user_now(tz).date()


def valid_timezone(tz: str) -> bool:
    """Return True when ``tz`` is a known IANA zone name."""
    if not isinstance(tz, str) or not tz or tz.startswith(("/", ".")) or ".." in tz:
        return False
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True
