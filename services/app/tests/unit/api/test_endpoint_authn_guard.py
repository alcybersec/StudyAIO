"""Structural guard on the authentication boundary, route by route.

The authz counterpart of this file (`test_endpoint_scoping_guard.py`, #54) was
written because hand sweeps miss things: run against the tree as it stood before
#53 it flagged every cluster found by hand *and* eleven more in `courseops` that
three rounds of manual review walked past. This is the same idea applied one
layer out — not "does this endpoint check *whose* object it is", but "does this
endpoint ask who is calling at all".

## What it does

Enumerates every route on the real app and, for each one not on the public
allowlist, sends a real unauthenticated request in SaaS mode (`self_hosted=False`)
and asserts a 401. No dependency override for `get_current_user_or_default` —
that override is what makes the rest of the API suite blind to this.

Nothing downstream of the auth dependency is exercised, and deliberately so: a
401 is raised while sub-dependencies are being solved, before body validation and
before the handler. So the walk needs no fixtures, no request bodies, and no
plausible ids — a 401 is the *only* correct answer to an anonymous request at a
protected endpoint, whatever else is wrong with it. Any other status is the
finding.

## Adding an entry

A route that turns up unprotected means one of two things. Add the auth
dependency, or — if it is genuinely meant to be reachable by anonymous callers —
add it to `PUBLIC_BY_DESIGN` **with a reason**. A webhook that authenticates by
signature counts; "the frontend only calls it when logged in" does not.

Both directions are asserted, so an entry left behind after an endpoint gains
auth fails too. Otherwise the allowlist silently becomes a list of routes nobody
checks any more.

## Why the public set is checked structurally as well

The behavioural walk skips public routes (requesting them would run their
handlers, which is a different test's job), so on its own it could not notice a
stale entry. `_unauthenticated_routes()` reads the dependency tree instead, and
the two views are asserted to agree.
"""

import asyncio
import contextlib
import re
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.routing import APIRoute

from app.api.deps import get_current_user, get_current_user_or_default
from app.config import settings
from app.core.database import get_session
from app.main import app

# The dependencies that establish an identity. `require_role` / `require_plan`
# are not listed because both take `get_current_user` as a sub-dependency, so
# the recursive walk finds it through them.
IDENTITY_DEPENDENCIES = frozenset({get_current_user, get_current_user_or_default})

# Substituted for every path parameter. It never has to resolve to anything: the
# auth dependency raises before the path parameter is even parsed.
DUMMY_PATH_VALUE = "00000000-0000-0000-0000-0000000000ff"

# Bounds on the walk when it is *failing*. A protected route answers in about a
# millisecond because nothing past the auth dependency runs; a route that lets
# the caller through runs its real handler against a stub session, and some of
# those block for a long time (the retrieval endpoints load an embedding model).
# Without these, a broken auth boundary turns this test from a clear failure into
# a hung suite -- the one outcome nobody debugs.
REQUEST_TIMEOUT_S = 5.0
MAX_FINDINGS = 10

# ---------------------------------------------------------------------------
# Allowlist. Key is "<METHOD> <path>". Every entry needs a reason.
# ---------------------------------------------------------------------------

PUBLIC_BY_DESIGN: dict[str, str] = {
    # Probes. Must answer before anyone can log in, by definition.
    "GET /health": "liveness/readiness probe, no data",
    "GET /health/live": "liveness probe, no data",
    "GET /health/ready": "readiness probe, reports DB/Redis up/down only",
    # The login funnel: every one of these is how a caller *becomes*
    # authenticated, so requiring authentication would be circular.
    "GET /api/auth/config": "tells the login page what to render (which providers, invite required)",
    "POST /api/auth/login": "the login endpoint itself; throttled per account and per address",
    "POST /api/auth/register": "account creation; gated by REGISTRATION_MODE and rate-limited",
    "POST /api/auth/logout": "clears cookies; refusing an unauthenticated logout helps nobody",
    "POST /api/auth/refresh": "authenticates by refresh cookie, not access cookie",
    "POST /api/auth/forgot-password": "pre-login recovery; answers identically for unknown addresses",
    "POST /api/auth/reset-password": "authenticates by the emailed single-use reset token",
    "POST /api/auth/verify-email": "authenticates by the emailed single-use verification token",
    "GET /api/auth/oauth/{provider}": "starts the OAuth redirect; there is no session yet",
    "GET /api/auth/oauth/{provider}/callback": "OAuth callback, verified by the provider state token",
    "GET /api/auth/demo-login": "mints the shared demo session; inert unless DEMO_ENABLED",
    # Webhooks. Third parties cannot present a user cookie, so each carries its
    # own authentication — the check to keep an eye on is that one, not this.
    "POST /api/billing/webhook": "Stripe webhook, verified by stripe-signature HMAC",
    "POST /api/calendar/webhook": "Google Calendar push, verified by the channel id it issued",
    "POST /api/notifications/telegram/webhook": (
        "Telegram update, verified by the x-telegram-bot-api-secret-token header"
    ),
    # Public by content.
    "GET /api/notifications/push/vapid-key": "returns the VAPID *public* key, which is published",
}

