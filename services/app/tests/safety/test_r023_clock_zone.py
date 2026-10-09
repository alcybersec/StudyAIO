"""R-023 / ADR 0006 — the per-user time zone against the floors.

The zone (``user_settings.timezone``) is user-supplied and unverified. Four
questions, one block each:

* **Quota and usage (ADR 0006 Decision 6; abuse of the instance's AI
  credentials, next to floor 2).** The daily AI quota and the usage records
  billing reads live on the UTC day. If any of it moved with the zone, a user
  could exhaust today's allowance, hop from ``Etc/GMT+12`` to
  ``Pacific/Kiritimati`` and be in "tomorrow" with a fresh one. Pinned
  structurally (no quota/usage module reads a zone) and behaviourally (with the
  clock frozen where the two zones straddle midnight, every ``record_date`` the
  code reads or writes is the UTC date).
* **Zone input (Decision 4).** Validation is membership in the shipped key set,
  never raises, and refuses path-like and host-specific keys; a bad stored
  value degrades to UTC and never raises in a request or a beat task.
* **Floor 1.** The zone lookup is scoped to the authenticated caller, takes no
  request-supplied identity, and the zone is carried by no response model but
  the caller's own settings.
* **Floor 4.** Covered by ``test_floor4_user_data_never_lost.py``; the R-023
  diff adds no delete or overwrite of user data (SAFETY-037 review).
"""

from __future__ import annotations

import ast
import importlib.resources
import inspect
import pkgutil
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfoNotFoundError, available_timezones

import pytest
from pydantic import BaseModel
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import BinaryExpression, BindParameter

from tests.safety._source import APP_ROOT, app_modules, parse, rel
from tests.safety._tenant import filters_on_user, tables_in

# 23:30 UTC on 2026-10-09: already 2026-10-10 in Kiritimati (UTC+14), still
# 2026-10-09 in Etc/GMT+12 (UTC-12). Any user-local day here differs from UTC
# for the far-east zone, so a quota on the local day would be visible.
FROZEN_LATE = datetime(2026, 10, 9, 23, 30, tzinfo=UTC)
# 00:30 UTC on 2026-10-10: still 2026-10-09 at UTC-12.
FROZEN_EARLY = datetime(2026, 10, 10, 0, 30, tzinfo=UTC)

HOP_ZONES = ("Pacific/Kiritimati", "Etc/GMT+12")

#: Names through which code reaches a user's zone or user-local day.
USER_ZONE_NAMES = frozenset(
    {"user_today", "user_now", "local_day_end_utc", "get_user_timezone", "get_user_tz"}
)

#: Hostile zone input. Each must be refused on write and degrade to UTC on read.
HOSTILE_KEYS: tuple[object, ...] = (
    "localtime",  # host-specific: a symlink to /etc/localtime on Debian hosts
    "/etc/localtime",
    "../etc/passwd",
    "Europe/../../../etc/passwd",
    "/dev/zero",
    "posixrules",
    "UTC\x00",
    "",
    " UTC",
    "Mars/Base",
    "x" * 1_000_000,
    "Ευρώπη/Αθήνα",
    "\ud800",  # lone surrogate: not encodable, must not reach a path
    None,
    123,
    b"UTC",
    ["UTC"],
)


def _frozen(instant: datetime):
    """Freeze the one clock (ADR 0006: tests freeze ``app.core.clock``)."""
    return patch("app.core.clock.utc_now", return_value=instant)


def _shipped_zone_keys() -> frozenset[str]:
    """The zone keys of the declared ``tzdata`` dependency, independent of the host."""
    text = importlib.resources.files("tzdata").joinpath("zones").read_text()
    return frozenset(line.strip() for line in text.splitlines() if line.strip())


def _record_dates(statement) -> list[date]:
    """Every value a statement compares ``record_date`` with."""
    out = []
    for element in visitors.iterate(statement):
        if not isinstance(element, BinaryExpression):
            continue
        for column, other in ((element.left, element.right), (element.right, element.left)):
            if getattr(column, "name", None) == "record_date" and isinstance(other, BindParameter):
                out.append(other.effective_value)
    return out


