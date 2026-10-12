"""SEC-10: the credential surface is throttled per address and per account.

Two independent brakes stand in front of a password guess:

* the per-address limiter (``app/core/rate_limit.py``) on every ``/api/auth/*``
  route, which **fails closed** (503) when its store is down;
* the per-account login throttle (``app/core/login_throttle.py``), which counts
  failures per email and delays the next answer, and **fails open** by design.

M33-S1-SAFETY-050 pins two things that silently weakened them:

1. The limiter counted with a *fixed* window, which forgets every hit when the
   window closes, so a caller could spend the budget at the end of one window and
   again just after it: twice the limit in a fraction of a second. A moving
   window must hold "N per minute" at every instant.
2. The unit-suite ``FakeRedis`` lacked ``incr``, so ``record_failure`` raised,
   logged ``login_throttle_unavailable`` and returned 0 in every unit test: the
   throttle was off in the whole unit tier and nothing noticed.

Clock control: the limiter's ``memory://`` store reads ``time.time()`` from
``limits.storage.memory``; the tests replace it, so time moves only when a test
says so and runner latency cannot move a request across a window.
"""

import ast
import inspect
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from limits import parse
from limits.strategies import MovingWindowRateLimiter

from app.core import login_throttle
from app.core.exceptions import AuthenticationError
from app.core.rate_limit import RATE_LIMIT_STRATEGY, build_limiter, limiter
from tests.unit.conftest import FakeRedis

APP = Path(__file__).resolve().parents[2] / "app"
LOGIN = {"email": "brute@example.com", "password": "wrong"}

#: The SEC-10 ceilings for the credential routes, as shipped at M32. A route may
#: get stricter; it may not get looser, and it may not lose its limit.
AUTH_LIMIT_CEILINGS = {
    "register": "3/minute",
    "login": "5/minute",
    "forgot_password": "3/minute",
    "reset_password": "3/minute",
    "resend_verification": "3/minute",
    "oauth_mfa_complete": "5/minute",
    "demo_login": "10/minute",
    "delete_account": "3/minute",
}


class _Clock:
    def __init__(self, now: float = 2_000_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch):
    clk = _Clock()
    monkeypatch.setattr("limits.storage.memory.time", SimpleNamespace(time=clk))
    return clk


def _swap_store(monkeypatch, storage_uri: str, timeout: float | None = None) -> None:
    """Point the app's limiter at a fresh store built by the production factory."""
    fresh = build_limiter(storage_uri, timeout)
    monkeypatch.setattr(limiter, "_storage", fresh._storage)
    monkeypatch.setattr(limiter, "_limiter", fresh._limiter)


@pytest.fixture
def fake_throttle_store(monkeypatch):
    """Back the login throttle with the unit suite's own Redis fake."""
    import app.core.redis as core_redis

    FakeRedis.reset()
    monkeypatch.setattr(core_redis, "redis_client", FakeRedis())
    with patch("app.core.login_throttle.asyncio.sleep", new_callable=AsyncMock) as sleep:
        yield sleep


# --- 1. moving window -----------------------------------------------------------


def test_sec10_every_limiter_counts_with_a_moving_window():
    """The module limiter and both store kinds the factory builds use one strategy."""
    assert RATE_LIMIT_STRATEGY == "moving-window"
    assert isinstance(limiter._limiter, MovingWindowRateLimiter)
    for uri in ("memory://", "redis://127.0.0.1:1/0"):
        assert isinstance(build_limiter(uri, 0.05)._limiter, MovingWindowRateLimiter), uri


def test_sec10_no_limiter_is_built_outside_the_factory():
    """A second ``Limiter(...)`` could pick its own strategy and outage policy."""
    offenders = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in {"Limiter", "_OutagePolicyLimiter"}:
                offenders.append(f"{path.relative_to(APP)}:{node.lineno} {name}(...)")
    assert offenders == [
        "core/rate_limit.py:" + _factory_call_line() + " _OutagePolicyLimiter(...)"
    ]


def _factory_call_line() -> str:
    source, start = inspect.getsourcelines(build_limiter)
    for offset, line in enumerate(source):
        if "_OutagePolicyLimiter(" in line:
            return str(start + offset)
    raise AssertionError("build_limiter no longer constructs _OutagePolicyLimiter")


async def test_sec10_window_boundary_does_not_refill_the_login_budget(
    async_client, clock, monkeypatch, fake_throttle_store
):
    """Five attempts at the end of a window, then a burst just after it closes.

    A fixed window opens at t0 and forgets everything at t0+60, so the burst at
    t0+60.1 gets a fresh five: ten guesses inside 0.2 s. A moving window still
    sees the four at t0+59.9, so only one more is allowed and the rest are 429.
    """
    _swap_store(monkeypatch, "memory://")
    statuses: list[tuple[float, int]] = []
    t0 = clock.now

    async def attempt() -> None:
        response = await async_client.post("/api/auth/login", json=LOGIN)
        statuses.append((clock.now - t0, response.status_code))

    with patch(
        "app.api.auth.user_service.authenticate_user",
        new_callable=AsyncMock,
        side_effect=AuthenticationError("Invalid credentials"),
    ):
        await attempt()  # t0: opens the (fixed) window
        clock.now = t0 + 59.9
        for _ in range(4):
            await attempt()  # the budget is spent at the window's end
        clock.now = t0 + 60.1  # just past the fixed window's reset
        for _ in range(5):
            await attempt()

    codes = [code for _, code in statuses]
    assert codes[:5] == [401] * 5, statuses
    assert codes[5:] == [401, 429, 429, 429, 429], statuses

    # The invariant itself: no 60 s span ever lets more than five through.
    allowed = [t for t, code in statuses if code != 429]
    for start in allowed:
        assert sum(1 for t in allowed if start <= t < start + 60) <= 5, statuses

    # Budget returns once every recorded hit has aged out.
    clock.now = t0 + 60.1 + 60.0
    with patch(
        "app.api.auth.user_service.authenticate_user",
        new_callable=AsyncMock,
        side_effect=AuthenticationError("Invalid credentials"),
    ):
        assert (await async_client.post("/api/auth/login", json=LOGIN)).status_code == 401


