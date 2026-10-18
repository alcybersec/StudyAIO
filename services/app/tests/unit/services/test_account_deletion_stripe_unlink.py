"""Account deletion unlinks the Stripe customer from webhook rows (never deletes them)."""

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.dml import Delete, Update

from app.services import account_service


def _literal(stmt: object) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _session(customers: list[str | None]) -> AsyncMock:
    session = AsyncMock()
    seen: list[object] = []

    async def execute(stmt, *_a, **_k):
        seen.append(stmt)
        result = MagicMock()
        result.scalars.return_value.all.return_value = customers
        result.rowcount = 3
        return result

    session.execute = AsyncMock(side_effect=execute)
    session.seen = seen
    return session


@pytest.mark.asyncio
async def test_unlink_updates_rows_for_the_users_customers_only() -> None:
    session = _session(["cus_a", None, "cus_b"])

    n = await account_service._unlink_stripe_events(session, "user-1")

    lookup, update = session.seen
    assert "subscriptions.user_id = 'user-1'" in _literal(lookup)  # the user's own customers
    assert isinstance(update, Update) and not isinstance(update, Delete)
    sql = _literal(update)
    assert sql.startswith("UPDATE stripe_webhook_events SET stripe_customer_id=NULL")
    assert "IN ('cus_a', 'cus_b')" in sql
    assert n == 3


@pytest.mark.asyncio
async def test_unlink_without_a_subscription_issues_no_update() -> None:
    session = _session([])

    assert await account_service._unlink_stripe_events(session, "user-1") == 0
    assert len(session.seen) == 1


def test_unlink_runs_before_the_tables_are_deleted() -> None:
    src = inspect.getsource(account_service.delete_user_account)
    assert src.index("_unlink_stripe_events") < src.index("_ordered_tables()")
