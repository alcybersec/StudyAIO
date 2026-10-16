"""Stripe webhook safety (BILL-01, GL#21, R-034): replay, ordering, trialing, tenancy."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services import billing_service


class FakeWebhookSession:
    """A session with an in-memory ``stripe_webhook_events`` table and one transaction.

    Interprets only the statements ``handle_webhook_event`` issues: the claim
    INSERT, the per-customer lock, the watermark SELECT and the stale UPDATE.
    Anything else is a subscription lookup and answers with ``self.sub``.
    ``rollback`` discards what the transaction wrote, as Postgres would.
    """

    def __init__(self) -> None:
        self.committed: list[dict] = []
        self.pending: list[dict] = []
        self.sub = None
        self.fail_on_lookup = False
        self.commits = 0
        self.rollbacks = 0
        self.lock_taken_for: list[str] = []

    async def execute(self, stmt, *_a, **_k):
        compiled = stmt.compile(dialect=postgresql.dialect())
        sql = " ".join(str(compiled).split())
        params = compiled.params
        result = MagicMock()
        if sql.startswith("INSERT INTO stripe_webhook_events"):
            if any(e["stripe_event_id"] == params["stripe_event_id"] for e in self.pending):
                result.scalar_one_or_none.return_value = None
            else:
                self.pending.append(
                    {
                        "id": params["id"],
                        "stripe_event_id": params["stripe_event_id"],
                        "stripe_customer_id": params["stripe_customer_id"],
                        "stripe_created": params["stripe_created"],
                        "outcome": params["outcome"],
                    }
                )
                result.scalar_one_or_none.return_value = params["id"]
        elif "pg_advisory_xact_lock" in sql:
            self.lock_taken_for.append(next(v for v in params.values() if "stripe:customer:" in v))
        elif sql.startswith("SELECT stripe_webhook_events.id"):
            hit = any(
                e["stripe_customer_id"] == params["stripe_customer_id_1"]
                and e["outcome"] == params["outcome_1"]
                and e["stripe_created"] > params["stripe_created_1"]
                for e in self.pending
            )
            result.scalar_one_or_none.return_value = "newer" if hit else None
        elif sql.startswith("UPDATE stripe_webhook_events"):
            for e in self.pending:
                if e["id"] == params["id_1"]:
                    e["outcome"] = params["outcome"]
        else:
            if self.fail_on_lookup:
                raise RuntimeError("db down")
            result.scalar_one_or_none.return_value = self.sub
        return result

    async def commit(self) -> None:
        self.commits += 1
        self.committed = [dict(e) for e in self.pending]

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.pending = [dict(e) for e in self.committed]


@pytest.fixture
def session():
    return FakeWebhookSession()


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
    session.sub = sub


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
        commits = session.commits
        sub.plan = "free"  # tamper to prove a replay does not touch it again
        await _send(session, "active", "evt_1", 100)
        assert sub.plan == "free"
        assert session.commits == commits
        assert len(session.committed) == 1

    async def test_failed_processing_rolls_the_claim_back_and_can_be_retried(self, session, sub):
        session.fail_on_lookup = True
        with pytest.raises(RuntimeError):
            await _send(session, "active", "evt_2", 100)
        assert session.committed == [] and session.pending == []
        assert session.rollbacks == 1
        session.fail_on_lookup = False
        _found(session, sub)
        await _send(session, "active", "evt_2", 100)
        assert sub.plan == "pro"
        assert [e["outcome"] for e in session.committed] == ["applied"]

    async def test_claim_and_effect_share_one_commit(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "evt_3", 100)
        assert session.commits == 1
        assert len(session.committed) == 1

    async def test_no_redis_on_any_path(self, session, sub, monkeypatch):
        from app.core import redis as redis_mod

        class _Boom:
            def __getattr__(self, name):
                raise AssertionError(f"billing touched Redis: {name}")

        monkeypatch.setattr(redis_mod, "redis_client", _Boom())
        _found(session, sub)
        await _send(session, "active", "evt_4", 100)
        await _send(session, "active", "evt_4", 100)
        await _send(session, "canceled", "evt_5", 50)


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

    async def test_stale_event_is_recorded_stale_and_committed(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "evt_new", 200)
        await _send(session, "canceled", "evt_old", 100)
        outcomes = {e["stripe_event_id"]: e["outcome"] for e in session.committed}
        assert outcomes == {"evt_new": "applied", "evt_old": "stale"}

    async def test_customer_lock_is_taken_for_the_event_customer(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "evt_l", 100, customer="cus_1")
        assert session.lock_taken_for == ["stripe:customer:cus_1"]

    async def test_event_without_a_customer_is_applied_and_not_ordered(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "evt_a", 500, customer=None)
        await _send(session, "active", "evt_b", 100, customer=None)
        assert session.lock_taken_for == []
        assert [e["outcome"] for e in session.committed] == ["applied", "applied"]

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

    async def test_lookup_is_keyed_on_the_event_customer(self, session, sub):
        _found(session, sub)
        seen: list[str] = []
        original = session.execute

        async def spy(stmt, *a, **k):
            seen.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))
            return await original(stmt, *a, **k)

        session.execute = spy
        await _send(session, "active", "e2", 100, customer="cus_1")
        lookup = [q for q in seen if "FROM subscriptions" in q]
        assert lookup and "cus_1" in lookup[0]

    async def test_ordering_state_is_per_customer(self, session, sub):
        _found(session, sub)
        await _send(session, "active", "e1", 500, customer="cus_other")
        await _send(session, "active", "e2", 100, customer="cus_1")
        assert sub.plan == "pro"
