"""Floor 1 (and floor 2's no-token rule) for the day-2 study nudge (PROD-03, GL#15).

backend ``ebae1cb`` adds a cross-user selection (``nudge_service.candidates_stmt``),
seeds opt-out notification preferences at every signup path, and puts an
unsubscribe link in every email footer. These pins hold:

* every sub-query of the candidate selection is correlated to the candidate's
  own ``users.id``, as a plain conjunct, so one user's activity or opt-in never
  decides another user's nudge; the selection returns only ids and a flag;
* the selection is reachable only from the worker (``app/pipeline/``,
  ``app/worker.py``), never from a request;
* delivery (inbox, preference lookup, address lookup) is keyed on the
  candidate alone;
* preference seeding writes only the new user's rows and looks up only theirs;
* the footer link is one static URL for everyone: no token, no address, no id.
  A signed one-click link would be a credential in every inbox and log.
"""

from __future__ import annotations

import ast
import inspect
import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql import operators, visitors
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList
from sqlalchemy.sql.selectable import Exists, Select

from tests.safety._source import APP_ROOT, app_modules, parse, rel
from tests.safety._tenant import filters_on_user, tables_in, user_owned_tables

USER_A = "floor1-nudge-user-a"


# ── selection ────────────────────────────────────────────────────────────


def _conjuncts(clause) -> list:
    if clause is None:
        return []
    if isinstance(clause, BooleanClauseList) and clause.operator is operators.and_:
        out = []
        for c in clause.clauses:
            out.extend(_conjuncts(c))
        return out
    return [clause]


def _is_owner_correlation(expr, inner_tables: set[str]) -> bool:
    """``<inner>.user_id = users.id`` (either side), as an equality."""
    if not isinstance(expr, BinaryExpression) or expr.operator is not operators.eq:
        return False
    sides = [expr.left, expr.right]
    names = {
        (getattr(getattr(s, "table", None), "name", None), getattr(s, "name", None)) for s in sides
    }
    has_user = ("users", "id") in names
    has_owner = any(t in inner_tables and c == "user_id" for t, c in names)
    return has_user and has_owner


def _inner_selects(statement) -> list[Select]:
    found = []
    for node in visitors.iterate(statement):
        if isinstance(node, Exists):
            for inner in visitors.iterate(node):
                if isinstance(inner, Select):
                    found.append(inner)
                    break
    return found


def test_floor1_nudge_candidate_subqueries_are_each_correlated_to_the_candidate():
    """Every EXISTS in the selection carries ``<table>.user_id = users.id`` as a conjunct.

    Without it, ``~exists(StudySession)`` is true for nobody once any user has
    studied, and ``exists(opted-in preference)`` lets one user's opt-in nudge
    everyone: another user's rows would decide who gets mail.
    """
    from app.services.nudge_service import candidates_stmt

    statement = candidates_stmt(datetime(2026, 10, 10, 8, 0, tzinfo=UTC))
    inners = _inner_selects(statement)
    assert len(inners) >= 4, (
        f"expected the opt-in/studied/reviewed/uploads sub-queries, got {len(inners)}"
    )
    owned = user_owned_tables()
    for inner in inners:
        inner_tables = {t for t in tables_in(inner) if t != "users"}
        assert inner_tables <= owned, f"unexpected sub-query tables {inner_tables}"
        correlated = [
            c for c in _conjuncts(inner.whereclause) if _is_owner_correlation(c, inner_tables)
        ]
        assert correlated, (
            f"Floor 1: a nudge sub-query on {sorted(inner_tables)} is not correlated to the "
            f"candidate's users.id: {inner.whereclause}"
        )


def test_floor1_nudge_selection_returns_ids_not_other_users_data():
    """The selection's columns are the user id and booleans; no email, zone or content."""
    from app.services.nudge_service import candidates_stmt

    statement = candidates_stmt(datetime(2026, 10, 10, 8, 0, tzinfo=UTC))
    cols = list(statement.selected_columns)
    assert getattr(cols[0], "table", None) is not None and cols[0].table.name == "users"
    assert cols[0].name == "id"
    for col in cols[1:]:
        assert isinstance(col, Exists) or col.type.python_type is bool, f"extra column {col}"