# Real, currently-unprotected routes that a PR is deliberately not fixing —
# pinned so they cannot be lost, and so the guard stays green while the fix is
# tracked as its own issue rather than buried in a test-coverage diff.
#
# The one entry #65 parked here, `GET /api/files/{file_type}/{path:path}`, was
# fixed in #66: the route now takes `get_current_user_or_default` and resolves
# the owner from the path prefix. So the dict is empty, and should stay that
# way — an entry is a debt, not a resting place.
KNOWN_UNAUTHENTICATED_PENDING_FIX: dict[str, str] = {}

PUBLIC = frozenset(PUBLIC_BY_DESIGN) | frozenset(KNOWN_UNAUTHENTICATED_PENDING_FIX)


def _route_key(route: APIRoute, method: str) -> str:
    return f"{method} {route.path}"


def _api_routes() -> list[tuple[APIRoute, str]]:
    """Every (route, method) pair the app serves.

    HEAD and OPTIONS are dropped: Starlette adds them itself, and OPTIONS is
    answered by the CORS middleware before routing.
    """
    pairs = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            pairs.append((route, method))
    return pairs


def _dependency_calls(route: APIRoute) -> set:
    """Every callable in the route's dependency tree, transitively."""
    calls = set()
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if dep.call is not None:
            calls.add(dep.call)
        stack.extend(dep.dependencies)
    return calls


def _allowed_roles(route: APIRoute) -> frozenset[str] | None:
    """The roles a `require_role(...)` on this route permits, or None if it has none.

    `require_role` returns a closure, so the permitted roles are read out of its
    cell rather than hard-coded here — a future `require_role("admin", "user")`
    is then honoured instead of silently expected to 403.
    """
    roles: set[str] = set()
    found = False
    for call in _dependency_calls(route):
        if getattr(call, "__qualname__", "") != "require_role.<locals>._check_role":
            continue
        found = True
        cells = dict(
            zip(call.__code__.co_freevars, (c.cell_contents for c in call.__closure__), strict=True)
        )
        roles |= set(cells["allowed_roles"])
    return frozenset(roles) if found else None


def _unauthenticated_routes() -> set[str]:
    """Route keys whose dependency tree establishes no caller identity."""
    return {
        _route_key(route, method)
        for route, method in _api_routes()
        if not (_dependency_calls(route) & IDENTITY_DEPENDENCIES)
    }


def _concrete_path(path: str) -> str:
    """Fill in path parameters with a value that never has to resolve.

    Covers Starlette convertors too (`{path:path}`) — the whole brace group is
    replaced, so the type suffix goes with it.
    """
    return re.sub(r"\{[^}]+\}", DUMMY_PATH_VALUE, path)


def _mock_session() -> AsyncMock:
    """A session that answers nothing.

    It exists only so `get_session` never opens a socket. If a route reaches it
    at all, that route did not reject the caller and the walk has already found
    its bug.
    """
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    result.all.return_value = []
    session.execute.return_value = result
    return session


@contextlib.asynccontextmanager
async def _saas_client(user=None):
    """A SaaS-mode client with the database stubbed and auth left real.

    Passing `user` overrides `get_current_user` (and the or-default variant)
    to make the caller that user — used by the role walk below, which needs an
    authenticated but unprivileged caller. Passing nothing leaves the real auth
    dependency in place, which is what the authn walk needs.
    """
    session = _mock_session()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    if user is not None:

        async def override_user():
            return user

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_current_user_or_default] = override_user
    try:
        with patch.object(settings, "self_hosted", False):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client
    finally:
        app.dependency_overrides.clear()


