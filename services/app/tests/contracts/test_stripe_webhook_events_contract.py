"""Contract test for `models.stripe-webhook-events v1` (docs/CONTRACTS.md, M34-S2-SEC-008).

Stripe webhook dedupe and ordering state moves from Redis to Postgres. Pins:

1. ``stripe_webhook_events`` matches the entry's column table, is unique on
   ``stripe_event_id`` (the claim the service inserts against) and indexed on
   ``(stripe_customer_id, stripe_created)`` (the ordering watermark read).
2. It carries no ``user_id`` and no payload column: Stripe's ids and our
   decision only.
3. ``billing_service`` no longer touches Redis (no import of ``app.core.redis``
   or ``redis``, no ``stripe:event:`` / ``stripe:last_created:`` key).
4. ``handle_webhook_event`` keeps its signature. **Green today.**
5. Retention is indefinite by decision (user, 2026-10-16): the entry says so,
   and nothing under ``app/`` or ``alembic/versions`` deletes from the table
   outside a ``downgrade``. **Green today**, and must stay green once the model
   lands.

6. R2 (safety review, ``docs/gates/M34/contracts-safety.md``): for an event
   with a customer, a per-customer lock (``pg_advisory_xact_lock`` naming the
   customer) is taken before the watermark read; an event with no customer
   reads no watermark and is applied.
7. R4: account deletion nulls ``stripe_customer_id`` on the deleted customer's
   rows with an ``UPDATE``, and the table is listed in ``GLOBAL_TABLES``.

The behaviour (replay, stale, concurrent duplicate, concurrent different
events, failure rollback) is listed in the entry for ``backend`` unit and
``qa`` integration tests; it needs a real transaction and cannot be pinned
here. Items 6 and 7 pin the statement order and shape only.

Red until ``data`` lands the model and migration and ``backend`` the service
change (M34-S2-SEC-008).
"""

import ast
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import DateTime, String
from sqlalchemy.dialects import postgresql

from tests.contracts._weakspot_docs import APP_ROOT, contract_section, table_rows

HEADING = "### models.stripe-webhook-events v1"
TABLE = "stripe_webhook_events"


@pytest.fixture(scope="module")
def table():
    import app.models  # noqa: F401  (registers every model on the metadata)
    from app.core.database import Base

    found = Base.metadata.tables.get(TABLE)
    assert found is not None, f"{TABLE} not on the metadata yet (`data`)"
    return found


@pytest.fixture(scope="module")
def rows() -> list[list[str]]:
    found = table_rows(contract_section(HEADING), "Table")
    assert len(found) == 5, f"{HEADING} lists {len(found)} columns; expected 5"
    return found


def _type_matches(column, spec: str) -> bool:
    spec = spec.strip("`")
    if spec.startswith("String("):
        return isinstance(column.type, String) and column.type.length == int(spec[7:-1])
    if spec == "DateTime(timezone=True)":
        return isinstance(column.type, DateTime) and column.type.timezone is True
    raise AssertionError(f"unrecognised type spec in {HEADING}: {spec!r}")


def test_columns_match_the_entry(table, rows):
    problems = []
    for name, column, type_spec, null, _notes in rows:
        assert name.strip("`") == TABLE
        col = table.columns.get(column.strip("`"))
        if col is None:
            problems.append(f"{column}: missing")
            continue
        if not _type_matches(col, type_spec):
            problems.append(f"{column}: {col.type!r} is not {type_spec}")
        if col.nullable != (null == "yes"):
            problems.append(f"{column}: nullable={col.nullable}, entry says {null!r}")
    for name in ("id", "created_at"):
        if name not in table.columns:
            problems.append(f"{name}: missing")
    assert not problems, f"{HEADING} disagrees with the model:\n" + "\n".join(problems)


