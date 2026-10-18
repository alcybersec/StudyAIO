"""Stripe webhook dedupe and ordering on a real Postgres (`models.stripe-webhook-events v1`).

Each delivery gets its own committed session, as each HTTP request does, so the
unique index and the per-customer advisory lock are really contended. The unit
tests prove the statement shapes; only this proves two simultaneous deliveries
apply once and the older of two same-customer events cannot undo the newer.
"""

import asyncio
import secrets
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text

from app.core.database import async_session_factory
from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.subscription import Subscription
from app.models.user import User
from app.services import account_service, billing_service

UPDATED = "customer.subscription.updated"
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def world(_run_migrations):
    """A committed user and subscription; everything removed afterwards."""
    tag = secrets.token_hex(5)
    now = datetime.now(UTC)
    ids = {"user": f"{tag}-user", "customer": f"cus_{tag}", "tag": tag}
    async with async_session_factory() as s:
        s.add(
            User(
                id=ids["user"],
                email=f"{tag}@stripe.test",
                username=f"{tag}_u",
                hashed_password="x",
                created_at=now,
                updated_at=now,
            )
        )
        await s.flush()
        s.add(
            Subscription(
                user_id=ids["user"],
                stripe_customer_id=ids["customer"],
                stripe_subscription_id=f"sub_{tag}",
                plan="free",
                status="inactive",
            )
        )
        await s.commit()
    yield ids
    async with async_session_factory() as s:
        await s.execute(
            delete(StripeWebhookEvent).where(StripeWebhookEvent.stripe_event_id.like(f"{tag}-%"))
        )
        await s.execute(delete(Subscription).where(Subscription.user_id == ids["user"]))
        await s.execute(delete(User).where(User.id == ids["user"]))
        await s.commit()


async def _deliver(world, event_id, status, created, *, customer="default"):
    obj = {
        "id": f"sub_{world['tag']}",
        "customer": world["customer"] if customer == "default" else customer,
        "status": status,
    }
    async with async_session_factory() as s:
        await billing_service.handle_webhook_event(
            s,
            UPDATED,
            {"object": obj},
            event_id=f"{world['tag']}-{event_id}",
            created=created,
        )


async def _plan(world) -> str:
    async with async_session_factory() as s:
        return (
            await s.execute(select(Subscription.plan).where(Subscription.user_id == world["user"]))
        ).scalar_one()


async def _events(world) -> dict[str, str]:
    async with async_session_factory() as s:
        rows = await s.execute(
            select(StripeWebhookEvent.stripe_event_id, StripeWebhookEvent.outcome).where(
                StripeWebhookEvent.stripe_event_id.like(f"{world['tag']}-%")
            )
        )
        return {k.removeprefix(f"{world['tag']}-"): v for k, v in rows.all()}


class _ApplyGate:
    """Holds the first apply open until the test says go; later applies pass freely.

    Ordering comes from events and from Postgres itself, not from sleeps: the
    second delivery is only released-against once Postgres reports it blocked
    on the first one's lock (or it has finished without blocking, which is the
    signal that the lock is missing).
    """

    def __init__(self, original) -> None:
        self.original = original
        self.calls: list[str] = []
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, session, obj) -> None:
        self.calls.append(obj["status"])
        self.entered.set()
        await asyncio.wait_for(self.release.wait(), timeout=15)
        await self.original(session, obj)


@pytest.fixture
def gate(monkeypatch):
    g = _ApplyGate(billing_service._handle_subscription_update)
    monkeypatch.setattr(billing_service, "_handle_subscription_update", g)
    return g


async def _blocked_sessions() -> int:
    async with async_session_factory() as s:
        return await s.scalar(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock'"
            )
        )


