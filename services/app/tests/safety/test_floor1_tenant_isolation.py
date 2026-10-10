"""Floor 1 — tenant isolation.

    an authenticated endpoint never returns or mutates another user's rows;
    every user-owned query filters on user_id

Three layers, each catching what the one before cannot:

1. **Route sweep** (``test_floor1_route_sweep_*``). Every authenticated,
   non-admin route is called with a type-valid request built from its own
   declared types (``tests/safety/_payload.py``): a foreign id in every path
   parameter (an ``int`` for ``week: int``) and every body field. A mock
   session records each SQL statement. Every statement that touches a
   user-owned table must compare some ``user_id`` column to *the caller's* id.
   This is the floor's own wording, checked on the SQL the handler actually
   built, not on what its source mentions. A second pass lets the caller's own
   scoped lookups succeed, so the handler gets past its ownership check; there
   a statement keyed on request input alone (not on a primary key the caller
   was shown to own) fails. ``…_reaches_every_handler`` fails if a route still
   422s at validation, since the sweep is blind to a handler that never runs.
   (Until M31-S2 the sweep sent ``json={}`` and string path ids, and missed
   the four body-borne R-015 ids and the typed ``/weeks/{week}`` route.)
2. **Unscoped primary-key fetch** (``test_floor1_no_unscoped_session_get``).
   ``session.get(Model, id)`` builds no WHERE clause at all, so no SQL check can
   scope it. Statically, no ``api``/``services`` function may fetch a
   user-owned model by a caller-supplied id this way except the classified
   entries below. **Unscoped query function**
   (``test_floor1_no_unscoped_query_function_outside_classification``): no
   ``services``/``pipeline`` function may query an owned model with no caller
   parameter and no ``user_id`` predicate unless classified. This reaches code
   no route sweep can, such as the worker's ``classify._get_known_courses``.
   **Optional caller** (``test_floor1_caller_parameter_is_never_optional``,
   R-021): nor may one take the caller as an optional parameter, scoped only
   when a caller remembers to pass it.
3. **Behaviour** for each known violation, so the fix is pinned by a test that
   does not care how it was fixed.

``tests/unit/api/test_endpoint_scoping_guard.py`` (the #47/#53 guard) checks the
endpoint layer; layer 2 exists because that guard trusts a ``user_id=`` keyword
at the call site, and ``attach_assessment_document`` takes one and ignores it
for the lookup.
"""

from __future__ import annotations

import ast
import contextlib
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from tests.safety._payload import (
    FOREIGN_ID,
    FOREIGN_INT,
    FOREIGN_UUID,
    model_payload,
    value_for,
)
from tests.safety._source import app_modules, dotted, parse, rel, walk_with_scope
from tests.safety._tenant import (
    UNOWNED_TABLES,
    all_tables,
    bind_values,
    filters_by_id_list,
    filters_on_user,
    is_planted,
    primary_key_values,
    tables_in,
    user_owned_tables,
)

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
#: product disagree and the user has not ruled. An entry that stops crossing
#: users fails as stale, and ``test_floor1_no_cross_user_route_awaits_a_ruling``
#: is red while any entry is open. Empty since the 2026-10-04 rulings.
SWEEP_PENDING_RULING: dict[str, str] = {}

#: Cross-user reads the user ruled acceptable *only* for users who opted in.
#: The sweep cannot judge an opt-in filter (it asks whether ``user_id`` is
#: compared to the caller), so each entry is exempt from the sweep and carries
#: a behavioural pin that evaluates the filter row by row. Not stale-checked:
#: the fixed query may also compare ``user_id`` to the caller (to show the
#: caller their own rank), which makes the sweep call it scoped.
SWEEP_OPT_IN_CROSS_USER = {
    "GET /api/gamification/leaderboard": (
        "ruled 2026-10-04 (R-007): opt-in, hidden by default; floor 1 stands. "
        "Lists only users with user_settings.leaderboard_opt_in = true (plus the "
        "caller). Pinned by test_floor1_leaderboard_lists_only_opted_in_users"
    ),
}

SWEEP_EXEMPT = frozenset(SWEEP_PENDING_RULING) | frozenset(SWEEP_OPT_IN_CROSS_USER)

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
            params[qp.alias] = value_for(qp.field_info.annotation, list(qp.field_info.metadata))
    return params


def _path_value(annotation: object) -> object:
    """A type-valid foreign value: ``week: int`` gets an int, not a string that 422s."""
    if annotation is int:
        return FOREIGN_INT
    if getattr(annotation, "__name__", "") == "UUID":
        return FOREIGN_UUID
    return FOREIGN_ID


def _url(route: APIRoute) -> str:
    types = {p.alias: p.field_info.annotation for p in route.dependant.path_params}
    return re.sub(
        r"\{(\w+)(:\w+)?\}", lambda m: str(_path_value(types.get(m.group(1), str))), route.path
    )


def _json_body(route: APIRoute, method: str) -> object:
    """The route's JSON body built from its own schema, foreign ids in every slot.

    File/form routes keep ``{}``: they 422 before the handler, and are listed in
    ``SWEEP_UNREACHED_BY_DESIGN``.
    """
    from fastapi.params import Body

    params = [b for b in route.dependant.body_params if type(b.field_info) is Body]
    if not params:
        return {} if method in {"POST", "PUT", "PATCH"} else None

    def build(field) -> object:
        annotation = field.field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return model_payload(annotation)
        return value_for(annotation, list(field.field_info.metadata))

    if len(params) == 1 and not getattr(params[0].field_info, "embed", False):
        return build(params[0])
    return {p.alias: build(p) for p in params}


#: Stand-in id for a row the *caller* owns, returned in the owned-parent pass.
OWNED_ROW_ID = "row-owned-by-the-caller"


def _owned_row(caller_id: str) -> MagicMock:
    """A row the caller owns: its own ids are OWNED_ROW_ID, its owner the caller."""
    row = MagicMock()
    for attr in (
        "id",
        "course_id",
        "artifact_id",
        "exam_id",
        "session_id",
        "assessment_id",
    ):
        setattr(row, attr, OWNED_ROW_ID)
    row.user_id = caller_id
    return row


def _owned_result(row: MagicMock) -> MagicMock:
    result = _empty_result()
    result.scalar_one_or_none.return_value = row
    result.scalars.return_value.first.return_value = row
    result.first.return_value = row
    result.one_or_none.return_value = row
    return result