ALLOWED_IMPORTERS = ("app/pipeline/", "app/worker.py", "app/services/nudge_service.py")


def test_floor1_nudge_selection_is_worker_only():
    """Only the worker may run the cross-user selection; a route never can."""
    offenders = []
    for path in app_modules():
        r = rel(path)
        if r.startswith(ALLOWED_IMPORTERS):
            continue
        tree = parse(path)
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names = [f"{mod}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.Attribute) and node.attr in (
                "find_nudge_candidates",
                "candidates_stmt",
            ):
                names = [node.attr]
            if any(
                "nudge_service" in n or n.endswith(("find_nudge_candidates", "candidates_stmt"))
                for n in names
            ):
                offenders.append(f"{r}:{node.lineno}")
    assert not offenders, f"Floor 1: the cross-user nudge selection is reachable from {offenders}"


# ── delivery ─────────────────────────────────────────────────────────────


class _Recorder:
    def __init__(self) -> None:
        self.statements: list = []
        self.added: list = []

    async def execute(self, statement, *a, **k):
        self.statements.append(statement)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.all.return_value = []
        return result

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def refresh(self, *_a, **_k):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("has_uploads", [True, False])
async def test_floor1_nudge_delivery_is_keyed_on_the_candidate_only(has_uploads, monkeypatch):
    """Inbox row, preference lookup and address lookup are all the candidate's."""
    from app.config import settings
    from app.models.notification import Notification
    from app.services import nudge_service

    monkeypatch.setattr(settings, "notifications_enabled", True)
    session = _Recorder()
    pref = MagicMock(channel="email", event_type="study_nudge", enabled=True, user_id=USER_A)

    async def execute(statement, *a, **k):
        session.statements.append(statement)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [pref]
        result.scalar_one_or_none.return_value = "a@floor1.invalid"
        return result

    session.execute = execute
    with patch("app.services.email_service.send_email", new=AsyncMock(return_value=True)):
        await nudge_service.send_study_nudge(session, USER_A, has_uploads)

    inbox = [o for o in session.added if isinstance(o, Notification)]
    assert inbox and all(o.user_id == USER_A for o in inbox), "inbox row not the candidate's"
    owned = user_owned_tables() | {"users"}
    assert session.statements, "delivery ran no query, so this proves nothing"
    for statement in session.statements:
        if not tables_in(statement) & owned:
            continue
        scoped = filters_on_user(statement, USER_A) or _filters_users_id(statement, USER_A)
        assert scoped, f"Floor 1: nudge delivery runs an unscoped statement: {statement}"


def _filters_users_id(statement, user_id: str) -> bool:
    """``users.id = :candidate`` (the address lookup keys on the users PK)."""
    for node in visitors.iterate(statement):
        if (
            isinstance(node, BinaryExpression)
            and node.operator is operators.eq
            and getattr(getattr(node.left, "table", None), "name", None) == "users"
            and getattr(node.left, "name", None) == "id"
            and getattr(node.right, "value", None) == user_id
        ):
            return True
    return False


@pytest.mark.asyncio
async def test_floor1_preference_seeding_writes_and_reads_only_the_new_users_rows():
    """Seeding at signup looks up and creates rows for the new user alone."""
    from app.models.notification_preference import NotificationPreference
    from app.services import notification_service

    session = _Recorder()
    await notification_service.seed_default_preferences(session, USER_A)
    prefs = [o for o in session.added if isinstance(o, NotificationPreference)]
    assert prefs, "seeding created nothing, so this proves nothing"
    assert {p.user_id for p in prefs} == {USER_A}
    assert session.statements and all(filters_on_user(s, USER_A) for s in session.statements)


SIGNUP_PATHS = [
    ("app/services/user_service.py", "register_user"),
    ("app/services/user_service.py", "create_or_link_oauth"),
    ("app/services/admin_service.py", "create_user"),
]


