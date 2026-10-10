"""Stripe webhook safety (BILL-01, GL#21, R-034): replay, ordering, trialing, tenancy."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import billing_service


@pytest.fixture
def session():
    s = AsyncMock()
    s.commit = AsyncMock()
    return s


@pytest.fixture
def sub():
    s = MagicMock()
    s.user_id = "user-1"
    s.stripe_customer_id = "cus_1"
    s.stripe_subscription_id = "sub_1"
    s.plan = "free"
    s.status = "inactive"
    return s


def _found(session, sub):
    result = MagicMock()
    result.scalar_one_or_none.return_value = sub
    session.execute.return_value = result


def _data(status="active", customer="cus_1", sub_id="sub_1"):
    return {"object": {"id": sub_id, "customer": customer, "status": status}}


UPDATED = "customer.subscription.updated"
DELETED = "customer.subscription.deleted"


async def _send(session, status, event_id, created, event_type=UPDATED, **kw):
    await billing_service.handle_webhook_event(
        session, event_type, _data(status, **kw), event_id=event_id, created=created
    )


@pytest.mark.asyncio
class TestIdempotency:
    async def test_replayed_event_id_is_applied_once(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "evt_1", 100)
        calls = session.execute.await_count
        sub.plan = "free"  # tamper to prove a replay does not touch it again
        await _send(session, "active", "evt_1", 100)
        assert session.execute.await_count == calls
        assert sub.plan == "free"

    async def test_failed_processing_can_be_retried(self, session, sub):
        session.execute.side_effect = RuntimeError("db down")
        with pytest.raises(RuntimeError):
            await _send(session, "active", "evt_2", 100)
        session.execute.side_effect = None
        _found(session, sub)
        await _send(session, "active", "evt_2", 100)
        assert sub.plan == "pro"


@pytest.mark.asyncio
class TestOrdering:
    async def test_stale_updated_cannot_downgrade(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "evt_new", 200)
        assert sub.plan == "pro"
        await _send(session, "canceled", "evt_old", 100)  # arrives late
        assert sub.plan == "pro"
        assert sub.status == "active"

    async def test_stale_deleted_cannot_downgrade(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "evt_new", 200)
        await _send(session, "canceled", "evt_del", 100, event_type=DELETED)
        assert sub.plan == "pro"

    async def test_newer_event_still_applies(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "e1", 100)
        await _send(session, "canceled", "e2", 200)
        assert sub.plan == "free"

    async def test_deleted_for_a_replaced_subscription_is_ignored(self, session, sub):
        _found(session, sub)
        sub.plan = "pro"
        await _send(session, "canceled", "e1", 100, event_type=DELETED, sub_id="sub_OLD")
        assert sub.plan == "pro"
        assert sub.stripe_subscription_id == "sub_1"


@pytest.mark.asyncio
class TestStatusMapping:
    @pytest.mark.parametrize("status", ["active", "trialing", "past_due"])
    async def test_paying_like_statuses_map_to_pro(self, session, sub, status):
        _found(session, sub)
        await _send(session, status, f"e_{status}", 100)
        assert sub.plan == "pro"
        assert sub.status == status

    @pytest.mark.parametrize("status", ["canceled", "unpaid", "incomplete_expired", "paused"])
    async def test_ended_statuses_map_to_free(self, session, sub, status):
        _found(session, sub)
        sub.plan = "pro"
        await _send(session, status, f"e_{status}", 100)
        assert sub.plan == "free"

    async def test_incomplete_does_not_grant_pro(self, session, sub):
        _found(session, sub)
        await _send(session, "incomplete", "e_inc", 100)
        assert sub.plan == "free"

    async def test_past_due_after_trial_keeps_pro(self, session, sub):
        _found(session, sub)
        await _send(session, "trialing", "e1", 100)
        await _send(session, "past_due", "e2", 200)
        assert sub.plan == "pro"


@pytest.mark.asyncio
class TestTenancy:
    async def test_unknown_customer_changes_nobody(self, session, sub):
        _found(session, None)
        await _send(session, "active", "e_ghost", 100, customer="cus_ghost")
        assert sub.plan == "free"
        session.commit.assert_not_awaited()

    async def test_lookup_is_keyed_on_the_event_customer(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "e1", 100, customer="cus_1")
        stmt = session.execute.await_args_list[0].args[0]
        assert "cus_1" in str(stmt.compile(compile_kwargs={"literal_binds": True}))

    async def test_ordering_state_is_per_customer(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "e1", 500, customer="cus_other")
        await _send(session, "active", "e2", 100, customer="cus_1")
        assert sub.plan == "pro"
