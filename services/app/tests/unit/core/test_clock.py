"""Unit tests for app.core.clock."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.core import clock

# 2026-03-10 23:30 UTC: Kiritimati (+14) is already 03-11.
FROZEN = datetime(2026, 3, 10, 23, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "utc_now", lambda: FROZEN)


def test_utc_today_is_utc_date() -> None:
    assert clock.utc_today() == date(2026, 3, 10)


def test_user_today_ahead_of_utc() -> None:
    assert clock.user_today("Pacific/Kiritimati") == date(2026, 3, 11)


def test_user_today_behind_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    early = FROZEN.replace(hour=2)
    monkeypatch.setattr(clock, "utc_now", lambda: early)
    assert clock.user_today("America/Los_Angeles") == date(2026, 3, 9)


@pytest.mark.parametrize("tz", [None, "", "Not/AZone", "../etc/passwd"])
def test_user_today_falls_back_to_utc(tz: str | None) -> None:
    assert clock.user_today(tz) == date(2026, 3, 10)


def test_user_now_is_aware_in_zone() -> None:
    now = clock.user_now("Pacific/Kiritimati")
    assert now.utcoffset() == timedelta(hours=14)
    assert now == FROZEN


def test_valid_timezone() -> None:
    assert clock.valid_timezone("Europe/Paris")
    assert clock.valid_timezone("UTC")
    assert not clock.valid_timezone("Mars/Base")
    assert not clock.valid_timezone("")
    assert not clock.valid_timezone("../x")