def test_event_id_is_unique(table):
    unique = [
        {c.name for c in con.columns}
        for con in table.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    unique += [{c.name for c in ix.columns} for ix in table.indexes if ix.unique]
    if table.columns["stripe_event_id"].unique:
        unique.append({"stripe_event_id"})
    assert {"stripe_event_id"} in unique, "stripe_event_id must be unique: the claim relies on it"


def test_ordering_index(table):
    cols = [[c.name for c in ix.columns] for ix in table.indexes]
    assert ["stripe_customer_id", "stripe_created"] in cols, cols


def test_no_user_id_and_no_payload(table):
    names = set(table.columns.keys())
    assert "user_id" not in names
    assert not names & {"payload", "data", "body", "raw", "email"}, names
    assert names <= {
        "id",
        "stripe_event_id",
        "event_type",
        "stripe_customer_id",
        "stripe_created",
        "outcome",
        "created_at",
    }, f"columns beyond the entry: {sorted(names)}"


def _billing_tree() -> ast.Module:
    path = APP_ROOT / "app" / "services" / "billing_service.py"
    return ast.parse(path.read_text(encoding="utf-8"))


def test_billing_service_does_not_touch_redis():
    tree = _billing_tree()
    problems = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (
                node.module == "app.core.redis"
                or node.module.startswith("redis")
                or (node.module == "app.core" and any(a.name == "redis" for a in node.names))
            )
        ):
            problems.append(f"line {node.lineno}: from {node.module} import ...")
        if isinstance(node, ast.Import) and any(
            a.name.split(".")[0] == "redis" for a in node.names
        ):
            problems.append(f"line {node.lineno}: import redis")
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and (node.value.startswith(("stripe:event:", "stripe:last_created:")))
        ):
            problems.append(f"line {node.lineno}: Redis key {node.value!r}")
        if isinstance(node, ast.JoinedStr):
            text = ast.unparse(node)
            if "stripe:event:" in text or "stripe:last_created:" in text:
                problems.append(f"line {node.lineno}: Redis key {text}")
    assert not problems, "billing_service still uses Redis for webhook state:\n" + "\n".join(
        problems
    )


