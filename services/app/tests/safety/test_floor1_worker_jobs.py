"""Floor 1 / floor 4 guards for cross-user worker jobs and the Stripe webhook.

M32-S4-SAFETY-027. Two pieces of wave-2 code read every user's rows on purpose:

* ``app.pipeline.recovery`` (TECH-04, GL#22): a beat job that requeues
  artifacts stuck in an in-progress state, across all users. It is classified
  in ``UNSCOPED_FUNCTION_ALLOWED``; these tests pin the three conditions that
  classification rests on: no request path reaches it, each requeue runs as
  that artifact's own owner, and it never deletes anything (floor 4).
* ``billing_service.handle_webhook_event`` (BILL-01, GL#21): a signature-verified
  Stripe webhook that finds the subscription by Stripe's customer id. These
  tests pin that the mutation lands only on the row of the customer named in the
  event and on that row's own user, and that a replayed or stale event mutates
  nothing.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from tests.safety._source import app_modules, docstring_nodes, dotted, parse, rel

# ── stuck-artifact recovery ────────────────────────────────────────────

RECOVERY_MODULE = "app.pipeline.recovery"
RECOVERY_NAMES = {"_recover", "recover_stuck_artifacts"}
#: Where the recovery job may be named: itself, and the Celery app that
#: registers it (include list + beat schedule).
RECOVERY_REFERENCE_ALLOWED = {"app/pipeline/recovery.py", "app/worker.py"}

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def _recovery_references() -> set[tuple[str, int]]:
    """Every import of, call to, or task-name string for the recovery job."""
    found: set[tuple[str, int]] = set()
    for path in app_modules():
        tree = parse(path)
        docs = docstring_nodes(tree)
        for node in ast.walk(tree):
            hit = False
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                hit = mod == RECOVERY_MODULE or (
                    mod == "app.pipeline" and any(a.name == "recovery" for a in node.names)
                )
            elif isinstance(node, ast.Import):
                hit = any(a.name == RECOVERY_MODULE for a in node.names)
            elif isinstance(node, ast.Call):
                hit = dotted(node.func).split(".")[-1] in RECOVERY_NAMES
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
            ):
                hit = RECOVERY_MODULE in node.value
            if hit:
                found.add((rel(path), getattr(node, "lineno", 0)))
    return found


def test_floor1_recovery_job_is_worker_only():
    """No module but the job itself and the Celery app names the recovery job.

    It reads every user's in-progress artifacts; reachable from a request it
    would let a caller requeue (and, after three tries, fail) another user's
    upload. A ``send_task("app.pipeline.recovery...")`` from a router counts.
    """
    refs = _recovery_references()
    assert any(m == "app/worker.py" for m, _ in refs), (
        "detector found no reference from app/worker.py — it has gone blind"
    )
    outside = sorted(r for r in refs if r[0] not in RECOVERY_REFERENCE_ALLOWED)
    assert not outside, f"recovery job referenced outside the worker: {outside}"


def _artifact(art_id: str, owner: str, status: str = "summarizing") -> MagicMock:
    art = MagicMock()
    art.id = art_id
    art.user_id = owner
    art.status = status
    art.updated_at = NOW - timedelta(hours=3)
    return art


def _recovery_session(artifacts: list[MagicMock], attempts: list[int]) -> AsyncMock:
    rows = MagicMock()
    rows.scalars.return_value.all.return_value = artifacts
    counts = []
    for n in attempts:
        r = MagicMock()
        r.scalar_one.return_value = n
        counts.append(r)
    session = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.execute.side_effect = [rows, *counts]
    return session


async def _run_recovery(session: AsyncMock) -> MagicMock:
    from app.pipeline import recovery

    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    factory.return_value.__aexit__.return_value = False
    with (
        patch.object(recovery, "async_session_factory", factory),
        patch("app.pipeline.orchestrator.resume_pipeline") as resume,
    ):
        await recovery._recover(now=NOW)
    return resume


async def test_floor1_recovery_requeues_each_artifact_as_its_own_owner():
    """Two users' stuck artifacts in one batch: each resumes under its row owner.

    The batch is cross-user by design, so the only thing tying a requeued chain
    to a tenant is the ``user_id`` handed to ``resume_pipeline``. A loop that
    reused one owner (or passed none) would run B's artifact with A's
    credentials and billing.
    """
    a = _artifact("art-a", "user-a")
    b = _artifact("art-b", "user-b", status="indexing")
    resume = await _run_recovery(_recovery_session([a, b], [0, 1]))

    calls = {c.args[0]: c.kwargs.get("user_id") for c in resume.call_args_list}
    assert calls == {"art-a": "user-a", "art-b": "user-b"}, (
        f"recovery resumed an artifact as someone other than its owner: {calls}"
    )


async def test_floor4_recovery_never_deletes():
    """Requeue or give-up: recovery writes run rows and a status, never a delete.

    Giving up marks the artifact ``failed`` and leaves its upload, extraction and
    any summary in place, so a later retry can still use them.
    """
    from sqlalchemy.sql.dml import Delete

    given_up = _artifact("art-a", "user-a")
    requeued = _artifact("art-b", "user-b")
    session = _recovery_session([given_up, requeued], [3, 0])
    await _run_recovery(session)

    session.delete.assert_not_called()
    deletes = [c for c in session.execute.call_args_list if isinstance(c.args[0], Delete)]
    assert not deletes, f"recovery issued a DELETE: {deletes}"
    assert given_up.status == "failed"

    tree = parse(next(p for p in app_modules() if rel(p) == "app/pipeline/recovery.py"))
    deleting = sorted(
        dotted(n.func)
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and dotted(n.func).split(".")[-1] in {"delete", "remove", "unlink", "rmtree", "delete_file"}
    )
    assert not deleting, f"recovery calls a delete: {deleting}"


# ── Stripe webhook ─────────────────────────────────────────────────────


def _compiled(statement) -> tuple[str, dict]:
    c = statement.compile(dialect=postgresql.dialect())
    return str(c), dict(c.params)


class _WebhookDb:
    """Session holding two users' subscriptions, answering by customer id."""

    def __init__(self) -> None:
        self.subs = {
            "cus_A": MagicMock(user_id="user-a", stripe_subscription_id="sub_A", plan="free"),
            "cus_B": MagicMock(user_id="user-b", stripe_subscription_id="sub_B", plan="pro"),
        }
        self.users = {
            "user-a": MagicMock(id="user-a", tier="free"),
            "user-b": MagicMock(id="user-b", tier="pro"),
        }
        self.statements: list[tuple[str, dict]] = []
        self.session = AsyncMock()
        self.session.execute.side_effect = self._execute

    async def _execute(self, statement, *_a, **_k):
        sql, params = _compiled(statement)
        self.statements.append((sql, params))
        values = set(params.values())
        result = MagicMock()
        if "FROM subscriptions" in sql:
            hits = [s for c, s in self.subs.items() if c in values]
        elif "FROM users" in sql:
            hits = [u for i, u in self.users.items() if i in values]
        else:
            hits = []
        result.scalar_one_or_none.return_value = hits[0] if len(hits) == 1 else None
        return result


