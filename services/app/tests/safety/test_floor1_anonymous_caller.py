"""Floor 1: an anonymous caller never acts as a user unless single-user mode is opted into.

M32 gate (SAFETY, SEC-05 / GL#25, backend `33c7d1d`, R-035). Before SEC-05,
``SELF_HOSTED=true`` (the shipped default) made every unauthenticated request act
as the default admin, so anyone who could reach the API read and changed the
admin's rows and reached every admin route. SEC-05 made "no login" an explicit
opt-in (``SINGLE_USER_MODE``) and ``SELF_HOSTED`` an authenticated mode.

The unit tier pins the dependency on its own
(``tests/unit/test_single_user_mode.py``). This pin goes through the real app:
every route that requires a user, admin routes included, is called with no
session cookie on a self-hosted, multi-user instance, and must answer 401
without ever resolving the default admin. The single-user control proves the
harness can see the fallback when it is meant to happen.
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.routing import APIRoute

from tests.safety.test_floor1_tenant_isolation import _requires_user

#: Placeholder for every path parameter. "1" parses as an int and as a string;
#: authentication is solved before path, query and body validation, so the value
#: never reaches a handler on the expected (401) path.
_PATH_VALUE = "1"

#: The pin is vacuous if the app stops yielding user-requiring routes (a lazy
#: ``include_router`` on fastapi>=0.137 does that; see the route-enumeration
#: guard in test_floor1_tenant_isolation.py). 149 /api routes at M32.
MIN_ROUTES = 120


def _user_routes() -> list[tuple[str, str]]:
    from app.main import app

    out = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not _requires_user(route):
            continue
        path = re.sub(r"\{[^}]+\}", _PATH_VALUE, route.path)
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            out.append((method, path))
    return out


async def _call_all_anonymously(
    mock_session, *, self_hosted: bool, single_user_mode: bool
) -> tuple[dict[str, int], AsyncMock]:
    import app.api.deps as deps
    from app.config import settings
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    async def override_session():
        yield mock_session

    default_admin = AsyncMock(side_effect=RuntimeError("default admin resolved"))
    statuses: dict[str, int] = {}
    app.dependency_overrides[get_session] = override_session
    limiter.reset()
    try:
        with (
            patch.object(settings, "self_hosted", self_hosted),
            patch.object(settings, "single_user_mode", single_user_mode),
            patch.object(deps, "_get_or_create_default_user", default_admin),
            patch.object(deps, "_default_user_cache", None),
        ):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                for method, path in _user_routes():
                    response = await client.request(method, path)
                    statuses[f"{method} {path}"] = response.status_code
    finally:
        app.dependency_overrides.clear()
    return statuses, default_admin


@pytest.mark.asyncio
async def test_floor1_self_hosted_anonymous_caller_is_401_on_every_user_route(mock_session):
    """SELF_HOSTED without SINGLE_USER_MODE: no cookie means 401, never the default admin."""
    statuses, default_admin = await _call_all_anonymously(
        mock_session, self_hosted=True, single_user_mode=False
    )
    assert len(statuses) >= MIN_ROUTES, (
        f"only {len(statuses)} user-requiring routes enumerated (floor {MIN_ROUTES}); "
        "the pin is vacuous"
    )
    assert default_admin.await_count == 0, (
        "Floor 1 (SEC-05): an unauthenticated request on a self-hosted, multi-user "
        f"instance resolved the default admin {default_admin.await_count} time(s)"
    )
    not_401 = {k: v for k, v in statuses.items() if v != 401}
    assert not not_401, (
        "Floor 1 (SEC-05): user-requiring routes answered an anonymous caller with "
        "something other than 401 on a self-hosted, multi-user instance:\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(not_401.items()))
    )


@pytest.mark.asyncio
async def test_floor1_single_user_mode_control_reaches_the_default_admin(mock_session):
    """Control: with SINGLE_USER_MODE the same harness does see the fallback."""
    statuses, default_admin = await _call_all_anonymously(
        mock_session, self_hosted=True, single_user_mode=True
    )
    assert default_admin.await_count > 0, (
        "the harness never reached the single-user fallback, so the 401 pin above "
        "cannot tell a fixed dependency from a broken harness"
    )