async def _overlap(gate, first, second) -> None:
    """Run `first` to the apply step, start `second`, then let both finish.

    `second` is given until Postgres shows it waiting on a lock (the claim's
    unique index or the customer advisory lock) or it completes by itself.
    """
    t1 = asyncio.create_task(first)
    await asyncio.wait_for(gate.entered.wait(), timeout=15)
    t2 = asyncio.create_task(second)
    try:
        for _ in range(300):
            if t2.done() or await _blocked_sessions():
                break
            await asyncio.sleep(0.05)  # poll a condition; the order is fixed by the gate
    finally:
        gate.release.set()
    await asyncio.gather(t1, t2)


async def test_replay_of_an_applied_event_is_a_noop(world):
    await _deliver(world, "e1", "active", 1_000)
    assert await _plan(world) == "pro"
    async with async_session_factory() as s:
        await s.execute(
            Subscription.__table__.update()
            .where(Subscription.user_id == world["user"])
            .values(plan="free")
        )
        await s.commit()
    await _deliver(world, "e1", "active", 1_000)
    assert await _plan(world) == "free"  # not re-applied
    assert await _events(world) == {"e1": "applied"}


async def test_concurrent_duplicate_delivery_applies_once(world, gate):
    await _overlap(
        gate,
        _deliver(world, "dup", "active", 1_000),
        _deliver(world, "dup", "active", 1_000),
    )
    assert gate.calls == ["active"]
    assert await _plan(world) == "pro"
    assert await _events(world) == {"dup": "applied"}


async def test_failed_first_attempt_releases_the_claim_for_the_retry(world, monkeypatch):
    original = billing_service._handle_subscription_update

    async def boom(session, obj):
        raise RuntimeError("db down")

    monkeypatch.setattr(billing_service, "_handle_subscription_update", boom)
    with pytest.raises(RuntimeError):
        await _deliver(world, "retry", "active", 1_000)
    assert await _events(world) == {}
    monkeypatch.setattr(billing_service, "_handle_subscription_update", original)
    await _deliver(world, "retry", "active", 1_000)
    assert await _plan(world) == "pro"
    assert await _events(world) == {"retry": "applied"}


async def test_stale_event_is_ignored_and_recorded(world):
    await _deliver(world, "new", "active", 2_000)
    await _deliver(world, "old", "canceled", 1_000)
    assert await _plan(world) == "pro"
    assert await _events(world) == {"new": "applied", "old": "stale"}


@pytest.mark.parametrize("older_first", [True, False])
async def test_same_customer_concurrent_events_end_in_the_newer_state(world, gate, older_first):
    older = _deliver(world, "older", "canceled", 1_000)
    newer = _deliver(world, "newer", "active", 2_000)

    await (_overlap(gate, older, newer) if older_first else _overlap(gate, newer, older))

    assert await _plan(world) == "pro"
    outcomes = await _events(world)
    assert outcomes["newer"] == "applied"
    # Delivered older-first both apply in order; newer-first the older is stale.
    assert outcomes["older"] == ("applied" if older_first else "stale")


async def test_event_without_a_customer_is_applied_and_ordered_against_nothing(world):
    await _deliver(world, "n1", "active", 5_000, customer=None)
    await _deliver(world, "n2", "active", 1_000, customer=None)
    assert await _events(world) == {"n1": "applied", "n2": "applied"}


async def test_account_deletion_nulls_the_customer_and_keeps_the_rows(world, storage):
    await _deliver(world, "gone", "active", 1_000)
    async with async_session_factory() as s:
        await account_service.delete_user_account(s, world["user"], storage)
        await s.commit()
    async with async_session_factory() as s:
        rows = (
            await s.execute(
                select(
                    StripeWebhookEvent.stripe_event_id,
                    StripeWebhookEvent.stripe_customer_id,
                ).where(StripeWebhookEvent.stripe_event_id == f"{world['tag']}-gone")
            )
        ).all()
        total = await s.scalar(select(func.count()).select_from(StripeWebhookEvent))
    assert rows == [(f"{world['tag']}-gone", None)]
    assert total >= 1