@contextlib.contextmanager
def _no_live_ai():
    """Every ``get_agent`` / ``get_embedding_provider`` binding refuses at once.

    With a body that validates, ``POST /api/settings/test-ai`` and friends reach
    the factory, and on a host with the ``claude`` CLI the default backend
    would make a real provider call from the floor tier.
    """
    import sys

    from app.agents import embeddings, factory
    from app.core.exceptions import AgentError

    def refuse(*_a, **_k):
        raise AgentError("floor-1 sweep: no live AI provider")

    originals = {factory.get_agent, embeddings.get_embedding_provider}
    with contextlib.ExitStack() as stack:
        for name, module in list(sys.modules.items()):
            if not (name == "app" or name.startswith("app.")) or module is None:
                continue
            for attr in ("get_agent", "get_embedding_provider"):
                if getattr(module, attr, None) in originals:
                    stack.enter_context(patch.object(module, attr, refuse))
        yield


async def _run_sweep(async_client, mock_session, caller_id: str, *, owned_parent: bool = False):
    """Call every swept route; return (violations, routes reaching owned tables, statuses).

    Two passes, two questions:

    * ``owned_parent=False`` — the database is empty. Every statement on a
      user-owned table must compare ``user_id`` to the caller.
    * ``owned_parent=True`` — every lookup that *is* scoped to the caller finds
      a row the caller owns (``OWNED_ROW_ID``); everything else is empty. That
      gets a handler past its ownership check (``get_course_by_code(...,
      user_id=)``), to the queries behind it. Those are judged by taint, not by
      table: a statement on an owned table that binds a value the *request*
      supplied (``is_planted``), without binding the caller-owned row's id and
      without filtering on the caller, is keyed on caller input alone. FK
      traversal from the caller's own row (``WHERE course_id = OWNED_ROW_ID``)
      is not flagged.
    """
    from app.api.deps import get_current_user
    from app.config import settings
    from app.core.rate_limit import limiter
    from app.main import app

    owned = user_owned_tables()
    captured: list = []
    fetched: list = []
    row = _owned_row(caller_id)

    def record(statement, *_a, **_k):
        captured.append(statement)
        if owned_parent and filters_on_user(statement, caller_id):
            return _owned_result(row)
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
        _no_live_ai(),
        # Unreachable Redis that refuses at once instead of timing out.
        patch.object(settings, "redis_url", "redis://127.0.0.1:1/0"),
        # ~150 requests from one client address would trip the per-route limits.
        patch.object(limiter, "enabled", False),
        patch("celery.app.task.Task.apply_async", MagicMock()),
        patch("celery.app.task.Task.delay", MagicMock()),
    ):
        for method, path, route in _sweep_routes():
            captured.clear()
            fetched.clear()
            try:
                response = await async_client.request(
                    method,
                    _url(route),
                    params=_required_query_params(route),
                    json=_json_body(route, method),
                    timeout=5,
                )
                statuses[f"{method} {path}"] = _status(response)
            except Exception as exc:  # a handler crash on a mock row is not the subject
                statuses[f"{method} {path}"] = type(exc).__name__
            bad = []
            touched_owned = False
            two_step = f"{method} {path}" in TWO_STEP_SCOPED
            anchored = any(filters_on_user(s, caller_id) for s in captured)
            vetted: set = set()  # request values a caller-scoped PK lookup has proven
            for statement in captured:
                hit = tables_in(statement) & owned
                if not hit:
                    continue
                touched_owned = True
                if filters_on_user(statement, caller_id):
                    vetted |= primary_key_values(statement)
                    continue
                if owned_parent:
                    values = bind_values(statement)
                    unvetted = [v for v in values if is_planted(v) and v not in vetted]
                    if not unvetted or OWNED_ROW_ID in values:
                        continue
                elif two_step and anchored and filters_by_id_list(statement):
                    continue
                flat = " ".join(str(statement).split())
                bad.append(f"{sorted(hit)}: {flat[:220]}")
            for model, ident in fetched:
                table = getattr(model, "__tablename__", "")
                if table in owned:
                    touched_owned = True
                    if owned_parent and (ident == OWNED_ROW_ID or ident in vetted):
                        continue  # FK traversal from a row the caller was shown to own
                    bad.append(f"session.get({model.__name__}, {ident!r}) — no WHERE at all")
            reached += touched_owned
            if bad:
                violations[f"{method} {path}"] = bad
    return violations, reached, statuses


def _status(response) -> object:
    """The status, or ``"rejected"`` for FastAPI's own request-validation 422.

    A 422 a handler raises itself (``detail`` is a string) means the handler ran;
    FastAPI's (``detail`` is a list of field errors) means it never did.
    """
    if response.status_code == 422:
        try:
            if isinstance(response.json().get("detail"), list):
                return "rejected"
        except ValueError:
            pass
    return response.status_code


def _format(violations: dict[str, list[str]]) -> str:
    return "\n".join(f"  {route}\n    " + "\n    ".join(v) for route, v in violations.items())


@pytest.mark.asyncio
async def test_floor1_route_sweep_every_owned_query_filters_on_caller(
    async_client, mock_session, default_test_user
):
    """Every user-owned query a handler issues compares user_id to the caller.

    Each route gets a type-valid request with a foreign id in every path
    parameter and every body field, so handlers whose id arrives in the body
    (``/study/review``) or behind a typed path parameter run instead of 422ing.
    """
    violations, reached, statuses = await _run_sweep(
        async_client, mock_session, default_test_user.id
    )
    unruled = {k: v for k, v in violations.items() if k not in SWEEP_EXEMPT}
    assert not unruled, (
        "Floor 1: route(s) issued a query on a user-owned table without "
        "filtering on the caller's user_id:\n" + _format(unruled)
    )
    stale = sorted(set(SWEEP_PENDING_RULING) - set(violations))
    assert not stale, f"SWEEP_PENDING_RULING entries no longer cross users — remove them: {stale}"
    assert reached >= MIN_ROUTES_WITH_OWNED_QUERIES, (
        f"Sweep reached only {reached} routes that query a user-owned table "
        f"(floor {MIN_ROUTES_WITH_OWNED_QUERIES}). The harness has stopped "
        "exercising handlers; the scoping assertion above is vacuous until fixed.\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(statuses.items()))
    )


@pytest.mark.asyncio
async def test_floor1_route_sweep_owned_parent_never_unlocks_foreign_rows(
    async_client, mock_session, default_test_user
):
    """Past a scoped parent lookup, no query is keyed on request input alone.

    ``GET /courses/{code}/weeks/{n}`` scopes the course to the caller, then
    looked the summary up by ``code`` + ``week`` only. On an empty database the
    handler 404s at the course, so only a pass where the caller's own lookups
    succeed reaches it.
    """
    violations, _reached, statuses = await _run_sweep(
        async_client, mock_session, default_test_user.id, owned_parent=True
    )
    unruled = {k: v for k, v in violations.items() if k not in SWEEP_EXEMPT}
    assert not unruled, (
        "Floor 1: behind a caller-scoped lookup, route(s) queried a user-owned table "
        "keyed on request input with no user_id filter and no caller-owned parent id:\n"
        + _format(unruled)
    )


