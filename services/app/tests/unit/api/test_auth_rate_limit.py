"""Tests for auth endpoint rate limiting."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from limits.strategies import MovingWindowRateLimiter

from app.core.exceptions import AuthenticationError
from app.core.rate_limit import build_limiter, limiter


@pytest.fixture(autouse=True)
def isolated_limiter(monkeypatch):
    """Give each test a private, empty limiter store.

    The module-level limiter is process-wide, so its counters (and the
    background expiry timer of the in-memory store) are shared by every test
    that runs in the same xdist worker. These tests count requests to an exact
    threshold, so they must not share that state: swap in a fresh store for the
    test and restore the original afterwards. Production limits are untouched.
    """
    fresh = build_limiter("memory://")
    monkeypatch.setattr(limiter, "_storage", fresh._storage)
    monkeypatch.setattr(limiter, "_limiter", fresh._limiter)
    yield


class Clock:
    """A controllable wall clock for the limiter's in-memory store."""

    def __init__(self, now: float = 1_000_000_020.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    """Freeze the limiter's clock so latency can never move a request across a window.

    Requests on a loaded CI runner took 2-6 s each; six of them straddled a
    minute boundary and a fixed window reset between the 5th and 6th. Counting
    tests must not depend on how fast the runner is, so time only advances when
    a test says so.
    """
    clk = Clock()
    monkeypatch.setattr("limits.storage.memory.time", SimpleNamespace(time=clk))
    return clk


@pytest.fixture
async def async_client(async_client, request):
    """The shared client, re-bound to a peer address unique to this test.

    The limiter keys on the peer address; a per-test address means no other
    request can ever land in this test's bucket.
    """
    from app.main import app

    ip = f"10.{abs(hash(request.node.nodeid)) % 250}.{id(request) % 250}.7"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=(ip, 5000)),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.asyncio
class TestAuthRateLimit:
    """Verify rate limits on auth endpoints prevent brute-force attacks."""

    async def test_login_rate_limited_after_5_attempts(self, async_client):
        """POST /api/auth/login returns 429 after 5 rapid attempts."""
        with patch(
            "app.api.auth.user_service.authenticate_user",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("Invalid credentials"),
        ):
            for i in range(5):
                response = await async_client.post(
                    "/api/auth/login",
                    json={"email": "test@example.com", "password": "wrong"},
                )
                assert response.status_code == 401, f"Request {i + 1} should be 401"

            # 6th attempt should be rate limited
            response = await async_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrong"},
            )
            assert response.status_code == 429

    async def test_register_rate_limited_after_3_attempts(self, async_client):
        """POST /api/auth/register returns 429 after 3 rapid attempts."""
        with patch(
            "app.api.auth.user_service.register_user",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("Registration failed"),
        ):
            for i in range(3):
                response = await async_client.post(
                    "/api/auth/register",
                    json={
                        "email": f"user{i}@example.com",
                        "username": f"user{i}",
                        "password": "TestPass1!",
                    },
                )
                # We don't care about exact status here, just that it's not 429 yet
                assert response.status_code != 429, f"Request {i + 1} should not be 429 yet"

            # 4th attempt should be rate limited
            response = await async_client.post(
                "/api/auth/register",
                json={
                    "email": "user99@example.com",
                    "username": "user99",
                    "password": "TestPass1!",
                },
            )
            assert response.status_code == 429

    async def test_forgot_password_rate_limited_after_3_attempts(self, async_client):
        """POST /api/auth/forgot-password returns 429 after 3 rapid attempts."""
        with patch(
            "app.api.auth.user_service.request_password_reset",
            new_callable=AsyncMock,
        ):
            for _i in range(3):
                response = await async_client.post(
                    "/api/auth/forgot-password",
                    json={"email": "test@example.com"},
                )
                assert response.status_code == 202

            # 4th attempt should be rate limited
            response = await async_client.post(
                "/api/auth/forgot-password",
                json={"email": "test@example.com"},
            )
            assert response.status_code == 429


LOGIN = {"email": "test@example.com", "password": "wrong"}


class TestMovingWindowStrategy:
    def test_limiter_uses_the_moving_window_strategy(self):
        assert isinstance(limiter._limiter, MovingWindowRateLimiter)


@pytest.mark.asyncio
class TestMovingWindow:
    """A fixed window lets an attacker spend 2x the budget around a boundary."""

    async def test_a_window_boundary_does_not_reset_the_count(self, async_client, clock):
        """One hit opens a window; four more land at its very end; the window
        then "expires". A fixed window forgets all five and grants five more
        (10 in ~1 s). A moving window still sees the four recent hits."""
        post = lambda: async_client.post("/api/auth/login", json=LOGIN)  # noqa: E731
        with patch(
            "app.api.auth.user_service.authenticate_user",
            new_callable=AsyncMock,
            side_effect=AuthenticationError("Invalid credentials"),
        ):
            assert (await post()).status_code == 401  # t0: opens the window
            clock.now += 59.9
            for _ in range(4):
                assert (await post()).status_code == 401  # 5 hits inside 60 s
            clock.now += 0.2  # t0 + 60.1: the first hit has aged out, four remain
            assert (await post()).status_code == 401  # the 5th in the window
            assert (await post()).status_code == 429  # the 6th: a fixed window says 401

            clock.now += 60.0  # every recorded hit has aged out: budget returns
            assert (await post()).status_code == 401
