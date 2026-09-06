"""The real authentication boundary, exercised with no dependency override.

Every other API test in this suite arrives pre-authenticated. `tests/conftest.py`
installs

    app.dependency_overrides[get_current_user_or_default] = override_user

for the `async_client` fixture, so the dependency that decides *whether a caller
has an identity at all* never runs. Thirteen test files depend on that override,
and none of them can fail if it stops rejecting anonymous callers.

That matters more here than in most apps, because of the shape of the real
dependency (`app/api/deps.py`):

    if settings.self_hosted:
        try:
            return await get_current_user(request, session)
        except AuthenticationError:
            return await _get_or_create_default_user(session)   # the DEFAULT ADMIN
    else:
        return await get_current_user(request, session)

A single boolean stands between a public instance and handing every anonymous
caller the default admin identity. Production runs `SELF_HOSTED=false`, so this
is not a live bug — but nothing was preventing the regression, and the blast
radius is total.

So these tests build their own client with **only** `get_session` overridden,
and drive real HTTP requests through the real dependency. `GET /api/courses` is
the stand-in protected endpoint: it depends on `get_current_user_or_default` and
does nothing but hand `user.id` to one service call, which is exactly the thing
worth watching.

The route-level counterpart — *every* protected endpoint, not just this one —
lives in `test_endpoint_authn_guard.py`.
"""

import contextlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import app.api.deps as deps_module
from app.api.deps import DEFAULT_ADMIN_ID
from app.config import settings
from app.core.auth import ACCESS_TOKEN_COOKIE, create_access_token, decode_token
from app.core.database import get_session
from app.main import app

# A protected endpoint whose whole body is one owner-scoped service call, so a
# fallback to another identity is visible in the call's kwargs rather than only
# in the status code.
PROTECTED_ENDPOINT = "/api/courses"
SERVICE_CALL = "app.api.courses.course_service.list_courses_with_stats"