def test_floor1_payload_builder_plants_type_valid_foreign_values():
    """The request builder satisfies each declared type and still plants foreign values.

    The sweep is only as wide as this builder: a type it cannot satisfy is a
    route whose handler never runs.
    """
    import datetime as dt
    import enum
    import uuid
    from typing import Annotated, Literal

    from pydantic import Field, model_validator

    from tests.safety._payload import FOREIGN_INT, model_payload, value_for
    from tests.safety._tenant import is_planted

    class Colour(enum.Enum):
        RED = "red"

    class Inner(BaseModel):
        exam_id: str

    class Everything(BaseModel):
        course_code: str | None = None
        week: Annotated[int, Field(gt=0, lt=10)]
        big: Annotated[int, Field(ge=100)] = 100
        ratio: Annotated[float, Field(le=1.0)] = 0.5
        colour: Colour = Colour.RED
        mode: Literal["a", "b"] = "a"
        when: dt.datetime | None = None
        day: dt.date | None = None
        at: dt.time | None = None
        ref: uuid.UUID | None = None
        extra: dict = {}
        inner: Inner | None = None
        ids: list[str] = []
        email: Annotated[str, Field(pattern=r"^[^@]+@[^@]+$")] = "x@y"
        code: Annotated[str, Field(min_length=40)] = "x" * 40
        anything: object = None

    body = model_payload(Everything)
    Everything.model_validate(body)
    assert is_planted(body["course_code"]) and is_planted(body["inner"]["exam_id"])
    assert body["ids"] and is_planted(body["ids"][0])
    assert body["week"] == 9 and body["big"] == 100 and body["ratio"] == 1.0
    assert body["email"] == "someone-else@example.com"
    assert value_for(int) == FOREIGN_INT and is_planted(value_for(uuid.UUID))
    assert value_for(Annotated[int, Field(lt=5)]) == 4
    assert value_for(Everything, depth=99) is None
    assert model_payload(Everything) is not model_payload(Everything), "cache must hand out copies"

    class OneOf(BaseModel):
        text: str | None = None
        url: str | None = None

        @model_validator(mode="after")
        def exactly_one(self):
            if (self.text is None) == (self.url is None):
                raise ValueError("text or url, not both")
            return self

    assert model_payload(OneOf) == {"text": value_for(str)}

    class Impossible(BaseModel):
        broken: Annotated[str, Field(pattern=r"^\d{3}$")] | None = None
        required: Annotated[str, Field(pattern=r"^\d{3}$")]

    impossible = model_payload(Impossible)
    assert "broken" not in impossible and "required" in impossible

    class NeverValid(BaseModel):
        a: str | None = None

        @model_validator(mode="after")
        def refuse(self):
            raise ValueError("never")

    assert model_payload(NeverValid) == {"a": value_for(str)}
    assert not is_planted(True) and not is_planted(1.5) and not is_planted("id")


#: Routes the typed sweep still cannot get past validation, each with why.
#: Any other route that 422s is invisible to both passes, which is the gap the
#: M31 gate found; ``test_floor1_route_sweep_reaches_every_handler`` pins it.
SWEEP_UNREACHED_BY_DESIGN = {
    "POST /api/uploads": "multipart file upload; covered by tests/unit/api upload scoping tests",
    "POST /api/uploads/batch": "multipart file upload",
    "POST /api/courseops/documents": "multipart file upload",
    "POST /api/courseops/assessments/{assessment_id}/documents": (
        "multipart file upload; V1 pinned by "
        "test_floor1_cannot_attach_document_to_another_users_assessment"
    ),
}


@pytest.mark.asyncio
async def test_floor1_route_sweep_reaches_every_handler(
    async_client, mock_session, default_test_user
):
    """No swept route is rejected at validation (422) except the listed file routes.

    A 422 means the handler never ran, so the sweep saw no SQL and reported the
    route clean. That is how the first sweep missed four body-borne R-015 ids.
    """
    _violations, _reached, statuses = await _run_sweep(
        async_client, mock_session, default_test_user.id
    )
    unreached = sorted(
        k for k, v in statuses.items() if v == "rejected" and k not in SWEEP_UNREACHED_BY_DESIGN
    )
    assert not unreached, (
        "Floor-1 sweep is blind to these routes: their typed request still fails "
        "validation, so the handler never runs. Teach tests/safety/_payload.py the "
        "missing type, or list the route in SWEEP_UNREACHED_BY_DESIGN with a reason:\n"
        + "\n".join(f"  {k}" for k in unreached)
    )
    stale = sorted(k for k in SWEEP_UNREACHED_BY_DESIGN if statuses.get(k) != "rejected")
    assert not stale, f"SWEEP_UNREACHED_BY_DESIGN routes now reach the handler: {stale}"


def test_floor1_no_cross_user_route_awaits_a_ruling():
    """Every deliberate cross-user read has been ruled on by the user.

    The leaderboard, the only entry, was ruled opt-in on 2026-10-04 and moved
    to ``SWEEP_OPT_IN_CROSS_USER`` with its own behavioural pin. A new entry
    here is a floor question for the user, and the floor is not green while
    one is open.
    """
    assert not SWEEP_PENDING_RULING, "\n".join(
        f"  {k}: {v}" for k, v in SWEEP_PENDING_RULING.items()
    )
    assert not set(SWEEP_PENDING_RULING) & set(SWEEP_OPT_IN_CROSS_USER)


#: The tables a leaderboard row is made of. A query that reads any other
#: column fails as Unreadable rather than being guessed at.
LEADERBOARD_TABLES = ("users", "user_xp", "user_settings")


def _leaderboard_row(user_id: str, *, opted_in: bool | None) -> dict[tuple[str, str], object]:
    """One user's joined row. ``opted_in=None`` means the user has no settings row."""
    from sqlalchemy import Boolean, Integer

    tables = all_tables()
    row: dict[tuple[str, str], object] = {}
    for name in LEADERBOARD_TABLES:
        for column in tables[name].c:
            if isinstance(column.type, Boolean):
                default: object = False
            elif isinstance(column.type, Integer):
                default = 100
            else:
                default = f"{name}.{column.name}:{user_id}"
            row[(name, column.name)] = default
    row[("users", "id")] = user_id
    row[("user_xp", "user_id")] = user_id
    row[("user_settings", "user_id")] = user_id
    row[("user_settings", "leaderboard_opt_in")] = bool(opted_in)
    if opted_in is None:  # no settings row: every user_settings column is NULL
        row = {k: (None if k[0] == "user_settings" else v) for k, v in row.items()}
    return row