def _recording_session(result=None):
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    executed = []

    async def _execute(statement, *args, **kwargs):
        executed.append(statement)
        res = MagicMock()
        res.scalar_one_or_none.return_value = result
        res.one.return_value = (0, 0)
        res.scalar_one.return_value = 0
        return res

    session.execute = AsyncMock(side_effect=_execute)
    return session, executed


# ── 1. Quota, billing and usage are on the UTC day ─────────────────────


def _usage_modules() -> list:
    """Every app module that touches usage records or the quota, models excluded."""
    out = []
    for path in app_modules(exclude=("app/models/",)):
        r = rel(path)
        text = path.read_text()
        if "UsageRecord" in text or r in {"app/services/quota_service.py", "app/core/quota.py"}:
            out.append(path)
    return out


def test_r023_quota_and_usage_modules_never_read_the_user_zone():
    """No module that reads or writes usage records, or decides quota, reaches a zone."""
    modules = _usage_modules()
    names = {rel(p) for p in modules}
    # Not vacuous: the three domains Decision 6 names are all in scope.
    assert {
        "app/services/quota_service.py",
        "app/services/billing_service.py",
        "app/services/admin_service.py",
    } <= names, names

    offenders = []
    for path in modules:
        for node in ast.walk(parse(path)):
            hit = None
            if isinstance(node, ast.Name) and node.id in USER_ZONE_NAMES:
                hit = node.id
            elif isinstance(node, ast.Attribute) and (
                node.attr in USER_ZONE_NAMES or node.attr == "timezone"
            ):
                hit = node.attr
            elif isinstance(node, ast.alias) and node.name.split(".")[-1] in USER_ZONE_NAMES:
                hit = node.name
            elif isinstance(node, ast.arg) and node.arg in {"tz", "timezone"}:
                hit = f"parameter {node.arg}"
            if hit:
                offenders.append(f"{rel(path)}:{getattr(node, 'lineno', '?')} {hit}")
    assert not offenders, (
        "ADR 0006 Decision 6: quota, billing and usage are UTC; a user zone here lets "
        f"a user move their quota day by changing a setting: {offenders}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("instant", "utc_date"),
    [(FROZEN_LATE, date(2026, 10, 9)), (FROZEN_EARLY, date(2026, 10, 10))],
)
async def test_r023_usage_day_is_utc_whatever_the_zone(instant, utc_date):
    """Quota reads and usage writes key on the UTC date while the zones disagree."""
    from app.core.clock import user_today
    from app.services import billing_service, quota_service

    with _frozen(instant):
        # The freeze is one where a zone hop crosses a day boundary.
        local_days = {user_today(z) for z in HOP_ZONES}
        assert len(local_days) == 2 and utc_date in local_days | {utc_date}

        session, executed = _recording_session()
        await quota_service.get_usage_today(session, "caller")
        await quota_service.get_global_usage_today(session)
        await billing_service.record_usage(session, "caller", ai_calls=1)

    compared = [d for stmt in executed for d in _record_dates(stmt)]
    assert len(compared) >= 3, "the quota and usage reads stopped filtering on record_date"
    assert set(compared) == {utc_date}, compared
    added = [c.args[0] for c in session.add.call_args_list]
    assert [r.record_date for r in added] == [utc_date]


@pytest.mark.asyncio
async def test_r023_zone_change_touches_no_usage_record():
    """Setting the zone writes the settings row and nothing else."""
    from app.services import settings_service

    row = MagicMock(settings_json={}, timezone="Etc/GMT+12")
    session, executed = _recording_session()
    with patch.object(
        settings_service, "_get_or_create_user_settings", AsyncMock(return_value=row)
    ):
        await settings_service.update_user_settings(
            session, "caller", {"timezone": "Pacific/Kiritimati"}
        )
    assert row.timezone == "Pacific/Kiritimati"
    touched = set().union(*(tables_in(s) for s in executed)) if executed else set()
    assert "usage_records" not in touched
    assert not session.add.called