# --- 2. outage policy and ceilings ----------------------------------------------


async def test_sec10_auth_limiter_store_down_fails_closed(async_client, monkeypatch):
    """With the limiter's Redis unreachable, login is refused before it runs."""
    _swap_store(monkeypatch, "redis://127.0.0.1:1/0", timeout=0.05)
    with patch(
        "app.api.auth.user_service.authenticate_user", new_callable=AsyncMock
    ) as authenticate:
        response = await async_client.post("/api/auth/login", json=LOGIN)
    assert response.status_code == 503
    authenticate.assert_not_awaited()


def _limit_strings(func: ast.AsyncFunctionDef | ast.FunctionDef) -> list[str]:
    out = []
    for dec in func.decorator_list:
        if not (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and dec.func.attr == "limit"
            and getattr(dec.func.value, "id", None) == "limiter"
        ):
            continue
        arg = dec.args[0] if dec.args else None
        if isinstance(arg, ast.Lambda):
            arg = arg.body
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            raise AssertionError(
                f"{func.name}: limit is not a literal, cannot judge it: {ast.unparse(dec)}"
            )
        out.append(arg.value)
    return out


def _per_second(limit: str) -> float:
    item = parse(limit)
    return item.amount / item.get_expiry()


def test_sec10_no_auth_limit_is_loosened_or_dropped():
    tree = ast.parse((APP / "api" / "auth.py").read_text())
    found = {
        node.name: _limit_strings(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    problems = []
    for name, ceiling in AUTH_LIMIT_CEILINGS.items():
        limits_ = found.get(name)
        if not limits_:
            problems.append(f"{name}: no @limiter.limit (ceiling {ceiling})")
        elif min(_per_second(x) for x in limits_) > _per_second(ceiling):
            problems.append(f"{name}: {limits_} looser than {ceiling}")
    assert problems == []


def test_sec10_ceiling_check_reads_lambda_and_literal_limits():
    """Control for the ceiling reader: both decorator forms, and a non-literal."""
    src = textwrap.dedent(
        """
        @limiter.limit(lambda: "5/minute")
        async def a(): ...
        @limiter.limit("2/second")
        async def b(): ...
        @limiter.limit(lambda: settings.x)
        async def c(): ...
        """
    )
    funcs = {f.name: f for f in ast.parse(src).body}
    assert _limit_strings(funcs["a"]) == ["5/minute"]
    assert _per_second(_limit_strings(funcs["b"])[0]) > _per_second("5/minute")
    with pytest.raises(AssertionError, match="not a literal"):
        _limit_strings(funcs["c"])


# --- 3. the per-account throttle really runs under the unit-suite fake ----------


def _redis_calls_in_login_throttle() -> set[str]:
    tree = ast.parse(inspect.getsource(login_throttle))
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and getattr(node.func.value, "id", None) == "redis_client"
    }


def test_sec10_unit_fake_implements_every_call_the_throttle_makes():
    """A new Redis call in the throttle must land in the fake, or the unit tier
    exercises login with the throttle silently off again."""
    calls = _redis_calls_in_login_throttle()
    assert {"get", "incr", "expire", "delete"} <= calls
    missing = sorted(c for c in calls if not callable(getattr(FakeRedis, c, None)))
    assert missing == []


async def test_sec10_login_throttle_counts_and_engages_under_the_unit_fake(fake_throttle_store):
    sleep = fake_throttle_store
    free = login_throttle.settings.login_throttle_free_attempts
    with patch.object(login_throttle.logger, "warning") as warn:
        counts = [await login_throttle.record_failure(LOGIN["email"]) for _ in range(free + 1)]
        slept = await login_throttle.apply_delay(LOGIN["email"].upper())  # same account
    assert counts == list(range(1, free + 2))
    events = [c.args[0] for c in warn.call_args_list if c.args]
    assert "login_throttle_unavailable" not in events
    assert "login_throttle_engaged" in events
    assert slept == login_throttle.settings.login_throttle_base_delay > 0
    sleep.assert_awaited_once_with(slept)


async def test_sec10_failed_logins_over_http_engage_the_throttle(
    async_client, clock, monkeypatch, fake_throttle_store
):
    """End to end: failed logins are recorded, and past the free allowance the
    next answer is delayed, under the same fake the unit tier uses."""
    sleep = fake_throttle_store
    _swap_store(monkeypatch, "memory://")
    free = login_throttle.settings.login_throttle_free_attempts
    with (
        patch(
            "app.api.auth.user_service.authenticate_user",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("Invalid credentials"),
        ),
        patch.object(login_throttle.logger, "warning") as warn,
    ):
        for _ in range(free + 1):
            clock.now += 61.0  # stay under the per-address limit; only the account counts
            assert (await async_client.post("/api/auth/login", json=LOGIN)).status_code == 401
        clock.now += 61.0
        assert (await async_client.post("/api/auth/login", json=LOGIN)).status_code == 401
    assert "login_throttle_unavailable" not in [c.args[0] for c in warn.call_args_list if c.args]
    sleep.assert_awaited()
    assert sleep.await_args.args[0] > 0
