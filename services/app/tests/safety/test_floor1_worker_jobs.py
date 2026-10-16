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
  nothing. Since M34-S2-SEC-008 the dedupe and ordering state is the
  ``stripe_webhook_events`` table, not Redis; account deletion nulls its
  customer id and never deletes a row (R4).
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
#
# M34-S2-SEC-008 moved dedupe and ordering from Redis into Postgres
# (``models.stripe-webhook-events v1``): the event id is claimed with an
# insert-or-skip on its unique index, the ordering watermark is read from the
# customer's applied rows under a per-customer advisory lock, and claim and
# effect commit or roll back together. ``_WebhookDb`` models exactly that. The
# ``stripe_webhook_events`` rows live in a ``MiniDB``, so the watermark read is
# answered by evaluating its real WHERE clause and a dropped customer filter
# changes the answer; the claim honours the unique index; ``rollback`` restores
# the rows as they were at the last ``commit``.


def _compiled(statement) -> tuple[str, dict]:
    c = statement.compile(dialect=postgresql.dialect())
    return str(c), dict(c.params)


def _ts(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, tz=UTC)


class _WebhookDb:
    """Two users' subscriptions answered by customer id, plus a modelled event table."""

    def __init__(self) -> None:
        from tests.safety._minidb import MiniDB

        self.subs = {
            "cus_A": MagicMock(user_id="user-a", stripe_subscription_id="sub_A", plan="free"),
            "cus_B": MagicMock(user_id="user-b", stripe_subscription_id="sub_B", plan="pro"),
        }
        self.users = {
            "user-a": MagicMock(id="user-a", tier="free"),
            "user-b": MagicMock(id="user-b", tier="pro"),
        }
        self.events = MiniDB()
        self._committed: list = []
        self.statements: list[tuple[str, dict]] = []
        self.locks: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_on_subscriptions = False
        self.session = AsyncMock()
        self.session.execute.side_effect = self._execute
        self.session.commit.side_effect = self._commit
        self.session.rollback.side_effect = self._rollback

    # ── state ──────────────────────────────────────────────────────────

    def seed(self, event_id: str, customer: str | None, created: int) -> None:
        """A committed, applied event."""
        from app.models.stripe_webhook_event import StripeWebhookEvent

        self.events.add(
            StripeWebhookEvent(
                id=f"row-{event_id}",
                stripe_event_id=event_id,
                event_type="customer.subscription.updated",
                stripe_customer_id=customer,
                stripe_created=_ts(created),
                outcome="applied",
            )
        )
        self._committed = list(self.events.rows["stripe_webhook_events"])

    def event(self, event_id: str):
        rows = self.events.rows["stripe_webhook_events"]
        return next((r for r in rows if r.stripe_event_id == event_id), None)

    async def _commit(self) -> None:
        self.commits += 1
        self._committed = list(self.events.rows["stripe_webhook_events"])

    async def _rollback(self) -> None:
        self.rollbacks += 1
        self.events.rows["stripe_webhook_events"] = list(self._committed)

    # ── statements ─────────────────────────────────────────────────────

    def touched(self, table: str) -> list[tuple[str, dict]]:
        """Statements that read or write ``table``."""
        return [
            (q, p)
            for q, p in self.statements
            if f"FROM {table}" in q or f"UPDATE {table}" in q or f"INTO {table}" in q
        ]

    async def _execute(self, statement, *_a, **_k):
        from sqlalchemy.sql.dml import Insert

        from tests.safety._minidb import Result
        from tests.safety._tenant import tables_in

        sql, params = _compiled(statement)
        self.statements.append((sql, params))
        if "pg_advisory_xact_lock" in sql:
            self.locks.extend(v for v in params.values() if isinstance(v, str))
            return Result([(None,)])
        if "stripe_webhook_events" in tables_in(statement):
            if isinstance(statement, Insert):
                assert "ON CONFLICT (stripe_event_id) DO NOTHING" in sql, sql
                if self.event(params["stripe_event_id"]) is not None:
                    return Result([])
                self.events.execute(statement)
                return Result([(params["id"],)])
            return self.events.execute(statement)
        values = set(params.values())
        result = MagicMock()
        if "FROM subscriptions" in sql:
            if self.fail_on_subscriptions:
                raise RuntimeError("database went away mid-effect")
            hits = [s for c, s in self.subs.items() if c in values]
        elif "FROM users" in sql:
            hits = [u for i, u in self.users.items() if i in values]
        else:
            hits = []
        result.scalar_one_or_none.return_value = hits[0] if len(hits) == 1 else None
        return result