def test_handle_webhook_event_signature_is_unchanged():
    from app.services import billing_service

    sig = inspect.signature(billing_service.handle_webhook_event)
    assert list(sig.parameters) == ["session", "event_type", "data", "event_id", "created"]
    assert sig.parameters["event_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["created"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["event_id"].default is None
    assert sig.parameters["created"].default is None


def test_entry_keeps_rows_indefinitely():
    flat = " ".join(contract_section(HEADING).split())
    assert "kept indefinitely, by decision" in flat
    assert "No beat task, CLI command or migration deletes rows from this table" in flat


def _deletes_from_the_table(source: str) -> bool:
    compact = " ".join(source.lower().split())
    return any(
        needle in compact
        for needle in (f"delete from {TABLE}", "delete(stripewebhookevent", f"delete({TABLE}")
    )


def test_nothing_prunes_the_table():
    offenders = []
    for path in sorted((APP_ROOT / "app").rglob("*.py")):
        if _deletes_from_the_table(path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(APP_ROOT).as_posix())
    for path in sorted((APP_ROOT / "alembic" / "versions").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if (
                isinstance(node, ast.FunctionDef)
                and node.name != "downgrade"
                and _deletes_from_the_table(ast.unparse(node))
            ):
                offenders.append(f"{path.relative_to(APP_ROOT).as_posix()}:{node.name}")
    assert not offenders, f"{TABLE} is kept indefinitely; these delete from it: {offenders}"


# --- 6. R2: lock before the watermark; no customer, no ordering ------------------

CUSTOMER = "cus_contract0001"


def _compiled(stmt, params) -> tuple[str, list[object]]:
    compiled = stmt.compile(dialect=postgresql.dialect())
    values = list(compiled.params.values())
    if isinstance(params, dict):
        values += list(params.values())
    return " ".join(str(compiled).split()), values


def _webhook_session():
    """Records every statement; the claim INSERT succeeds, every read finds nothing."""
    seen: list[tuple[str, list[object]]] = []

    def _result(stmt, params) -> MagicMock:
        sql, values = _compiled(stmt, params)
        seen.append((sql, values))
        result = MagicMock()
        claimed = "claim-0001" if sql.upper().startswith("INSERT") else None
        for name in ("scalar", "scalar_one_or_none", "first", "one_or_none"):
            getattr(result, name).return_value = claimed
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalars.return_value.first.return_value = None
        result.rowcount = 1
        return result

    async def execute(stmt, params=None, *_args, **_kwargs):
        return _result(stmt, params)

    async def scalar(stmt, params=None, *_args, **_kwargs):
        return _result(stmt, params).scalar()

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute)
    session.scalar = AsyncMock(side_effect=scalar)
    return session, seen


def _is_lock(sql: str, values: list[object]) -> bool:
    return "pg_advisory_xact_lock" in sql and any(CUSTOMER in str(v) for v in values)


def _is_watermark_read(sql: str) -> bool:
    return sql.upper().startswith("SELECT") and TABLE in sql and "stripe_customer_id" in sql


async def _deliver(obj: dict) -> tuple[list[tuple[str, list[object]]], AsyncMock]:
    from app.services import billing_service

    session, seen = _webhook_session()
    # `app.core.redis` is patched only so that today's Redis-backed service stays
    # hermetic while this test is red; the entry removes Redis from the path.
    with (
        patch("app.core.redis.redis_client", new=AsyncMock()),
        patch.object(billing_service, "_handle_subscription_update", new=AsyncMock()) as apply,
    ):
        await billing_service.handle_webhook_event(
            session,
            "customer.subscription.updated",
            {"object": obj},
            event_id="evt_contract0001",
            created=1_760_000_000,
        )
    return seen, apply


async def test_customer_lock_is_taken_before_the_watermark_read():
    seen, apply = await _deliver({"id": "sub_contract0001", "customer": CUSTOMER})

    locks = [i for i, (sql, values) in enumerate(seen) if _is_lock(sql, values)]
    reads = [i for i, (sql, _v) in enumerate(seen) if _is_watermark_read(sql)]
    assert locks, "no pg_advisory_xact_lock on the customer (R2)"
    assert reads, "no watermark read on stripe_webhook_events"
    assert locks[0] < reads[0], "the watermark is read before the customer lock is taken (R2)"
    apply.assert_awaited_once()


async def test_event_without_a_customer_skips_ordering_and_applies():
    seen, apply = await _deliver({"id": "sub_contract0002"})

    reads = [sql for sql, _v in seen if _is_watermark_read(sql)]
    assert not reads, f"an event with no customer was ordered against other rows (R2): {reads}"
    assert not any("pg_advisory_xact_lock" in sql for sql, _v in seen)
    apply.assert_awaited_once()


# --- 7. R4: account deletion unlinks the customer ---------------------------------


def test_entry_states_the_deletion_update():
    flat = " ".join(contract_section(HEADING).split())
    assert "sets `stripe_customer_id = NULL` on every `stripe_webhook_events` row" in flat
    assert "(an `UPDATE`, never a `DELETE`)" in flat


def test_account_deletion_nulls_the_customer_id_and_lists_the_table():
    from app.services import account_service

    assert TABLE in account_service.GLOBAL_TABLES, f"{TABLE} must be listed in GLOBAL_TABLES"
    tree = ast.parse(inspect.getsource(account_service))
    helpers = {
        n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    delete_fn = helpers["delete_user_account"]
    called = {
        n.func.id
        for n in ast.walk(delete_fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    source = "\n".join(
        ast.unparse(helpers[name]) for name in {"delete_user_account", *called} if name in helpers
    )
    assert TABLE in source or "StripeWebhookEvent" in source, (
        f"delete_user_account does not touch {TABLE} (R4, `backend`)"
    )
    assert "update(" in source and "stripe_customer_id" in source, (
        f"delete_user_account must UPDATE {TABLE}.stripe_customer_id to NULL (R4)"
    )