@pytest.mark.asyncio
async def test_floor1_leaderboard_lists_only_opted_in_users(
    async_client, mock_session, default_test_user
):
    """GET /leaderboard returns no other user who has not opted in.

    Ruled 2026-10-04 (R-007): the leaderboard is opt-in and hidden by
    default; floor 1 stands. Each statement the route runs on ``user_xp`` is
    evaluated row by row (``_predicate.admits``) against three other users:
    one opted in, one opted out, and one with no settings row at all. Only the
    first may come back, and it must, or "hidden" was implemented as "empty".
    The caller's own row is unconstrained. Green since M31-S2-BACKEND-019 added
    the filter.
    """
    from tests.safety._predicate import Unreadable, admits

    captured: list = []

    def record(statement, *_a, **_k):
        captured.append(statement)
        result = MagicMock()
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.scalar.return_value = None
        return result

    mock_session.execute = AsyncMock(side_effect=record)
    mock_session.scalar = AsyncMock(side_effect=lambda s, *a, **k: record(s).scalar())

    await async_client.get("/api/gamification/leaderboard")

    reads = [s for s in captured if "user_xp" in tables_in(s)]
    assert reads, "control: the leaderboard ran no query on user_xp"

    others = {
        "opted-in": _leaderboard_row("user-opted-in", opted_in=True),
        "opted-out": _leaderboard_row("user-opted-out", opted_in=False),
        "no-settings-row": _leaderboard_row("user-no-settings", opted_in=None),
    }
    try:
        shown = {label: [str(s) for s in reads if admits(s, row)] for label, row in others.items()}
    except Unreadable as exc:
        pytest.fail(
            f"The leaderboard query uses a construct tests/safety/_predicate.py does not "
            f"model ({exc}). Teach the evaluator; do not weaken this pin."
        )
    leaked = {k: v for k, v in shown.items() if k != "opted-in" and v}
    assert not leaked, (
        "Floor 1 VIOLATION: the leaderboard returns users who did not opt in:\n"
        + "\n".join(f"  {k}: {v[0]}" for k, v in leaked.items())
    )
    assert shown["opted-in"], (
        "The leaderboard hides an opted-in user too: the filter is not "
        "leaderboard_opt_in, it is something stricter or broken."
    )


