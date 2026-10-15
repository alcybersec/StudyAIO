"""Contract test for `api.weak-spots v1` (docs/CONTRACTS.md, ADR 0007 Decision 7).

Checks the HTTP surface ``backend`` owes ``frontend`` against the live app:

1. Every ``Method | Path`` row of the entry's route table is a route of
   ``app.main.app``, and the weak-spot prefixes carry no route the table lacks.
2. Every one of them requires a caller (``get_current_user_or_default`` or
   ``get_current_user`` in its dependency tree).
3. ``POST /api/weak-spots/targeted`` — the only route here that spends AI —
   declares ``require_ai_consent`` (``api.ai-consent v1``); no other route here
   does, because none other spends.
4. The usage events the entry adds to ``services.usage v1`` exist, and the
   client-reportable set did not grow.

Behaviour (status codes, scoping wiring, the daily cap) is ``backend``'s unit
tests and ``qa``'s integration tests; ``safety``'s derived guards cover
authn, scoping and consent for routes nobody listed.

Red until ``backend`` lands ``app/api/weakspots.py`` (M33-S2-BACKEND-020).
"""

import pytest
from fastapi.routing import APIRoute

from tests.contracts._weakspot_docs import contract_section, table_rows

HEADING = "### api.weak-spots v1"
PREFIXES = ("/api/weak-spots", "/api/study-plan")
SPENDING_ROUTE = ("POST", "/api/weak-spots/targeted")


@pytest.fixture(scope="module")
def contract_routes() -> set[tuple[str, str]]:
    rows = table_rows(contract_section(HEADING), "Method")
    routes = {(row[0].strip("`"), row[1].strip("`")) for row in rows}
    assert len(routes) == 6, f"expected 6 routes in {HEADING}, found {sorted(routes)}"
    return routes


@pytest.fixture(scope="module")
def app_routes() -> dict[tuple[str, str], APIRoute]:
    from app.main import app

    out: dict[tuple[str, str], APIRoute] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                out[(method, route.path)] = route
    return out


def _dependency_calls(route: APIRoute) -> set[object]:
    calls: set[object] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if dep.call is not None:
            calls.add(dep.call)
        stack.extend(dep.dependencies)
    return calls


def test_every_contract_route_exists(contract_routes, app_routes):
    missing = sorted(contract_routes - set(app_routes))
    assert not missing, f"routes in {HEADING} that the app does not serve: {missing}"


def test_no_unlisted_route_under_the_prefixes(contract_routes, app_routes):
    extra = sorted(
        key for key in app_routes if key[1].startswith(PREFIXES) and key not in contract_routes
    )
    assert not extra, f"routes under {PREFIXES} missing from {HEADING}: {extra}"


def test_every_route_requires_a_caller(contract_routes, app_routes):
    from app.api.deps import get_current_user, get_current_user_or_default

    callers = {get_current_user, get_current_user_or_default}
    anonymous = sorted(
        key
        for key in contract_routes
        if key in app_routes and not (_dependency_calls(app_routes[key]) & callers)
    )
    assert not anonymous, f"routes that do not resolve a caller: {anonymous}"


def test_only_the_targeted_route_is_consent_gated(contract_routes, app_routes):
    from app.api.deps import require_ai_consent

    assert SPENDING_ROUTE in app_routes, f"{SPENDING_ROUTE} is not served yet"
    gated = {
        key
        for key in contract_routes
        if key in app_routes and require_ai_consent in _dependency_calls(app_routes[key])
    }
    assert gated == {SPENDING_ROUTE}


def test_usage_events_added_and_client_set_unchanged():
    from app.services import usage_service

    assert {"study_plan_built", "targeted_generation_requested"} <= usage_service.USAGE_EVENTS
    assert frozenset({"summary_viewed", "study_plan_viewed"}) == usage_service.CLIENT_EVENTS
