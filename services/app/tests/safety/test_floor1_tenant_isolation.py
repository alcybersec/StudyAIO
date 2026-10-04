"""Floor 1 — tenant isolation.

    an authenticated endpoint never returns or mutates another user's rows;
    every user-owned query filters on user_id

Three layers, each catching what the one before cannot:

1. **Route sweep** (``test_floor1_route_sweep_*``). Every authenticated,
   non-admin route is called with a caller-supplied foreign id and a mock
   session that records each SQL statement. Every statement that touches a
   user-owned table must compare some ``user_id`` column to *the caller's* id.
   This is the floor's own wording, checked on the SQL the handler actually
   built, not on what its source mentions. It sees only the statements a
   handler reaches against empty results: follow-up queries behind a found row
   are covered by layer 2 and by ``tests/integration/test_idor_row_level.py``.
2. **Unscoped primary-key fetch** (``test_floor1_no_unscoped_session_get``).
   ``session.get(Model, id)`` builds no WHERE clause at all, so no SQL check can
   scope it. Statically, no ``api``/``services`` function may fetch a
   user-owned model by a caller-supplied id this way except the classified
   entries below.
3. **Behaviour** for each known violation, so the fix is pinned by a test that
   does not care how it was fixed.

``tests/unit/api/test_endpoint_scoping_guard.py`` (the #47/#53 guard) checks the
endpoint layer; layer 2 exists because that guard trusts a ``user_id=`` keyword
at the call site, and ``attach_assessment_document`` takes one and ignores it
for the lookup.
"""

from __future__ import annotations

import ast
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.routing import APIRoute

from tests.safety._source import app_modules, dotted, parse, rel, walk_with_scope
from tests.safety._tenant import (
    UNOWNED_TABLES,
    all_tables,
    filters_by_id_list,
    filters_on_user,
    tables_in,
    user_owned_tables,
)

FOREIGN_ID = "id-owned-by-someone-else"

#: Paths left out of the sweep, each with its reason.
SWEEP_EXCLUDED = {
    "/api/uploads/pipeline-events": "SSE stream: never completes under a test client",
}

#: Routes that scope in two steps: first select ids by ``user_id``, then
#: select children ``WHERE <fk> IN (<those ids>)``. The second statement
#: carries no user_id of its own, so for these the sweep requires only that
#: the route *anchors* on the caller (some statement filters on their id) and
#: that every unanchored statement is an ``IN`` over an id list.
TWO_STEP_SCOPED = {
    "GET /api/auth/account/export": (
        "account_service.export_user_data walks account_service.collect_owned_ids, "
        "which selects every parent id by user_id first; the same walk drives "
        "account deletion (tests/integration/test_account_deletion.py)"
    ),
}

#: Routes that read across users on purpose, where the floor's text and the
#: product disagree. Each needs the user's ruling: scope it, make it opt-in,
#: or amend the floor by ADR. Pinned both ways: an entry that stops crossing
#: users fails as stale, and the xfail(strict) test below fails once empty.
SWEEP_PENDING_RULING = {
    "GET /api/gamification/leaderboard": (
        "xp_service.get_leaderboard selects every user's user_xp joined to "
        "users.username with no opt-in, and returns user_id, username, total_xp "
        "and level of the top N to any authenticated caller (PRD_v2 lists the "
        "endpoint as 'optional'; no privacy rule is stated)"
    ),
}

#: Prefix of the admin surface. Admin routes are cross-user by design and are
#: authorised by role (tests/unit/api/test_admin_*.py), not by ownership.
ADMIN_PREFIX = "/api/admin"

#: The sweep must keep reaching this many routes that query a user-owned
#: table. A drop means the harness stopped exercising handlers (an auth
#: override broke, everything 401s) and every assertion became vacuous.
MIN_ROUTES_WITH_OWNED_QUERIES = 60


# ── layer 1: route sweep ───────────────────────────────────────────────


def _requires_user(route: APIRoute) -> bool:
    from app.api.deps import get_current_user, get_current_user_or_default

    wanted = {get_current_user, get_current_user_or_default}
    stack = [route.dependant]
    while stack:
        dep = stack.pop()
        if dep.call in wanted:
            return True
        stack.extend(dep.dependencies)
    return False


def _sweep_routes() -> list[tuple[str, str, APIRoute]]:
    from app.main import app

    out = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not _requires_user(route):
            continue
        if route.path.startswith(ADMIN_PREFIX) or route.path in SWEEP_EXCLUDED:
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            out.append((method, route.path, route))
    return out