async def _probe(client: httpx.AsyncClient, method: str, path: str) -> int | str:
    """Request one route and describe the outcome as a status code or a reason.

    A route that rejects its caller never reaches the handler, so it answers in
    about a millisecond and cannot raise. Blocking or blowing up therefore means
    the caller got through -- which is the finding, not an infrastructure
    problem to be papered over. Both are reported in place of a status code so
    the failure message names the route either way.
    """
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT_S):
            return (await client.request(method, path)).status_code
    except TimeoutError:
        return f"timed out after {REQUEST_TIMEOUT_S}s"
    except Exception as exc:
        # Truncated: a handler that ran against the stub session can raise a
        # multi-page validation error, and the route name is the useful part.
        return f"handler ran and raised {type(exc).__name__}: {str(exc).splitlines()[0][:120]}"


def test_public_route_allowlist_is_exact():
    """The set of routes with no identity dependency must match the allowlist.

    Exact in both directions. A new endpoint that forgot its auth dependency
    fails here even before the behavioural walk gets to it, and an endpoint that
    later gained one fails until its stale entry is deleted.
    """
    actual = _unauthenticated_routes()
    missing = sorted(actual - PUBLIC)
    stale = sorted(PUBLIC - actual)

    assert not missing, (
        "Route(s) reachable with no caller identity and not on the allowlist:\n"
        + "\n".join(f"  {k}" for k in missing)
        + "\n\nAdd `user: User = Depends(get_current_user_or_default)` to the endpoint, "
        "or, if it is genuinely public, add it to PUBLIC_BY_DESIGN in "
        "tests/unit/api/test_endpoint_authn_guard.py with a reason."
    )
    assert not stale, (
        "Allowlist entries that are no longer unauthenticated -- the route gained "
        "auth, was renamed, or was removed. Delete them from "
        "tests/unit/api/test_endpoint_authn_guard.py:\n" + "\n".join(f"  {k}" for k in stale)
    )


def test_known_unauthenticated_routes_are_still_present():
    """Pin the unprotected routes so they cannot be quietly lost.

    If one stops being reported it was either fixed (remove it from the dict) or
    the detection rule regressed (fix the rule) -- both need a human to look.
    Written as a loop rather than a parametrize so that an empty dict is a pass
    and not a skip: a guard that reports "skipped" is a guard nobody reads.
    """
    actual = _unauthenticated_routes()
    lost = sorted(k for k in KNOWN_UNAUTHENTICATED_PENDING_FIX if k not in actual)
    assert not lost, (
        "No longer detected as unauthenticated:\n"
        + "\n".join(f"  {k}" for k in lost)
        + "\nIf they were fixed, remove them from KNOWN_UNAUTHENTICATED_PENDING_FIX."
    )


@pytest.mark.asyncio
async def test_every_protected_route_401s_an_anonymous_caller():
    """The behavioural half: walk the app and knock on every protected door."""
    walked, wrong, truncated = 0, [], False

    async with _saas_client() as client:
        for route, method in _api_routes():
            key = _route_key(route, method)
            if key in PUBLIC:
                continue
            walked += 1
            status = await _probe(client, method, _concrete_path(route.path))
            if status != 401:
                wrong.append(f"  {key} -> {status}")
                if len(wrong) >= MAX_FINDINGS:
                    truncated = True
                    break

    assert not wrong, (
        "Route(s) did not reject an unauthenticated caller in SaaS mode "
        "(self_hosted=False):\n"
        + "\n".join(sorted(wrong))
        + (f"\n  ... stopped after {MAX_FINDINGS} findings" if truncated else "")
    )
    # A walk that silently stopped enumerating would pass with zero findings.
    assert walked > 100, f"only {walked} protected routes walked -- enumeration broke"


@pytest.mark.asyncio
async def test_admin_routes_403_a_non_admin_caller(make_user):
    """Privilege escalation: an authenticated `role="user"` must not reach admin.

    The same enumeration, one layer further in. Four admin endpoints already had
    a hand-written non-admin test; this covers every route whose dependency tree
    contains a `require_role` the caller does not satisfy, so the eleventh admin
    endpoint someone adds is covered on the day it is written.
    """
    caller = make_user(id="user-002", role="user", tier="free")
    checked, wrong = 0, []

    async with _saas_client(user=caller) as client:
        for route, method in _api_routes():
            allowed = _allowed_roles(route)
            if allowed is None or caller.role in allowed:
                continue
            checked += 1
            status = await _probe(client, method, _concrete_path(route.path))
            if status != 403:
                wrong.append(f"  {_route_key(route, method)} -> {status}")

    assert not wrong, (
        "Role-restricted route(s) did not reject a role='user' caller with 403:\n"
        + "\n".join(sorted(wrong))
    )
    assert checked, "no role-restricted routes found -- the require_role detection broke"
