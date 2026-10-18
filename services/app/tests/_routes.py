"""Route enumeration that survives FastAPI's lazy ``include_router``.

From fastapi 0.137 ``app.include_router`` no longer copies routes into
``app.routes``; it appends one ``_IncludedRouter`` wrapper per inclusion. A guard
that does ``for r in app.routes: if isinstance(r, APIRoute)`` then sees no
included route at all and passes vacuously (R-040). ``api_routes`` expands the
wrappers through FastAPI's public ``iter_route_contexts``.

Each item is a ``RouteContext``. ``.path``, ``.methods``, ``.dependant``,
``.endpoint``, ``.response_model`` and the rest resolve to the *effective* route
(include prefix and include-level dependencies applied), which is what a request
actually runs. ``.original_route`` is the underlying ``APIRoute``.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts


def route_contexts(app: FastAPI) -> list[RouteContext]:
    """Every route of ``app`` with lazy includes expanded (any route type)."""
    return list(iter_route_contexts(app.routes))


def api_routes(app: FastAPI) -> list[RouteContext]:
    """Every ``APIRoute`` of ``app``, effective path and dependencies applied."""
    return [rc for rc in route_contexts(app) if isinstance(rc.original_route, APIRoute)]