def _redis(*, fresh: bool = True, last_created: int | None = None) -> MagicMock:
    client = MagicMock()
    client.set = AsyncMock(return_value=True if fresh else None)
    client.get = AsyncMock(return_value=None if last_created is None else str(last_created))
    client.delete = AsyncMock()
    return client


async def _webhook(db: _WebhookDb, event_type: str, obj: dict, client: MagicMock, **kw):
    from app.core import redis as redis_mod
    from app.services import billing_service

    with patch.object(redis_mod, "redis_client", client):
        await billing_service.handle_webhook_event(db.session, event_type, {"object": obj}, **kw)


@pytest.mark.parametrize(
    ("event_type", "obj"),
    [
        (
            "customer.subscription.updated",
            {"customer": "cus_A", "id": "sub_A", "status": "active"},
        ),
        ("customer.subscription.deleted", {"customer": "cus_B", "id": "sub_B"}),
    ],
)
async def test_floor1_webhook_mutates_only_the_named_customers_row(event_type, obj):
    """A subscription event changes the named customer's row and its owner only.

    Every lookup is keyed on a value from the signed event (the customer id) or
    on the ``user_id`` of the row that lookup returned, never on anything else.
    """
    db = _WebhookDb()
    plans = {c: s.plan for c, s in db.subs.items()}
    tiers = {i: u.tier for i, u in db.users.items()}
    await _webhook(db, event_type, obj, _redis(), event_id="evt_1", created=100)

    target = obj["customer"]
    owner = db.subs[target].user_id
    for customer, plan in plans.items():
        if customer != target:
            assert db.subs[customer].plan == plan, f"webhook for {target} changed {customer}"
    for uid, tier in tiers.items():
        if uid != owner:
            assert db.users[uid].tier == tier, f"webhook for {target} changed user {uid}"

    for sql, params in db.statements:
        if "FROM subscriptions" in sql:
            assert "stripe_customer_id" in sql and target in params.values(), sql
        if "FROM users" in sql:
            assert set(params.values()) == {owner}, f"user lookup not keyed on the owner: {sql}"
    assert db.users[owner].tier == ("pro" if event_type.endswith("updated") else "free")


async def test_floor1_webhook_replayed_or_stale_event_mutates_nothing():
    """A replayed event id, or an event older than the last applied, runs no query."""
    db = _WebhookDb()
    obj = {"customer": "cus_B", "id": "sub_B", "status": "canceled"}
    await _webhook(
        db, "customer.subscription.updated", obj, _redis(fresh=False), event_id="evt_1", created=5
    )
    await _webhook(
        db,
        "customer.subscription.updated",
        obj,
        _redis(last_created=10),
        event_id="evt_2",
        created=5,
    )
    assert db.statements == []
    assert db.subs["cus_B"].plan == "pro"


async def test_floor1_webhook_old_subscription_delete_keeps_the_current_one():
    """Deleting a customer's superseded subscription does not downgrade them."""
    db = _WebhookDb()
    await _webhook(
        db,
        "customer.subscription.deleted",
        {"customer": "cus_B", "id": "sub_OLD"},
        _redis(),
        event_id="evt_3",
        created=100,
    )
    assert db.subs["cus_B"].plan == "pro"
    assert db.users["user-b"].tier == "pro"