def test_floor1_predicate_evaluator_models_sql_semantics():
    """``_predicate.admits`` keeps exactly the rows Postgres would, or refuses.

    The leaderboard pin is only as good as this evaluator, so its semantics are
    pinned here: three-valued logic (NULL is neither true nor false), outer
    joins that null the unmatched side, IN over lists and subqueries, and a
    loud ``Unreadable`` for anything it does not model.
    """
    import sqlalchemy as sa

    from app.models.user import User
    from app.models.user_settings import UserSettings
    from app.models.user_xp import UserXP
    from tests.safety._predicate import Unreadable, admits, value

    opted, hidden, bare = (
        _leaderboard_row("u-in", opted_in=True),
        _leaderboard_row("u-out", opted_in=False),
        _leaderboard_row("u-none", opted_in=None),
    )
    base = sa.select(UserXP).join(User, UserXP.user_id == User.id)
    outer = base.outerjoin(UserSettings, UserSettings.user_id == UserXP.user_id)
    opt = UserSettings.leaderboard_opt_in

    def keeps(stmt) -> tuple[bool, bool, bool]:
        return admits(stmt, opted), admits(stmt, hidden), admits(stmt, bare)

    assert keeps(base) == (True, True, True)
    assert keeps(outer.where(opt.is_(True))) == (True, False, False)
    assert keeps(outer.where(opt == sa.true())) == (True, False, False)
    assert keeps(outer.where(opt)) == (True, False, False)
    assert keeps(outer.where(~opt)) == (False, True, False)  # NOT NULL is NULL
    assert keeps(outer.where(sa.not_(opt.is_(False)))) == (True, False, True)
    assert keeps(outer.where(opt.is_not(None))) == (True, True, False)
    assert keeps(outer.where(opt != sa.false())) == (True, False, False)
    assert keeps(outer.where(sa.func.coalesce(opt, sa.false()).is_(False))) == (False, True, True)
    assert keeps(outer.where(sa.cast(opt, sa.Boolean).is_(True))) == (True, False, False)
    assert keeps(outer.where(sa.or_(opt.is_(True), UserXP.user_id == "u-out"))) == (
        True,
        True,
        False,
    )
    assert keeps(outer.where(sa.and_(opt.is_(True), UserXP.total_xp >= 100))) == (
        True,
        False,
        False,
    )
    assert keeps(outer.where(sa.or_(UserXP.total_xp > 100, UserXP.total_xp < 100))) == (
        False,
        False,
        False,
    )
    assert keeps(base.where(UserXP.user_id.in_(["u-in", "u-none"]))) == (True, False, True)
    assert keeps(base.where(UserXP.user_id.not_in(["u-in"]))) == (False, True, True)
    sub = sa.select(UserSettings.user_id).where(opt.is_(True))
    assert keeps(base.where(UserXP.user_id.in_(sub))) == (True, False, False)
    assert keeps(base.where(UserXP.user_id.in_(sub.scalar_subquery()))) == (True, False, False)
    gated = base.outerjoin(UserSettings, sa.and_(UserSettings.user_id == UserXP.user_id, opt))
    assert keeps(gated) == (True, True, True)  # an outer ON never filters the left side
    assert keeps(gated.where(UserSettings.user_id.is_not(None))) == (True, False, False)
    inner = base.join(UserSettings, sa.and_(UserSettings.user_id == UserXP.user_id, opt))
    assert keeps(inner) == (True, False, False)
    assert keeps(outer.where(sa.or_(UserXP.total_xp > 100, opt))) == (True, False, False)
    assert keeps(outer.where(sa.not_(sa.or_(UserXP.total_xp > 100, opt)))) == (False, True, False)
    assert keeps(outer.where(UserSettings.user_id.not_in(["u-in"]))) == (False, True, False)
    assert keeps(outer.where(sa.func.coalesce(opt, sa.null()).is_(None))) == (False, False, True)
    assert value(sa.null(), opted) is None
    assert value(sa.literal(3).label("x"), opted) == 3

    for unreadable in (
        base.where(User.email.like("%x%")),
        base.where(sa.func.lower(User.username) == "x"),
        base.where(UserXP.user_id.in_(sa.select(UserSettings.user_id, UserSettings.id))),
        base.where(sa.exists(sa.select(UserSettings.id))),
        base.where(UserXP.total_xp.desc()),
        base.where(sa.column("loose") == 1),
        base.where(sa.table("courses", sa.column("code")).c.code == "x"),
        sa.update(UserXP).values(total_xp=0),
        base.outerjoin(sa.select(UserSettings).subquery(), sa.false()),
    ):
        with pytest.raises(Unreadable):
            admits(unreadable, opted)


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
#:
#: ``_get_course_owned`` left this table in BACKEND-006 (d1276a0): ``user_id`` is
#: now required and the lookup is always a ``select`` joined on the owner.
UNSCOPED_GET_ALLOWED = {
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


# ── layer 2b: functions that query owned rows with no caller to scope by ──
#
# The route sweep reaches only what an HTTP handler reaches, and only against
# empty or caller-owned results. A service or pipeline function that builds a
# query on a user-owned model, takes no caller identity at all, and puts no
# ``user_id`` predicate in the query can only be safe if every caller hands it
# something already proven to be the caller's (or it is deliberately
# cross-user). R-015 had four of these: ``classify._get_known_courses`` sent
# every user's course codes to the AI, ``achievement_service.mark_notified``
# flipped anyone's achievements, ``timed_session_service.generate_timed_plan``
# and ``summary_service.get_summary_for_week`` matched on a course *code*,
# which is unique per user, not globally.
#
# So each such function must be classified below with the reason it is safe.
# A fix that threads the caller through (a ``user_id`` parameter the body uses,
# or a ``Model.user_id`` predicate) takes the function off the list by itself.

#: Statement builders whose first arguments name the model being queried.
QUERY_BUILDERS = frozenset({"select", "update", "delete", "insert", "sa_delete", "sa_update"})

#: Parameter names that carry the caller's identity into a function.
CALLER_PARAMS = frozenset({"user_id", "user", "owner_id", "current_user"})

FUNCTION_SCOPE_SCANNED = ("app/services/", "app/pipeline/")

#: (module, function) -> why a query with no caller in it is safe.
UNSCOPED_FUNCTION_ALLOWED = {
    ("app/pipeline/calendar_task.py", "_sync_all"): (
        "beat task: syncs every user's calendar by design; each sync then runs as its owner"
    ),
    ("app/pipeline/_owner.py", "_row_owner_async"): (
        "worker-only owner lookup (R-022, AI-021): reads LectureArtifact.user_id for the "
        "stage's own artifact id to pick the SSE channel; returns the owner id only, never a "
        "row, and a miss or error fails closed to None (event dropped). Pinned by "
        "test_floor1_owner_routing.py"
    ),
    ("app/services/asset_service.py", "save_flashcards"): (
        "pipeline write path (pipeline/assets.py) with ids the worker resolved from its artifact"
    ),
    ("app/services/asset_service.py", "save_quiz_questions"): ("same as save_flashcards"),
    ("app/services/billing_service.py", "_handle_subscription_update"): (
        "Stripe webhook, signature-verified; the subscription row is found by Stripe's id"
    ),
    ("app/services/billing_service.py", "_handle_subscription_deleted"): (
        "Stripe webhook, signature-verified"
    ),
    ("app/services/courseops_service.py", "backfill_courseops_storage_keys"): (
        "operator backfill (app/cli.py) over every row; not reachable from a request. "
        "Surfaced when the detector stopped counting a selected user_id column (SAFETY-025)"
    ),
    ("app/services/course_service.py", "get_course_weeks"): (
        "FK traversal: api/courses.py passes course.id of a course resolved with user_id"
    ),
    ("app/services/feedback_service.py", "list_feedback"): (
        "admin triage, behind require_role('admin'); cross-user by design"
    ),
    ("app/services/feedback_service.py", "count_by_status"): ("admin triage, as list_feedback"),
    ("app/services/feedback_service.py", "notify_admins"): (
        "reads the admins' Telegram links (User.role == 'admin') to deliver a report; "
        "returns a count, never a row, to the reporter. Surfaced by SAFETY-025's join fix"
    ),
    ("app/services/gcal_service.py", "handle_gcal_webhook"): (
        "Google push webhook: the sync row is found by the channel/resource ids Google holds"
    ),
    ("app/services/index_service.py", "index_artifact_chunks"): (
        "pipeline index stage, with the worker's own artifact id"
    ),
    ("app/services/pipeline_service.py", "get_artifact_pipeline_runs"): (
        "FK traversal: api/uploads.py resolves the artifact with user_id first (comment at "
        "the call site); the owned-parent sweep pins the route"
    ),
    ("app/services/readiness_service.py", "collect_week_stats"): (
        "FK traversal: called with exam.course_id of an exam already resolved for the caller"
    ),
    ("app/services/review_service.py", "create_review_item"): (
        "pipeline write path (classify stage) with the worker's own artifact id"
    ),
    ("app/services/summary_service.py", "get_week_extractions"): (
        "pipeline summarize stage, with the course id of the worker's own artifact"
    ),
    ("app/services/summary_service.py", "get_existing_summary"): (
        "pipeline summarize stage / save_summary, keyed on the artifact's course id"
    ),
    ("app/services/summary_service.py", "snapshot_summary"): (
        "FK traversal: reads the owner of the summary it is handed, to stamp the "
        "summary_versions row; callers hold a summary from the worker's own artifact "
        "(create_or_update_summary) or a target course resolved with user_id (merge_courses)"
    ),
    ("app/services/summary_service.py", "list_course_summaries"): (
        "FK traversal on a course id the caller has already resolved"
    ),
    ("app/services/summary_service.py", "backfill_summary_storage_keys"): (
        "operator backfill script over every row; not reachable from a request"
    ),
    ("app/services/telegram_service.py", "verify_link"): (
        "bot webhook: the link row is found by the one-time token the user was issued"
    ),
    ("app/services/user_service.py", "reset_password_with_token"): (
        "pre-auth: the magic link is found by its hashed one-time token"
    ),
    ("app/services/user_service.py", "verify_email_token"): (
        "pre-auth: the magic link is found by its hashed one-time token"
    ),
    ("app/services/user_service.py", "create_or_link_oauth"): (
        "OAuth callback: the account is found by (provider, provider_user_id) the provider vouched for"
    ),
}


def _model_aliases(tree: ast.Module, owned_models: set[str]) -> dict[str, str]:
    """Local name -> owned model class, through ``import ... as`` anywhere in the module."""
    aliases = {name: name for name in owned_models}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.models"):
            for alias in node.names:
                if alias.name in owned_models:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _base_name(node: ast.AST) -> str:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def _all_model_names() -> set[str]:
    from app.core.database import Base

    _owned_model_names()  # registers every model
    return {mapper.class_.__name__ for mapper in Base.registry.mappers}


def _user_id_predicate(sub: ast.AST, owned: dict[str, str], models: dict[str, str]) -> bool:
    """``Owned.user_id`` compared to a *value*, or ``Owned.user_id.in_(...)``.

    A comparison whose other side is another model's column is a join
    condition (``UserXP.user_id == User.id``), and a bare ``Owned.user_id`` is
    a selected column or an ``ON`` operand: neither filters any row.
    """

    def owned_user_id(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Attribute) and node.attr == "user_id" and _base_name(node) in owned
        )

    def model_column(node: ast.AST) -> bool:
        return isinstance(node, ast.Attribute) and _base_name(node) in models

    if isinstance(sub, ast.Compare):
        operands = [sub.left, *sub.comparators]
        return any(owned_user_id(o) for o in operands) and not all(
            model_column(o) for o in operands
        )
    return (
        isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Attribute)
        and sub.func.attr == "in_"
        and owned_user_id(sub.func.value)
    )


