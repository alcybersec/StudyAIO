"""Single source of wall-clock time (ADR 0006, R-023 clock policy).

Stored timestamps are always UTC. "Today" for user-facing features (streaks,
study history, daily challenge, due-today, exam countdown, per-user analytics)
is the user's local day, derived from ``user_settings.timezone``. Quota,
billing and admin/platform stats use the UTC day.

Nothing outside this module may call ``date.today()``, naive
``datetime.now()``, ``datetime.utcnow()`` or ``datetime.today()``.
"""

import importlib.resources
from datetime import UTC, date, datetime, tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Return the current instant as an aware UTC datetime."""
    return datetime.now(UTC)


def utc_today() -> date:
    """Return today's date in UTC."""
    return utc_now().date()


def _zone(tz: str | None) -> tzinfo:
    """Resolve an IANA name to a zone; None or invalid falls back to UTC."""
    if tz is None or not valid_timezone(tz):
        return UTC
    try:
        return ZoneInfo(tz)
    except Exception:
        return UTC


def user_now(tz: str | None) -> datetime:
    """Return the current instant as an aware datetime in the user's zone."""
    return utc_now().astimezone(_zone(tz))


def user_today(tz: str | None) -> date:
    """Return today's date in the user's zone (UTC when tz is None/invalid)."""
    return user_now(tz).date()


@lru_cache(maxsize=1)
def _known_zones() -> frozenset[str]:
    """Zone keys of the declared ``tzdata`` package, independent of the host."""
    text = importlib.resources.files("tzdata").joinpath("zones").read_text()
    return frozenset(line.strip() for line in text.splitlines() if line.strip())


def valid_timezone(tz: str) -> bool:
    """True iff `tz` is a key of the tzdata package's zone list. Never raises."""
    try:
        return isinstance(tz, str) and tz in _known_zones()
    except Exception:
        return False