def _empty_result(*_args, **_kwargs) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalars.return_value.first.return_value = None
    result.scalar_one_or_none.return_value = None
    result.scalar.return_value = None
    result.scalar_one.return_value = 0
    result.all.return_value = []
    result.first.return_value = None
    result.one_or_none.return_value = None
    result.rowcount = 0
    # .unique() / .tuples() chain back to the same empty result; otherwise a
    # MagicMock row appears "found" and the handler proceeds on a phantom.
    result.unique.return_value = result
    result.tuples.return_value = result
    return result


def _required_query_params(route: APIRoute) -> dict[str, object]:
    params: dict[str, object] = {}
    for qp in route.dependant.query_params:
        if qp.required:
            params[qp.alias] = 1 if qp.field_info.annotation is int else FOREIGN_ID
    return params


async def _run_sweep(async_client, mock_session, caller_id: str):
    """Call every swept route; return (violations, routes reaching owned tables, statuses)."""
    from app.api.deps import get_current_user
    from app.config import settings
    from app.core.rate_limit import limiter
    from app.main import app

    owned = user_owned_tables()
    captured: list = []
    fetched: list = []

    def record(statement, *_a, **_k):
        captured.append(statement)
        return _empty_result()

    async def record_get(model, ident, *_a, **_k):
        fetched.append((model, ident))
        return None

    mock_session.execute = AsyncMock(side_effect=record)
    mock_session.scalar = AsyncMock(side_effect=lambda s, *a, **k: captured.append(s))
    mock_session.get = AsyncMock(side_effect=record_get)
    user = app.dependency_overrides  # already holds get_current_user_or_default
    from app.api.deps import get_current_user_or_default

    app.dependency_overrides[get_current_user] = user[get_current_user_or_default]

    violations: dict[str, list[str]] = {}
    statuses: dict[str, object] = {}
    reached = 0
    with (
        # Unreachable Redis that refuses at once instead of timing out.
        patch.object(settings, "redis_url", "redis://127.0.0.1:1/0"),
        # ~150 requests from one client address would trip the per-route limits.
        patch.object(limiter, "enabled", False),
        patch("celery.app.task.Task.apply_async", MagicMock()),
        patch("celery.app.task.Task.delay", MagicMock()),
    ):
        for method, path, route in _sweep_routes():
            url = re.sub(r"\{\w+(:\w+)?\}", FOREIGN_ID, path)
            captured.clear()
            fetched.clear()
            try:
                response = await async_client.request(
                    method,
                    url,
                    params=_required_query_params(route),
                    json={} if method in {"POST", "PUT", "PATCH"} else None,
                    timeout=5,
                )
                statuses[f"{method} {path}"] = response.status_code
            except Exception as exc:  # a handler crash on a mock row is not the subject
                statuses[f"{method} {path}"] = type(exc).__name__
            bad = []
            touched_owned = False
            two_step = f"{method} {path}" in TWO_STEP_SCOPED
            anchored = any(filters_on_user(s, caller_id) for s in captured)
            for statement in captured:
                hit = tables_in(statement) & owned
                if not hit:
                    continue
                touched_owned = True
                if two_step and anchored and filters_by_id_list(statement):
                    continue
                if not filters_on_user(statement, caller_id):
                    flat = " ".join(str(statement).split())
                    bad.append(f"{sorted(hit)}: {flat[:220]}")
            for model, ident in fetched:
                table = getattr(model, "__tablename__", "")
                if table in owned:
                    touched_owned = True
                    bad.append(f"session.get({model.__name__}, {ident!r}) — no WHERE at all")
            reached += touched_owned
            if bad:
                violations[f"{method} {path}"] = bad
    return violations, reached, statuses