def unscoped_in_tree(
    tree: ast.Module, module: str, owned_models: set[str]
) -> dict[tuple[str, str], list[str]]:
    """The unscoped query functions of one parsed module (see ``unscoped_query_functions``)."""
    found: dict[tuple[str, str], list[str]] = {}
    aliases = _model_aliases(tree, owned_models)
    model_aliases = _model_aliases(tree, _all_model_names())
    for node, scope in walk_with_scope(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        queried: set[str] = set()
        predicate = False
        used_names = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                used_names.add(sub.id)
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id in QUERY_BUILDERS
            ):
                queried |= {aliases[b] for a in sub.args if (b := _base_name(a)) in aliases}
            if _user_id_predicate(sub, aliases, model_aliases):
                predicate = True
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "filter_by"
                and any(k.arg == "user_id" for k in sub.keywords)
            ):
                predicate = True
        if not queried or predicate:
            continue
        args = node.args
        params = {a.arg for a in args.args + args.kwonlyargs + args.posonlyargs}
        if params & CALLER_PARAMS & used_names:
            continue  # takes the caller and uses it; the route tiers judge how
        name = f"{scope}.{node.name}" if scope != "<module>" else node.name
        found[(module, name)] = sorted(queried)
    return found


def unscoped_query_functions() -> dict[tuple[str, str], list[str]]:
    """Functions that query an owned model with no caller param and no user_id predicate."""
    owned_models = _owned_model_names()
    found: dict[tuple[str, str], list[str]] = {}
    for path in app_modules():
        module = rel(path)
        if module.startswith(FUNCTION_SCOPE_SCANNED):
            found |= unscoped_in_tree(parse(path), module, owned_models)
    return found


def test_floor1_no_unscoped_query_function_outside_classification():
    """No service/pipeline function queries owned rows with no caller to scope by.

    Unlike the route sweep, this reaches functions no handler calls with a
    foreign id (``classify._get_known_courses`` runs in the worker and puts
    its result in an AI prompt).
    """
    found = unscoped_query_functions()
    new = {k: v for k, v in found.items() if k not in UNSCOPED_FUNCTION_ALLOWED}
    stale = sorted(set(UNSCOPED_FUNCTION_ALLOWED) - set(found))
    assert not new, (
        "Floor 1: function(s) query a user-owned table with no user_id predicate and no "
        "caller parameter, so nothing ties the rows to the caller:\n"
        + "\n".join(f"  {m}::{f}  queries {models}" for (m, f), models in sorted(new.items()))
        + "\nThread the caller's user_id into the query, or classify the function in "
        "UNSCOPED_FUNCTION_ALLOWED (tests/safety/test_floor1_tenant_isolation.py) with "
        "the reason every caller is safe."
    )
    assert not stale, (
        "UNSCOPED_FUNCTION_ALLOWED entries no longer match an unscoped query function — "
        f"remove them: {stale}"
    )


def test_floor1_unscoped_query_detector_is_not_vacuous():
    """The detector still sees the pipeline's own unscoped worker reads."""
    found = unscoped_query_functions()
    assert ("app/services/summary_service.py", "get_week_extractions") in found
    assert ("app/pipeline/calendar_task.py", "_sync_all") in found


_JOIN_ONLY_SOURCE = """
from sqlalchemy import select
from app.models.course import Course
from app.models.user import User
from app.models.user_xp import UserXP

async def board(session):
    return await session.execute(select(UserXP).join(User, UserXP.user_id == User.id))

async def owner_of(session, course_id):
    return await session.scalar(select(Course.user_id).where(Course.id == course_id))

async def by_owner(session, owner):
    return await session.execute(select(UserXP).where(UserXP.user_id == owner))

async def by_owners(session, owners):
    return await session.execute(select(UserXP).where(UserXP.user_id.in_(owners)))
"""


def test_floor1_unscoped_query_detector_needs_a_predicate_not_a_mention():
    """A join on ``Model.user_id``, or selecting it, is not a ``user_id`` predicate.

    SAFETY-021 blind spot 2: any ``Model.user_id`` attribute in the function
    counted as scoping, so ``select(UserXP).join(User, UserXP.user_id ==
    User.id)`` (the old global leaderboard) and ``select(Course.user_id)``
    (reading an owner, filtering on nothing) were never flagged.
    """
    found = unscoped_in_tree(ast.parse(_JOIN_ONLY_SOURCE), "synthetic.py", _owned_model_names())
    names = {name for _module, name in found}
    assert "by_owner" not in names and "by_owners" not in names, (
        f"control: a real user_id predicate was flagged as unscoped: {sorted(names)}"
    )
    assert {"board", "owner_of"} <= names, (
        "Floor 1 detector blind spot: a join on / select of Model.user_id counted as a "
        f"user_id predicate. Flagged only: {sorted(names)}"
    )


def test_floor1_caller_filter_detector_rejects_widened_predicates():
    """``filters_on_user`` accepts a caller comparison only when it constrains every row.

    SAFETY-021 blind spot 1: ``user_id = :caller OR <anything>`` was read as
    scoped, though it returns every row ``<anything>`` admits. So were
    ``user_id != :caller`` (``NOT (user_id = :caller)``) and ``user_id IN
    (:caller, :victim)``. Each of those must count as unscoped; an OR whose
    every branch is caller-scoped still counts as scoped.
    """
    import sqlalchemy as sa

    from app.models.course import Course

    caller = "caller-0001"
    by_code = Course.code == "CSIT302"
    assert filters_on_user(sa.select(Course).where(Course.user_id == caller, by_code), caller)
    assert filters_on_user(sa.select(Course).where(Course.user_id.in_([caller])), caller), (
        "control: IN (:caller) is scoped"
    )
    assert filters_on_user(
        sa.select(Course).where(
            sa.or_(
                sa.and_(Course.user_id == caller, by_code),
                sa.and_(Course.user_id == caller, Course.archived_at.is_(None)),
            )
        ),
        caller,
    ), "control: an OR whose every branch is caller-scoped is scoped"

    widened = {
        "OR other": sa.select(Course).where(sa.or_(Course.user_id == caller, by_code)),
        "NOT": sa.select(Course).where(sa.not_(Course.user_id == caller)),
        "!=": sa.select(Course).where(Course.user_id != caller),
        "IN with a victim": sa.select(Course).where(Course.user_id.in_([caller, "victim-0002"])),
    }
    accepted = sorted(label for label, stmt in widened.items() if filters_on_user(stmt, caller))
    assert not accepted, f"Floor 1 detector blind spot: read as caller-scoped: {accepted}"