async def _webhook(db: _WebhookDb, event_type: str, obj: dict, **kw) -> None:
    from app.services import billing_service

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
    The claim row records that same customer, and claim and effect commit once.
    """
    db = _WebhookDb()
    plans = {c: s.plan for c, s in db.subs.items()}
    tiers = {i: u.tier for i, u in db.users.items()}
    await _webhook(db, event_type, obj, event_id="evt_1", created=100)

    target = obj["customer"]
    owner = db.subs[target].user_id
    for customer, plan in plans.items():
        if customer != target:
            assert db.subs[customer].plan == plan, f"webhook for {target} changed {customer}"
    for uid, tier in tiers.items():
        if uid != owner:
            assert db.users[uid].tier == tier, f"webhook for {target} changed user {uid}"

    assert db.touched("subscriptions"), "the effect never ran: the pin would be vacuous"
    for sql, params in db.touched("subscriptions"):
        assert "stripe_customer_id" in sql and target in params.values(), sql
    for sql, params in db.touched("users"):
        assert set(params.values()) == {owner}, f"user lookup not keyed on the owner: {sql}"
    assert db.users[owner].tier == ("pro" if event_type.endswith("updated") else "free")

    claim = db.event("evt_1")
    assert claim is not None and claim.stripe_customer_id == target
    assert claim.outcome == "applied"
    assert (db.commits, db.rollbacks) == (1, 0)


async def test_floor1_webhook_replayed_or_stale_event_mutates_nothing():
    """A replayed event id, or an event older than one applied, never reaches a row.

    No statement touches ``subscriptions`` or ``users``. The replay adds no row,
    and the stale event is committed as ``stale`` so its own replay is a no-op.
    """
    db = _WebhookDb()
    db.seed("evt_1", "cus_B", created=5)
    db.seed("evt_0", "cus_B", created=10)
    obj = {"customer": "cus_B", "id": "sub_B", "status": "canceled"}

    await _webhook(db, "customer.subscription.updated", obj, event_id="evt_1", created=5)
    assert len(db.events.rows["stripe_webhook_events"]) == 2
    assert db.event("evt_1").outcome == "applied"

    await _webhook(db, "customer.subscription.updated", obj, event_id="evt_2", created=5)
    assert db.event("evt_2").outcome == "stale"
    assert db.commits == 1, "the stale decision is not committed: Stripe's retry would re-run it"

    await _webhook(db, "customer.subscription.updated", obj, event_id="evt_2", created=5)

    assert db.touched("subscriptions") == [] and db.touched("users") == []
    assert db.subs["cus_B"].plan == "pro"
    assert db.users["user-b"].tier == "pro"


async def test_floor1_webhook_ordering_is_per_customer():
    """Another customer's newer event is not this customer's watermark (R2).

    The watermark read is answered by evaluating its WHERE clause, so dropping
    the customer filter makes this event stale and its owner is never upgraded.
    The advisory lock is the named customer's and is taken before the read.
    """
    db = _WebhookDb()
    db.seed("evt_other", "cus_B", created=500)
    obj = {"customer": "cus_A", "id": "sub_A", "status": "active"}
    await _webhook(db, "customer.subscription.updated", obj, event_id="evt_9", created=100)

    assert db.event("evt_9").outcome == "applied"
    assert db.subs["cus_A"].plan == "pro" and db.users["user-a"].tier == "pro"
    assert db.subs["cus_B"].plan == "pro" and db.users["user-b"].tier == "pro"

    assert db.locks and all("cus_A" in k for k in db.locks), db.locks
    order = [q for q, _p in db.statements]
    lock_at = next(i for i, q in enumerate(order) if "pg_advisory_xact_lock" in q)
    read_at = next(
        i for i, q in enumerate(order) if q.startswith("SELECT") and "stripe_webhook_events" in q
    )
    assert lock_at < read_at, "watermark read before the per-customer lock"


async def test_floor4_webhook_failed_effect_releases_the_claim():
    """If the effect fails, the claim rolls back with it, so Stripe's retry applies."""
    db = _WebhookDb()
    db.fail_on_subscriptions = True
    obj = {"customer": "cus_A", "id": "sub_A", "status": "active"}
    with pytest.raises(RuntimeError):
        await _webhook(db, "customer.subscription.updated", obj, event_id="evt_5", created=100)
    assert db.event("evt_5") is None and db.rollbacks == 1

    db.fail_on_subscriptions = False
    await _webhook(db, "customer.subscription.updated", obj, event_id="evt_5", created=100)
    assert db.event("evt_5").outcome == "applied"
    assert db.users["user-a"].tier == "pro"