# ── 2. Zone input ──────────────────────────────────────────────────────


@pytest.mark.parametrize("key", HOSTILE_KEYS, ids=lambda k: repr(k)[:24])
def test_r023_valid_timezone_refuses_hostile_keys_without_raising(key):
    """Decision 4: membership, not "ZoneInfo did not raise"; never raises.

    RED on ``localtime``: ``zoneinfo.available_timezones()`` walks the host's
    TZPATH, and Debian ships ``/usr/share/zoneinfo/localtime -> /etc/localtime``,
    so the host-specific key the ADR names as refused is accepted.
    """
    from app.core.clock import valid_timezone

    result = valid_timezone(key)  # type: ignore[arg-type]
    assert result is False


def test_r023_accepted_zone_keys_come_from_the_declared_tzdata_only():
    """The accepted key set does not depend on what the host or base image ships.

    RED while ``valid_timezone`` trusts ``available_timezones()``, which unions
    in every TZif file under the host's ``/usr/share/zoneinfo``.
    """
    from app.core.clock import valid_timezone

    shipped = _shipped_zone_keys()
    assert "Europe/Berlin" in shipped and valid_timezone("Europe/Berlin")
    host_only = sorted(k for k in available_timezones() - shipped if valid_timezone(k))
    assert not host_only, f"host-specific zone keys accepted: {host_only}"


def test_r023_every_valid_key_fits_the_column():
    """No accepted key is truncated or rejected by ``String(64)`` on write."""
    from app.models.user_settings import UserSettings

    limit = UserSettings.__table__.c.timezone.type.length
    assert max(len(k) for k in _shipped_zone_keys()) <= limit


@pytest.mark.parametrize(
    "key", [k for k in HOSTILE_KEYS if k is None or isinstance(k, str)], ids=lambda k: repr(k)[:24]
)
def test_r023_bad_stored_zone_degrades_to_utc(key):
    """A bad stored value (pre-validation row, dropped key) is UTC on every read path."""
    from app.core.clock import user_now, user_today
    from app.core.localday import local_day_end_utc

    with _frozen(FROZEN_LATE):
        assert user_today(key) == date(2026, 10, 9)
        assert user_now(key).utcoffset().total_seconds() == 0
        assert local_day_end_utc(key) == datetime(2026, 10, 10, tzinfo=UTC)


@pytest.mark.parametrize(
    "error", [ZoneInfoNotFoundError("gone"), ValueError("bad TZif"), OSError("io")]
)
def test_r023_listed_but_unloadable_zone_degrades_to_utc(error):
    """Decision 4: a bad zone "never raises in a request or a beat task".

    A key can pass the membership check and still fail to load: the host
    ``localtime`` symlink dangling, or a TZif file under TZPATH (searched before
    ``tzdata``) truncated or unreadable. RED while ``clock._zone`` calls
    ``ZoneInfo`` unguarded.
    """
    from app.core import clock

    with _frozen(FROZEN_LATE), patch.object(clock, "ZoneInfo", side_effect=error):
        assert clock.user_today("Pacific/Kiritimati") == date(2026, 10, 9)
        assert clock.user_now("Pacific/Kiritimati").utcoffset().total_seconds() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key",
    [
        "localtime",
        "/etc/localtime",
        "../etc/passwd",
        "UTC\x00",
        "x" * 100_000,
        "Ευρώπη/Αθήνα",
        123,
        ["UTC"],
        "",
    ],
    ids=lambda k: repr(k)[:24],
)
async def test_r023_put_hostile_zone_is_422_and_stores_nothing(async_client, key):
    """``PUT /api/settings`` refuses hostile zones with 422 (never 500) and keeps the row."""
    row = MagicMock(settings_json={}, timezone="Europe/Berlin")
    with patch(
        "app.services.settings_service._get_or_create_user_settings",
        new_callable=AsyncMock,
        return_value=row,
    ):
        response = await async_client.put("/api/settings", json={"timezone": key})
    assert response.status_code == 422, response.status_code
    assert row.timezone == "Europe/Berlin"