@pytest.mark.asyncio
async def test_floor1_route_sweep_every_owned_query_filters_on_caller(
    async_client, mock_session, default_test_user
):
    """Every user-owned query a handler issues compares user_id to the caller."""
    violations, reached, statuses = await _run_sweep(
        async_client, mock_session, default_test_user.id
    )
    unruled = {k: v for k, v in violations.items() if k not in SWEEP_PENDING_RULING}
    assert not unruled, (
        "Floor 1: route(s) issued a query on a user-owned table without "
        "filtering on the caller's user_id:\n"
        + "\n".join(f"  {route}\n    " + "\n    ".join(v) for route, v in unruled.items())
    )
    stale = sorted(set(SWEEP_PENDING_RULING) - set(violations))
    assert not stale, f"SWEEP_PENDING_RULING entries no longer cross users — remove them: {stale}"
    assert reached >= MIN_ROUTES_WITH_OWNED_QUERIES, (
        f"Sweep reached only {reached} routes that query a user-owned table "
        f"(floor {MIN_ROUTES_WITH_OWNED_QUERIES}). The harness has stopped "
        "exercising handlers; the scoping assertion above is vacuous until fixed.\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(statuses.items()))
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="VETO-relevant, awaiting user ruling: leaderboard returns other users' "
    "user_id/username/XP to every user (see SWEEP_PENDING_RULING)",
)
def test_floor1_no_cross_user_route_awaits_a_ruling():
    """Every deliberate cross-user read has been ruled on by the user.

    Strict: once the ruling lands (route scoped, made opt-in, or the floor
    amended by ADR), emptying ``SWEEP_PENDING_RULING`` turns this into an
    XPASS, which fails — forcing the marker off with the entry.
    """
    assert not SWEEP_PENDING_RULING, "\n".join(
        f"  {k}: {v}" for k, v in SWEEP_PENDING_RULING.items()
    )


def test_floor1_every_table_is_classified():
    """Each table is user-owned or explicitly unowned — nothing in between."""
    tables = set(all_tables())
    owned = user_owned_tables()
    unclassified = sorted(tables - owned - UNOWNED_TABLES)
    stale = sorted(UNOWNED_TABLES - tables)
    assert not unclassified, (
        f"Tables neither user-owned nor in UNOWNED_TABLES: {unclassified}. Give the "
        "table a user_id (or a FK to an owned table), or add it to UNOWNED_TABLES / "
        "POLYMORPHIC_OWNED in tests/safety/_tenant.py with a reason."
    )
    assert not stale, f"UNOWNED_TABLES names tables that no longer exist: {stale}"


# ── layer 2: unscoped primary-key fetch ────────────────────────────────

#: (module, function, model) -> reason the fetch is safe.
UNSCOPED_GET_ALLOWED = {
    ("app/services/courseops_service.py", "_get_course_owned", "model"): (
        "the user_id=None branch, for the extraction pipeline; endpoints must pass "
        "user_id, which tests/unit/api/test_endpoint_scoping_guard.py enforces"
    ),
    ("app/services/courseops_service.py", "process_course_document", "CourseDocument"): (
        "called only from app/pipeline/courseops_task.py with an id the worker "
        "was handed by the upload endpoint (pinned below)"
    ),
    ("app/services/feedback_service.py", "set_status", "Feedback"): (
        "admin-only route behind require_role('admin'); triage is cross-user"
    ),
}

#: Live violations. Each has a behavioural test below that fails until fixed;
#: an entry here only keeps the static test from double-reporting it.
#:
#: Empty since M31-S1-BACKEND-008 (a2cd687): ``attach_assessment_document`` now
#: resolves the assessment through ``_get_course_owned`` (a join on
#: ``courses.user_id``). Its behavioural test stays as the regression pin.
UNSCOPED_GET_VIOLATIONS: dict[tuple[str, str, str], str] = {}

SESSION_NAMES = frozenset({"session", "db"})
SCANNED = ("app/api/", "app/services/")


def _owned_model_names() -> set[str]:
    owned = user_owned_tables()
    from app.core.database import Base

    return {
        mapper.class_.__name__
        for mapper in Base.registry.mappers
        if getattr(mapper.class_, "__tablename__", None) in owned
    }