# ── layer 2c: a caller parameter that may be left out (R-021, C6) ──────
#
# Layer 2b accepts any function that takes a caller parameter and uses it. It
# cannot see the shape ``def f(session, ..., user_id: str | None = None)`` with
# ``if user_id is not None: query = query.where(Model.user_id == user_id)``:
# the function is scoped when a route hands it the caller and unscoped when
# anyone else forgets to. The route sweep pins today's route callers; nothing
# pins the next worker, CLI or service caller that omits the argument and gets
# every user's rows. M31's gate re-run found this on the five functions the
# R-015 fix had just scoped (F-4), and on the pre-existing ADR 0004 deletes.
#
# So a ``services``/``pipeline`` function whose caller parameter is used in its
# body must fail closed: the parameter is required (no ``None`` default), and no
# ``user_id`` filter sits behind a ``None``/truthiness check on it. A function
# that genuinely serves an owner-less caller is classified below with the
# reason that caller is safe; a fix that makes the parameter required removes
# the function from the failure list by itself.

#: (module, function) -> why its caller parameter may be omitted.
#:
#: Pipeline stages (C6 ruling, decisions.md 2026-10-08; classified in
#: M32-S1-SAFETY-009). Every stage runs in the worker on an artifact id a
#: scoped route enqueued, loads that one ``lecture_artifacts`` row by its id,
#: and acts for ``artifact.user_id``, a NOT NULL column. Since M32-S1-AI-012
#: the row wins outright: the payload ``user_id`` is read only to log a
#: mismatch, so omitting it (or sending the wrong one) changes nothing.
#: ``classify._get_or_create_course`` is NOT here: AI-012 made its owner
#: required and raises on ``""``, so the detector no longer flags it.
_ROW_OWNER = (
    "stage loads its artifact by id and acts for artifact.user_id (NOT NULL); the "
    "payload user_id only feeds warn_on_owner_mismatch, so None never widens a query"
)
OPTIONAL_CALLER_ALLOWED: dict[tuple[str, str], str] = {
    ("app/pipeline/classify.py", "_classify"): (
        f"{_ROW_OWNER}: known courses, AI credentials, usage, course resolution"
    ),
    ("app/pipeline/extract.py", "_extract"): (
        f"{_ROW_OWNER}; the row's owner is echoed into the next stage's payload"
    ),
    ("app/pipeline/summarize.py", "_summarize"): (
        f"{_ROW_OWNER}: AI credentials and usage (owner_id = artifact.user_id)"
    ),
    ("app/pipeline/index.py", "_index"): (
        f"{_ROW_OWNER}; the row's owner is echoed into the next stage's payload"
    ),
    ("app/pipeline/assets.py", "_generate_assets"): (
        f"{_ROW_OWNER}: AI credentials, usage, refreshed CLI credentials, concepts, notification"
    ),
    ("app/pipeline/concepts_task.py", "_extract_concepts_for_artifact"): (
        f"{_ROW_OWNER} (effective_user_id = artifact.user_id)"
    ),
    ("app/pipeline/concepts_task.py", "extract_concepts"): (
        "Celery task signature: user_id is optional for queued-message back-compat "
        "and is passed straight to _extract_concepts_for_artifact (above); nothing in "
        "app/ enqueues it today (the route extracts inline, scoped)"
    ),
    ("app/pipeline/ingest.py", "_ingest"): (
        "None becomes '' for artifact_service.ingest_file: with an artifact_id it adopts "
        "that one pre-created row (owner from the row, later stages fall back to it); "
        "without one, dedup against owner '' matches nothing and the INSERT fails the "
        "NOT NULL users FK, so an owner-less ingest fails closed"
    ),
    ("app/pipeline/orchestrator.py", "run_pipeline"): (
        "dispatcher, no query: user_id only rides in the chain payload; None ends in "
        "_ingest's fail-closed branch or the adopted row's owner"
    ),
    ("app/pipeline/orchestrator.py", "resume_pipeline"): (
        "dispatcher, no query: user_id only rides in the chain payload; None means each "
        "stage falls back to artifact.user_id"
    ),
}


def _is_none(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _caller_defaults(args: ast.arguments) -> dict[str, ast.AST]:
    """Caller parameter -> its default expression, for the parameters that have one."""
    positional = args.posonlyargs + args.args
    tail = positional[len(positional) - len(args.defaults) :]
    out = {a.arg: d for a, d in zip(tail, args.defaults, strict=True)}
    out |= {a.arg: d for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True) if d}
    return {k: v for k, v in out.items() if k in CALLER_PARAMS}


def _none_check_on(test: ast.AST, params: set[str]) -> bool:
    """``p``, ``not p``, ``p is None``, ``p is not None``, ``p == None`` (also inside and/or)."""
    if isinstance(test, ast.BoolOp):
        return any(_none_check_on(v, params) for v in test.values)
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _none_check_on(test.operand, params)
    if isinstance(test, ast.Name):
        return test.id in params
    if isinstance(test, ast.Compare) and len(test.comparators) == 1:
        sides = [test.left, test.comparators[0]]
        return any(isinstance(s, ast.Name) and s.id in params for s in sides) and any(
            _is_none(s) for s in sides
        )
    return False


def _has_user_id_filter(nodes: list[ast.AST], owned: dict[str, str], models: dict[str, str]):
    for root in nodes:
        for sub in ast.walk(root):
            if _user_id_predicate(sub, owned, models):
                return True
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "filter_by"
                and any(k.arg == "user_id" for k in sub.keywords)
            ):
                return True
    return False