# ── 3. Floor 1: the zone is the caller's own ───────────────────────────


@pytest.mark.asyncio
async def test_r023_zone_lookup_filters_on_the_caller():
    """``get_user_timezone`` reads exactly the caller's settings row."""
    from app.services import settings_service

    session, executed = _recording_session(SimpleNamespace(timezone="Asia/Tokyo"))
    assert await settings_service.get_user_timezone(session, "caller") == "Asia/Tokyo"
    assert executed, "no lookup ran"
    for statement in executed:
        assert "user_settings" in tables_in(statement)
        assert filters_on_user(statement, "caller"), str(statement)


def test_r023_get_user_tz_takes_identity_only_from_authentication():
    """The dependency has no request-supplied parameter that could name another user."""
    from fastapi.params import Depends as DependsParam

    from app.api import deps

    params = inspect.signature(deps.get_user_tz).parameters
    assert set(params) == {"user", "session"}
    for p in params.values():
        assert isinstance(p.default, DependsParam), p
    assert params["user"].default.dependency is deps.get_current_user_or_default

    # And it hands the lookup that user's id, not anything else in scope.
    fn = next(
        n
        for n in ast.walk(parse(APP_ROOT / "api" / "deps.py"))
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_user_tz"
    )
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    lookup = [c for c in calls if getattr(c.func, "attr", None) == "get_user_timezone"]
    assert len(lookup) == 1
    assert ast.unparse(lookup[0].args[1]) == "user.id"


@pytest.mark.asyncio
async def test_r023_zone_route_ignores_a_smuggled_user(async_client, default_test_user):
    """A zone-dependent route given another user's id in the query still uses the caller's."""
    with (
        patch(
            "app.api.deps.settings_service.get_user_timezone",
            new_callable=AsyncMock,
            return_value="Asia/Tokyo",
        ) as lookup,
        patch(
            "app.api.study.streak_service.get_streak",
            new_callable=AsyncMock,
            return_value={"current_streak": 0, "longest_streak": 0, "last_study_date": None},
        ) as streak,
    ):
        response = await async_client.get(
            "/api/study/streak",
            params={"user_id": "victim", "tz": "Pacific/Kiritimati", "timezone": "Etc/GMT+12"},
        )
    assert response.status_code == 200
    assert lookup.await_args.args[1] == default_test_user.id
    assert streak.await_args.kwargs["user_id"] == default_test_user.id
    assert streak.await_args.kwargs["tz"] == "Asia/Tokyo"


#: The only schemas allowed to carry a zone: the caller's own settings.
ZONE_CARRYING_SCHEMAS = frozenset({"SettingsResponse", "SettingsUpdateRequest"})


def test_r023_zone_is_carried_only_by_the_callers_own_settings():
    """No response model (leaderboard, admin, export, ...) carries another user's zone."""
    import app.api as api_pkg

    carriers = set()
    for info in pkgutil.walk_packages(api_pkg.__path__, prefix="app.api."):
        module = __import__(info.name, fromlist=["_"])
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseModel)
                and obj.__module__ == module.__name__
                and ({"timezone", "tz"} & set(obj.model_fields))
            ):
                carriers.add(obj.__name__)
    assert carriers == ZONE_CARRYING_SCHEMAS, carriers


#: Files that may read the ``timezone`` attribute of a settings row.
ZONE_ATTRIBUTE_READERS = frozenset(
    {"app/services/settings_service.py", "app/models/user_settings.py"}
)


def test_r023_zone_column_read_only_through_the_scoped_lookup():
    """``<settings>.timezone`` is read only in ``settings_service``.

    Everything else gets the zone from ``get_user_timezone`` (scoped above), so
    a cross-user read (``UserSettings.timezone`` joined into a leaderboard or
    an admin listing) fails here first.
    """
    offenders = []
    for path in app_modules():
        if rel(path) in ZONE_ATTRIBUTE_READERS:
            continue
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Attribute) and node.attr == "timezone":
                offenders.append(f"{rel(path)}:{node.lineno} {ast.unparse(node)}")
    assert not offenders, offenders