def _function_params(tree: ast.Module) -> dict[str, set[str]]:
    params: dict[str, set[str]] = {}
    for node, scope in walk_with_scope(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            name = f"{scope}.{node.name}" if scope != "<module>" else node.name
            args = node.args
            params[name] = {a.arg for a in args.args + args.kwonlyargs + args.posonlyargs}
    return params


def unscoped_session_gets() -> dict[tuple[str, str, str], str]:
    """``session.get(Model, <param>)`` on a user-owned model, keyed (module, fn, model)."""
    owned_models = _owned_model_names()
    found: dict[tuple[str, str, str], str] = {}
    for path in app_modules():
        module = rel(path)
        if not module.startswith(SCANNED):
            continue
        tree = parse(path)
        params = _function_params(tree)
        for node, scope in walk_with_scope(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and dotted(node.func.value) in SESSION_NAMES
                and len(node.args) >= 2
            ):
                continue
            model_text = dotted(node.args[0])
            ident = node.args[1]
            # Only an id the function was handed: an attribute of an
            # already-resolved row (doc.course_id) is FK traversal, not a lookup.
            if not (isinstance(ident, ast.Name) and ident.id in params.get(scope, set())):
                continue
            if model_text in owned_models or model_text == "model":
                found[(module, scope, model_text)] = f"{module}:{node.lineno}"
    return found


def test_floor1_no_unscoped_session_get_on_owned_model():
    """No api/service function fetches an owned row by a caller id via session.get."""
    found = unscoped_session_gets()
    known = set(UNSCOPED_GET_ALLOWED) | set(UNSCOPED_GET_VIOLATIONS)
    new = {k: v for k, v in found.items() if k not in known}
    stale = sorted(known - set(found))
    assert not new, (
        "Floor 1: session.get() on a user-owned model by a caller-supplied id, with "
        "no owner check in the query:\n"
        + "\n".join(f"  {loc}  {key}" for key, loc in sorted(new.items()))
        + "\nScope the lookup (select ... where user_id == ...), or classify it in "
        "tests/safety/test_floor1_tenant_isolation.py with a reason."
    )
    assert not stale, (
        "Classified session.get() sites no longer present — remove them:\n"
        + "\n".join(f"  {k}" for k in stale)
    )


def test_floor1_pipeline_only_fetch_is_pipeline_only():
    """``process_course_document`` (unscoped fetch) is called only by the worker."""
    callers = set()
    for path in app_modules():
        tree = parse(path)
        for node, scope in walk_with_scope(tree):
            if isinstance(node, ast.Call) and dotted(node.func).endswith(
                "courseops_service.process_course_document"
            ):
                callers.add((rel(path), scope))
    assert callers, "detector found no caller at all — it has gone blind"
    outside = sorted(c for c in callers if not c[0].startswith("app/pipeline/"))
    assert not outside, f"process_course_document called outside the worker: {outside}"


# ── layer 3: behaviour of each known violation ─────────────────────────


@pytest.mark.asyncio
async def test_floor1_cannot_attach_document_to_another_users_assessment():
    """User B must not be able to attach a document to user A's assessment.

    Implementation-agnostic: a fix may scope the lookup in SQL, or fetch and
    compare the course's owner. Either way the call must return None and add
    nothing.

    The fake session behaves like the database holding A's assessment: a
    lookup that filters on B's ``user_id`` finds nothing, and any other lookup
    (``session.get``, or a ``select`` with no owner filter, or one filtered on
    the wrong user) finds A's row. So an unscoped ``select`` does not pass by
    accident on an empty mock result. The control call as owner A must find the
    row, which shows the fake is not empty for everyone.
    """
    from app.models.assessment import Assessment
    from app.models.course import Course
    from app.services import courseops_service

    owner_a, caller_b = "user-a", "user-b"
    assessment = MagicMock(spec=Assessment)
    assessment.id = "assessment-of-a"
    assessment.course_id = "course-of-a"
    course = MagicMock(spec=Course)
    course.id = "course-of-a"
    course.user_id = owner_a

    def as_database(statement, *_a, **_k):
        result = _empty_result()
        if "assessments" in tables_in(statement) and not filters_on_user(statement, caller_b):
            result.scalar_one_or_none.return_value = assessment
            result.scalars.return_value.first.return_value = assessment
            result.first.return_value = assessment
        return result

    def fake_session() -> AsyncMock:
        session = AsyncMock()
        session.add = MagicMock()
        session.execute = AsyncMock(side_effect=as_database)

        async def get(model, ident, *_a, **_k):
            return {Assessment: assessment, Course: course}.get(model)

        session.get = AsyncMock(side_effect=get)
        return session

    def attach(session: AsyncMock, user_id: str):
        return courseops_service.attach_assessment_document(
            session=session,
            assessment_id="assessment-of-a",
            document_type="brief",
            original_filename="brief.pdf",
            file_path=f"courseops/{user_id}/x/brief.pdf",
            file_type="pdf",
            sha256="b" * 64,
            file_size_bytes=10,
            user_id=user_id,
        )

    control = fake_session()
    assert await attach(control, owner_a) is not None, (
        "control: the owner's own attach found nothing, so the fake proves nothing"
    )

    session = fake_session()
    doc = await attach(session, caller_b)

    assert doc is None, (
        "Floor 1 VIOLATION: attach_assessment_document attached user B's document "
        "to user A's assessment (lookup not scoped to the course owner)."
    )
    session.add.assert_not_called()