@pytest.mark.parametrize(("path", "function"), SIGNUP_PATHS)
def test_floor1_signup_seeds_preferences_for_the_user_just_created(path, function):
    """Each signup path seeds with ``user.id`` of the row it created, never a request value."""
    tree = parse(APP_ROOT.parent / path)
    fn = next(
        n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == function
    )
    calls = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "seed_default_preferences"
    ]
    assert calls, f"{path}:{function} no longer seeds preferences"
    for call in calls:
        owner = ast.unparse(call.args[1]) if len(call.args) > 1 else ""
        assert owner == "user.id", f"{path}:{function} seeds preferences for {owner!r}"


# ── course quota at classify (GL#19, ai AI-029 447efb4) ───────────────────


@pytest.mark.asyncio
async def test_floor1_course_quota_reads_only_the_row_owners_tier_and_count():
    """A new course is gated on the owner's own tier and course count.

    ``users`` is a catalogue table to the sweep, so a tier read on another
    user (``select(User.tier).limit(1)``) would pass every other pin while
    pricing A's upload on B's plan. Nothing is deleted on refusal.
    """
    from app.core.exceptions import QuotaExceededError
    from app.pipeline import classify

    session = _Recorder()
    deleted = AsyncMock()
    session.delete = deleted
    check = AsyncMock(side_effect=QuotaExceededError("courses", 3, "plan"))
    with patch.object(classify, "check_course_quota", check):
        with pytest.raises(QuotaExceededError):
            await classify._get_or_create_course(session, "NEW101", user_id=USER_A)

    assert check.await_args.args[1] == USER_A, "course quota checked for someone else"
    tier_reads = [s for s in session.statements if tables_in(s) == {"users"}]
    assert tier_reads, "no tier lookup ran, so this proves nothing"
    for statement in tier_reads:
        assert _filters_users_id(statement, USER_A), (
            f"Floor 1: the course-quota tier is read from another user's row: {statement}"
        )
    for statement in session.statements:
        if "courses" in tables_in(statement):
            assert filters_on_user(statement, USER_A), f"unscoped course lookup: {statement}"
    assert session.added == [] and deleted.await_count == 0, "a refused course wrote or deleted"


# ── unsubscribe link ─────────────────────────────────────────────────────

EMAIL_SENTINEL = "floor2-nudge-recipient@floor2.invalid"
TOKEN_SENTINEL = "floor2-nudge-token-91c2"
_UNSUB = re.compile(r'<a href="([^"]*)">\s*Unsubscribe', re.IGNORECASE)


def _sender_args(fn) -> dict:
    out = {}
    for name, param in inspect.signature(fn).parameters.items():
        if name == "to_email":
            out[name] = EMAIL_SENTINEL
        elif param.annotation in (int, "int"):
            out[name] = 3
        elif param.default is not inspect.Parameter.empty and not isinstance(param.default, str):
            continue
        else:
            out[name] = f"https://app.invalid/x?token={TOKEN_SENTINEL}&email={EMAIL_SENTINEL}"
    return out


def _senders() -> list[str]:
    from app.services import email_service

    return sorted(
        n
        for n, f in vars(email_service).items()
        if n.startswith("send_")
        and n not in ("send_email", "send_templated_email")
        and inspect.iscoroutinefunction(f)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("sender", _senders())
async def test_floor2_email_unsubscribe_link_is_static_and_carries_no_token_or_pii(
    sender, monkeypatch
):
    """The footer link is the same static settings URL for every recipient."""
    from app.config import settings
    from app.services import email_service

    monkeypatch.setattr(settings, "app_base_url", "https://studyaio.invalid/")
    sent = AsyncMock(return_value=True)
    with patch.object(email_service, "send_email", new=sent):
        fn = getattr(email_service, sender)
        await fn(**_sender_args(fn))
    assert sent.await_args, f"{sender} sent nothing"
    html = (
        sent.await_args.args[2]
        if len(sent.await_args.args) > 2
        else sent.await_args.kwargs["html_body"]
    )
    links = _UNSUB.findall(html)
    assert links, f"{sender}: the email has no unsubscribe link"
    for link in links:
        assert link == "https://studyaio.invalid/settings/notifications", (
            f"Floor 2: {sender}'s unsubscribe link is {link!r}; it must be one static URL "
            "with no token, address or id"
        )