async def test_floor1_webhook_old_subscription_delete_keeps_the_current_one():
    """Deleting a customer's superseded subscription does not downgrade them."""
    db = _WebhookDb()
    await _webhook(
        db,
        "customer.subscription.deleted",
        {"customer": "cus_B", "id": "sub_OLD"},
        event_id="evt_3",
        created=100,
    )
    assert db.subs["cus_B"].plan == "pro"
    assert db.users["user-b"].tier == "pro"


# ── account deletion unlinks Stripe events (R4) ─────────────────────────


async def test_floor1_floor4_account_deletion_nulls_stripe_customer_with_update_never_delete():
    """Deleting an account nulls its customer id on webhook rows; no row is deleted.

    Run over ``MiniDB`` with two users' subscriptions and events: only the
    deleted user's customer is unlinked, every event row survives (floor 4,
    ruling 3: kept indefinitely), the other customer's link is untouched
    (floor 1), and the statement that touches ``stripe_webhook_events`` is an
    ``UPDATE``, never a ``DELETE``.
    """
    from sqlalchemy.sql.dml import Delete, Update

    from app.models.stripe_webhook_event import StripeWebhookEvent
    from app.models.subscription import Subscription
    from app.services import account_service
    from tests.safety._minidb import MiniDB, MiniSession
    from tests.safety._tenant import tables_in

    db = MiniDB()
    for uid, cus in (("user-a", "cus_A"), ("user-b", "cus_B")):
        db.add(Subscription(id=f"sub-{uid}", user_id=uid, stripe_customer_id=cus, plan="pro"))
        for n in range(2):
            db.add(
                StripeWebhookEvent(
                    id=f"row-{cus}-{n}",
                    stripe_event_id=f"evt_{cus}_{n}",
                    event_type="customer.subscription.updated",
                    stripe_customer_id=cus,
                    stripe_created=_ts(100 + n),
                    outcome="applied",
                )
            )
    seen: list = []

    class _Spy(MiniSession):
        async def execute(self, statement, *a, **k):
            if "stripe_webhook_events" in tables_in(statement):
                seen.append(statement)
            return await super().execute(statement, *a, **k)

    unlinked = await account_service._unlink_stripe_events(_Spy(db), "user-a")  # noqa: SLF001

    rows = db.rows["stripe_webhook_events"]
    assert len(rows) == 4, "an event row was deleted"
    assert unlinked == 2
    assert {r.id for r in rows if r.stripe_customer_id is None} == {
        "row-cus_A-0",
        "row-cus_A-1",
    }
    assert {r.stripe_customer_id for r in rows if r.id.startswith("row-cus_B")} == {"cus_B"}
    assert {r.stripe_event_id for r in rows} == {
        f"evt_{c}_{n}" for c in ("cus_A", "cus_B") for n in range(2)
    }
    assert seen and all(isinstance(s, Update) for s in seen), seen
    assert not any(isinstance(s, Delete) for s in seen)


def test_floor4_account_deletion_unlinks_stripe_events_before_deleting_subscriptions():
    """``delete_user_account`` unlinks first and never sweeps the event table.

    ``_unlink_stripe_events`` reads the customer ids from ``subscriptions``, so
    it must run before that table's rows go; and ``stripe_webhook_events`` stays
    in ``GLOBAL_TABLES`` so the per-table delete loop skips it.
    """
    import inspect

    from app.services import account_service

    assert "stripe_webhook_events" in account_service.GLOBAL_TABLES
    src = inspect.getsource(account_service.delete_user_account)
    unlink = src.find("_unlink_stripe_events(")
    loop = src.find("for table in reversed(_ordered_tables())")
    assert unlink != -1 and loop != -1 and unlink < loop, "unlink must precede the delete loop"