def _session_returning_no_rows() -> AsyncMock:
    """An AsyncSession stand-in whose queries all come back empty.

    Deliberately not the shared `mock_session` fixture: these tests assert that
    the session is never *reached*, so the session has to be theirs to inspect.
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
async def real_auth_client(
    *, self_hosted: bool, session: AsyncMock, cookies: dict[str, str] | None = None
):
    """A client that overrides the database and **nothing else**.

    `get_current_user_or_default` is left alone, which is the entire point of
    this module. `self_hosted` is patched on the shared `Settings` instance —
    `app.api.deps` holds a reference to that same object, so patching the
    attribute reaches the dependency.
    """

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    # The default admin is memoised in a module global; a value left behind by
    # one test would let the next one pass without the lookup it is testing.
    deps_module._default_user_cache = None
    try:
        with patch.object(settings, "self_hosted", self_hosted):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                cookies=cookies,
            ) as client:
                yield client
    finally:
        deps_module._default_user_cache = None
        app.dependency_overrides.clear()


def _cutoff_after(token: str) -> datetime:
    """A session cutoff guaranteed to postdate `token`.

    `iat` is a whole-second epoch value, so a cutoff read off the wall clock
    just before minting lands *below* the token's second whenever the two
    straddle a boundary, and the token then reads as still valid. Anchoring to
    the token's own `iat` makes "revoked after this token was issued" exact.
    """
    return datetime.fromtimestamp(decode_token(token)["iat"], tz=UTC) + timedelta(seconds=1)


@pytest.mark.asyncio
class TestSaaSModeRejectsAnonymousCallers:
    """SaaS mode (`self_hosted=False`) must never invent an identity."""

    async def test_unauthenticated_request_is_rejected(self):
        """No cookie, no identity: 401, and the handler never runs.

        The status code alone is not enough. A 401 could in principle come from
        somewhere else in the stack, so this also asserts the endpoint's service
        call was never made — i.e. nothing downstream saw *any* user id.
        """
        session = _session_returning_no_rows()
        with patch(SERVICE_CALL, new_callable=AsyncMock, return_value=[]) as list_courses:
            async with real_auth_client(self_hosted=False, session=session) as client:
                response = await client.get(PROTECTED_ENDPOINT)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        list_courses.assert_not_awaited()

    async def test_garbage_token_is_rejected_not_downgraded(self):
        """An unparseable cookie is a rejection, never a fall back to default."""
        session = _session_returning_no_rows()
        with patch(SERVICE_CALL, new_callable=AsyncMock, return_value=[]) as list_courses:
            async with real_auth_client(
                self_hosted=False, session=session, cookies={ACCESS_TOKEN_COOKIE: "not-a-jwt"}
            ) as client:
                response = await client.get(PROTECTED_ENDPOINT)

        assert response.status_code == 401
        list_courses.assert_not_awaited()

    async def test_valid_token_is_accepted(self, make_user):
        """The positive control.

        Without this, every assertion above would still pass if the client were
        simply broken — a 401 from a misconfigured test rig proves nothing about
        the boundary. This shows the same client, same dependency, and a real
        token gets through carrying the *token's* identity.
        """
        user = make_user(id="user-001")
        token = create_access_token(user.id, user.role, user.tier)
        session = _session_returning_no_rows()

        with (
            patch(SERVICE_CALL, new_callable=AsyncMock, return_value=[]) as list_courses,
            patch(
                "app.api.deps.user_service.get_user_by_id",
                new_callable=AsyncMock,
                return_value=user,
            ) as get_user_by_id,
        ):
            async with real_auth_client(
                self_hosted=False, session=session, cookies={ACCESS_TOKEN_COOKIE: token}
            ) as client:
                response = await client.get(PROTECTED_ENDPOINT)

        assert response.status_code == 200
        # The user came from the *token's* subject, not from whatever the stub
        # happened to return: without this the test passes even if the
        # dependency looks up a hard-coded id.
        assert get_user_by_id.await_args.args[1] == "user-001"
        assert list_courses.await_args.kwargs["user_id"] == "user-001"


@pytest.mark.asyncio
class TestSelfHostedModeFallsBack:
    """Self-hosted mode deliberately hands an anonymous caller the default admin.

    That is the product decision a single-user box is built on — no login wall
    on your own machine — and it is as much a regression risk as the SaaS
    branch. If someone "hardens" the dependency by deleting the fallback, every
    self-hosted install breaks on upgrade, silently, at the first request.
    """

    async def test_anonymous_request_gets_the_default_admin(self):
        """No cookie in self-hosted mode: the handler runs, as the default admin."""
        session = _session_returning_no_rows()
        with patch(SERVICE_CALL, new_callable=AsyncMock, return_value=[]) as list_courses:
            async with real_auth_client(self_hosted=True, session=session) as client:
                response = await client.get(PROTECTED_ENDPOINT)

        assert response.status_code == 200
        assert list_courses.await_args.kwargs["user_id"] == DEFAULT_ADMIN_ID

    async def test_valid_token_wins_over_the_default_admin(self, make_user):
        """A self-hosted user who *did* log in keeps their own identity."""
        user = make_user(id="user-001")
        token = create_access_token(user.id, user.role, user.tier)
        session = _session_returning_no_rows()

        with (
            patch(SERVICE_CALL, new_callable=AsyncMock, return_value=[]) as list_courses,
            patch(
                "app.api.deps.user_service.get_user_by_id",
                new_callable=AsyncMock,
                return_value=user,
            ) as get_user_by_id,
        ):
            async with real_auth_client(
                self_hosted=True, session=session, cookies={ACCESS_TOKEN_COOKIE: token}
            ) as client:
                response = await client.get(PROTECTED_ENDPOINT)

        assert response.status_code == 200
        assert get_user_by_id.await_args.args[1] == "user-001"
        assert list_courses.await_args.kwargs["user_id"] == "user-001"


@pytest.mark.asyncio
class TestRevokedSessionIsNotDowngraded:
    """`SessionRevokedError` must propagate, in both modes.

    `deps.py` says it in a comment: falling back here "would hand the caller the
    (admin) default identity — an upgrade, not a rejection". The reasoning is
    right and entirely invisible at the HTTP boundary, where the difference
    between a rejection and a promotion to admin is one `except` clause. Hence a
    guard.
    """

    async def test_self_hosted_revoked_token_is_rejected(self, make_user):
        """The interesting case: the mode that *has* a fallback must not use it."""
        user = make_user(id="user-001")
        token = create_access_token(user.id, user.role, user.tier)
        user.tokens_valid_from = _cutoff_after(token)
        session = _session_returning_no_rows()

        with (
            patch(SERVICE_CALL, new_callable=AsyncMock, return_value=[]) as list_courses,
            patch(
                "app.api.deps.user_service.get_user_by_id",
                new_callable=AsyncMock,
                return_value=user,
            ),
        ):
            async with real_auth_client(
                self_hosted=True, session=session, cookies={ACCESS_TOKEN_COOKIE: token}
            ) as client:
                response = await client.get(PROTECTED_ENDPOINT)

        assert response.status_code == 401
        assert "sign in again" in response.json()["detail"]
        # The load-bearing assertion: had the fallback swallowed it, this would
        # have been awaited with user_id=DEFAULT_ADMIN_ID and a 200 returned.
        list_courses.assert_not_awaited()

    async def test_saas_revoked_token_is_rejected(self, make_user):
        """Same outcome in SaaS mode, by the plain absence of any fallback."""
        user = make_user(id="user-001")
        token = create_access_token(user.id, user.role, user.tier)
        user.tokens_valid_from = _cutoff_after(token)
        session = _session_returning_no_rows()

        with (
            patch(SERVICE_CALL, new_callable=AsyncMock, return_value=[]) as list_courses,
            patch(
                "app.api.deps.user_service.get_user_by_id",
                new_callable=AsyncMock,
                return_value=user,
            ),
        ):
            async with real_auth_client(
                self_hosted=False, session=session, cookies={ACCESS_TOKEN_COOKIE: token}
            ) as client:
                response = await client.get(PROTECTED_ENDPOINT)

        assert response.status_code == 401
        list_courses.assert_not_awaited()