def optional_caller_in_tree(
    tree: ast.Module, module: str, owned_models: set[str]
) -> dict[tuple[str, str], list[str]]:
    """Functions of one parsed module whose caller parameter can be left out."""
    found: dict[tuple[str, str], list[str]] = {}
    aliases = _model_aliases(tree, owned_models)
    model_aliases = _model_aliases(tree, _all_model_names())
    for node, scope in walk_with_scope(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        args = node.args
        params = {a.arg for a in args.args + args.kwonlyargs + args.posonlyargs} & CALLER_PARAMS
        body_names = {
            sub.id for stmt in node.body for sub in ast.walk(stmt) if isinstance(sub, ast.Name)
        }
        used = params & body_names
        if not used:
            continue
        reasons = [
            f"`{p}` defaults to None"
            for p, default in sorted(_caller_defaults(args).items())
            if p in used and _is_none(default)
        ]
        for sub in ast.walk(node):
            if isinstance(sub, ast.If | ast.IfExp) and _none_check_on(sub.test, used):
                branches = (
                    sub.body + sub.orelse if isinstance(sub, ast.If) else [sub.body, sub.orelse]
                )
                if _has_user_id_filter(branches, aliases, model_aliases):
                    reasons.append(f"user_id filter is conditional (line {sub.lineno})")
                    break
        if reasons:
            name = f"{scope}.{node.name}" if scope != "<module>" else node.name
            found[(module, name)] = reasons
    return found


def optional_caller_functions() -> dict[tuple[str, str], list[str]]:
    """Every ``services``/``pipeline`` function that is scoped only if its caller remembers."""
    owned_models = _owned_model_names()
    found: dict[tuple[str, str], list[str]] = {}
    for path in app_modules():
        module = rel(path)
        if module.startswith(FUNCTION_SCOPE_SCANNED):
            found |= optional_caller_in_tree(parse(path), module, owned_models)
    return found


def test_floor1_caller_parameter_is_never_optional():
    """A scoped function fails closed: its caller parameter cannot be omitted.

    R-021 (M31 follow-up F-4, M32 condition C6). Red until
    M32-S1-BACKEND-006 makes the parameter required, or classifies a function
    in ``OPTIONAL_CALLER_ALLOWED`` with the reason its owner-less caller is safe.
    """
    found = optional_caller_functions()
    new = {k: v for k, v in found.items() if k not in OPTIONAL_CALLER_ALLOWED}
    stale = sorted(set(OPTIONAL_CALLER_ALLOWED) - set(found))
    assert not new, (
        f"Floor 1: {len(new)} function(s) are tenant-scoped only when the caller remembers "
        "to pass its identity; a caller that omits it runs unscoped:\n"
        + "\n".join(f"  {m}::{f}  {'; '.join(r)}" for (m, f), r in sorted(new.items()))
        + "\nMake the caller parameter required (no None default, no `if user_id` around "
        "the filter), or classify the function in OPTIONAL_CALLER_ALLOWED "
        "(tests/safety/test_floor1_tenant_isolation.py) with the reason it is safe."
    )
    assert not stale, f"OPTIONAL_CALLER_ALLOWED entries no longer match — remove them: {stale}"


#: The one call a ``_ROW_OWNER`` stage may hand the payload owner to: it logs a
#: disagreement with the row and decides nothing (``app/pipeline/_owner.py``).
_OWNER_MISMATCH_LOGGER = "warn_on_owner_mismatch"


def _owner_mismatch_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and dotted(node.func).split(".")[-1] == (
        _OWNER_MISMATCH_LOGGER
    )


def test_floor1_row_owner_stages_never_use_a_bare_optional_caller():
    """The ``_ROW_OWNER`` classification stays true: those stages act as the row's owner.

    ``OPTIONAL_CALLER_ALLOWED`` is keyed on the function, so on its own it would
    wave through a later edit that hands the possibly-``None`` payload owner to
    a scoped service (``list_courses(session, user_id=user_id)``), or one that
    goes back to preferring the payload (``user_id or artifact.user_id``), which
    lets a mismatched payload spend B's credentials and billing on A's artifact
    and file it under B's course. Since M32-S1-AI-012 the row wins: the payload
    ``user_id`` is read only inside ``warn_on_owner_mismatch(...)``.
    """
    import pathlib

    import app

    root = pathlib.Path(app.__file__).resolve().parent.parent
    entries = [k for k, v in OPTIONAL_CALLER_ALLOWED.items() if v.startswith(_ROW_OWNER)]
    assert len(entries) >= 6, f"control: the _ROW_OWNER entries went missing: {entries}"
    bare: list[str] = []
    for module, name in entries:
        tree = parse(root / module)
        fn = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == name
        )
        inside = {
            id(sub) for node in ast.walk(fn) if _owner_mismatch_call(node) for sub in ast.walk(node)
        }
        bare += [
            f"{module}::{name} line {n.lineno}"
            for stmt in fn.body
            for n in ast.walk(stmt)
            if isinstance(n, ast.Name)
            and n.id == "user_id"
            and isinstance(n.ctx, ast.Load)
            and id(n) not in inside
        ]
    assert not bare, (
        "Floor 1: a pipeline stage classified as acting for the artifact row's owner "
        "reads the optional payload `user_id` outside warn_on_owner_mismatch, so an "
        "omitted caller reaches it as None or a mismatched one overrides the row:\n  "
        + "\n  ".join(bare)
        + "\nUse `artifact.user_id`, or reclassify the stage."
    )


_OPTIONAL_CALLER_SOURCE = """
from sqlalchemy import select
from app.models.course import Course

async def required(session, code, *, user_id):
    return await session.execute(select(Course).where(Course.code == code, Course.user_id == user_id))

async def fail_closed(session, code, user_id):
    if user_id is None:
        raise ValueError("no caller")
    return await session.execute(select(Course).where(Course.user_id == user_id))

async def defaults_none(session, code, user_id=None):
    return await session.execute(select(Course).where(Course.user_id == user_id))

async def kw_defaults_none(session, code, *, user_id: str | None = None):
    return await session.execute(select(Course).where(Course.user_id == user_id))

async def skips_filter(session, code, user_id: str):
    query = select(Course).where(Course.code == code)
    if user_id:
        query = query.where(Course.user_id == user_id)
    return await session.execute(query)

async def forwards_none(session, code, user_id=None):
    return await required(session, code, user_id=user_id)

async def unused(session, code, user_id=None):
    return code
"""


def test_floor1_optional_caller_detector_is_not_vacuous():
    """The R-021 detector flags each fail-open shape and passes the fail-closed ones."""
    found = optional_caller_in_tree(
        ast.parse(_OPTIONAL_CALLER_SOURCE), "synthetic.py", _owned_model_names()
    )
    names = {name for _module, name in found}
    assert not names & {"required", "fail_closed", "unused"}, (
        f"control: a fail-closed or caller-free function was flagged: {sorted(names)}"
    )
    assert {"defaults_none", "kw_defaults_none", "skips_filter", "forwards_none"} <= names, (
        f"Floor 1 detector blind spot: optional caller not flagged. Flagged only: {sorted(names)}"
    )


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
