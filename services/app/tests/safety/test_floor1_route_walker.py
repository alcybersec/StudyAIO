"""Floor 1: the route walker sees the route a request actually runs.

M34-S2-SEC-007 lifted fastapi past 0.137, where ``include_router`` became lazy.
Every route-walking floor guard (the tenant sweep, the anonymous-caller pin, the
consent gate, the admin-aggregate pin) now enumerates through
``tests._routes.api_routes``, which expands the ``_IncludedRouter`` wrappers via
FastAPI's ``iter_route_contexts``. ``test_floor1_route_enumeration_is_not_vacuous``
proves the walker finds every route; this file proves it describes each one the
way the request path does.

The app passes no include-level ``dependencies=`` today, so nothing in the live
app would notice if the effective context stopped carrying them. A future
``app.include_router(r, dependencies=[Depends(get_current_user)])`` would then
read as an anonymous route to ``_requires_user``, and the sweep would skip it.
A synthetic app with a nested include pins that the walker returns the include
prefixes, the include-level dependencies and the route's own response model,
and that the request really runs the include-level dependency it reports.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.deps import get_current_user
from tests._routes import api_routes
from tests.safety.test_floor1_tenant_isolation import _requires_user


class _Out(BaseModel):
    ok: bool


def _synthetic_app() -> FastAPI:
    inner = APIRouter(prefix="/inner")

    @inner.get("/thing/{thing_id}", response_model=_Out)
    async def read_thing(thing_id: str) -> _Out:
        return _Out(ok=True)

    outer = APIRouter(prefix="/outer")
    outer.include_router(inner, dependencies=[Depends(get_current_user)])

    app = FastAPI()
    app.include_router(outer, prefix="/api")

    def _refuse() -> None:
        raise HTTPException(status_code=401, detail="no caller")

    app.dependency_overrides[get_current_user] = _refuse
    return app


def test_floor1_route_walker_returns_the_effective_route():
    """Nested prefixes, include-level dependencies and response_model all resolve."""
    app = _synthetic_app()

    routes = api_routes(app)
    assert [r.path for r in routes] == ["/api/outer/inner/thing/{thing_id}"]
    route = routes[0]
    assert route.methods == {"GET"}
    assert route.response_model is _Out
    assert isinstance(route.original_route, APIRoute)
    assert _requires_user(route), (
        "an include-level get_current_user is missing from the walked route's dependant; "
        "the floor-1 sweep would treat this route as anonymous and skip it"
    )
    # The control: the bare APIRoute knows neither the prefixes nor the dependency.
    # If the walker ever returned it, the two assertions above are what would fail.
    assert route.original_route.path == "/inner/thing/{thing_id}"
    assert not _requires_user(route.original_route)
    # And the pre-0.137 walker, applied to this app, sees nothing (R-040).
    assert not [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api")]


def test_floor1_route_walker_dependency_is_the_one_the_request_runs():
    """The include-level dependency the walker reports is enforced on a real request."""
    app = _synthetic_app()
    with TestClient(app) as client:
        assert client.get("/api/outer/inner/thing/x").status_code == 401
        app.dependency_overrides.clear()
        app.dependency_overrides[get_current_user] = object
        assert client.get("/api/outer/inner/thing/x").json() == {"ok": True}
