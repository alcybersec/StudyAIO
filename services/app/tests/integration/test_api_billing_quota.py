"""Billing endpoints, Stripe webhooks (really signed) and quota enforcement.

Stripe's HTTP API is the only thing replaced. Webhook payloads are signed with
the configured secret exactly as Stripe signs them, so `construct_event`'s
signature check runs for real, and every effect is read back from Postgres.
"""

import hashlib
import hmac
import json
import time
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.exceptions import GlobalCeilingError, QuotaExceededError
from app.core.utils import generate_id
from app.models.subscription import Subscription
from app.models.usage_record import UsageRecord
from app.services import billing_service, quota_service

from ._support import FakeAgent

pytestmark = pytest.mark.asyncio(loop_scope="session")

WEBHOOK_SECRET = "whsec_integration_test_secret"


@pytest.fixture
def saas():
    with (
        patch("app.config.settings.self_hosted", False),
        patch("app.config.settings.stripe_webhook_secret", SecretStr(WEBHOOK_SECRET)),
        patch("app.config.settings.stripe_api_key", SecretStr("sk_test_dummy")),
        patch("app.config.settings.stripe_pro_price_id", "price_pro"),
    ):
        yield


def _signed(payload: dict, secret: str = WEBHOOK_SECRET) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}


async def _subscription(db_session, user, customer="cus_1", **kw) -> Subscription:
    sub = Subscription(
        id=generate_id(),
        user_id=user.id,
        stripe_customer_id=customer,
        plan="free",
        status="inactive",
        **kw,
    )
    db_session.add(sub)
    await db_session.flush()
    return sub


class TestOverview:
    async def test_self_hosted_user_has_no_limits(self, client_factory, make_user):
        user = await make_user(tier="free")
        body = (await client_factory(user).get("/api/billing/subscription")).json()
        assert body["subscription"]["status"] == "active"
        assert body["usage"]["ai_calls_limit"] is None and body["usage"]["courses_limit"] is None

    @pytest.mark.xfail(
        strict=True,
        reason="BUG: api/billing.py reads quota_service.FREE_MAX_AI_CALLS_PER_DAY / "
        "FREE_MAX_UPLOADS_PER_MONTH / FREE_MAX_COURSES, which do not exist (limits moved to "
        "settings + _limit_for), so GET /billing/subscription raises AttributeError for every "
        "free user on a non-self-hosted instance",
    )
    async def test_saas_free_user_sees_limits_and_usage(
        self, client_factory, make_user, db_session, saas
    ):
        user = await make_user(tier="free")
        db_session.add(
            UsageRecord(
                id=generate_id(),
                user_id=user.id,
                record_date=date.today(),
                ai_calls_count=7,
                uploads_count=2,
            )
        )
        await db_session.flush()
        resp = await client_factory(user).get("/api/billing/subscription")
        assert resp.status_code == 200
        usage = resp.json()["usage"]
        assert usage["ai_calls_today"] == 7 and usage["uploads_this_month"] == 2
        assert usage["ai_calls_limit"] == 100 and usage["uploads_limit"] == 5

    async def test_saas_pro_user_is_unlimited_and_reports_subscription(
        self, client_factory, make_user, db_session, saas
    ):
        user = await make_user(tier="pro")
        sub = await _subscription(db_session, user)
        sub.plan, sub.status = "pro", "active"
        await db_session.flush()
        body = (await client_factory(user).get("/api/billing/subscription")).json()
        assert body["subscription"]["plan"] == "pro" and body["subscription"]["status"] == "active"
        assert body["usage"]["ai_calls_limit"] is None

    async def test_billing_requires_authentication(self, client_factory):
        assert (await client_factory().get("/api/billing/subscription")).status_code == 401


class TestCheckoutAndPortal:
    async def test_disabled_when_self_hosted(self, client_factory, make_user):
        client = client_factory(await make_user())
        body = {"success_url": "https://x/ok", "cancel_url": "https://x/no"}
        assert (await client.post("/api/billing/checkout", json=body)).status_code == 400
        assert (await client.post("/api/billing/portal")).status_code == 400

    async def test_checkout_creates_customer_once_and_returns_url(
        self, client_factory, make_user, db_session, saas
    ):
        user = await make_user()
        body = {"success_url": "https://x/ok", "cancel_url": "https://x/no"}
        with (
            patch("stripe.Customer.create", return_value=SimpleNamespace(id="cus_new")) as cust,
            patch(
                "stripe.checkout.Session.create",
                return_value=SimpleNamespace(id="cs_1", url="https://stripe.test/checkout"),
            ) as sess,
        ):
            first = await client_factory(user).post("/api/billing/checkout", json=body)
            second = await client_factory(user).post("/api/billing/checkout", json=body)
        assert (
            first.status_code == 200
            and first.json()["checkout_url"] == "https://stripe.test/checkout"
        )
        assert second.status_code == 200
        cust.assert_called_once()  # the customer id was persisted and reused
        assert sess.call_args.kwargs["customer"] == "cus_new"
        assert sess.call_args.kwargs["line_items"][0]["price"] == "price_pro"
        stored = (
            await db_session.execute(select(Subscription).where(Subscription.user_id == user.id))
        ).scalar_one()
        assert stored.stripe_customer_id == "cus_new"

    async def test_pro_user_cannot_check_out_again(self, client_factory, make_user, saas):
        resp = await client_factory(await make_user(tier="pro")).post(
            "/api/billing/checkout",
            json={"success_url": "https://x/ok", "cancel_url": "https://x/no"},
        )
        assert resp.status_code == 400

    async def test_portal_needs_a_subscription(self, client_factory, make_user, db_session, saas):
        user = await make_user()
        assert (await client_factory(user).post("/api/billing/portal")).status_code == 404
        await _subscription(db_session, user, customer="cus_portal")
        with patch(
            "stripe.billing_portal.Session.create",
            return_value=SimpleNamespace(url="https://stripe.test/portal"),
        ) as portal:
            resp = await client_factory(user).post("/api/billing/portal")
        assert resp.json()["portal_url"] == "https://stripe.test/portal"
        assert portal.call_args.kwargs["customer"] == "cus_portal"


class TestWebhook:
    async def _post(self, client_factory, payload, **kw):
        body, headers = _signed(payload, **kw)
        return await client_factory().post("/api/billing/webhook", content=body, headers=headers)

    async def test_signature_is_enforced(self, client_factory, saas):
        client = client_factory()
        payload = json.dumps({"id": "evt", "type": "x", "data": {"object": {}}}).encode()
        assert (await client.post("/api/billing/webhook", content=payload)).status_code == 400
        bad = await client.post(
            "/api/billing/webhook", content=payload, headers={"stripe-signature": "t=1,v1=deadbeef"}
        )
        assert bad.status_code == 400
        with patch("app.config.settings.stripe_webhook_secret", SecretStr("")):
            body, headers = _signed({"id": "e", "type": "x", "data": {"object": {}}})
            unconfigured = await client.post("/api/billing/webhook", content=body, headers=headers)
        assert unconfigured.status_code == 500

    async def test_subscription_lifecycle_upgrades_then_downgrades_user(
        self, client_factory, make_user, db_session, saas
    ):
        user = await make_user(tier="free")
        sub = await _subscription(db_session, user, customer="cus_life")
        now = int(time.time())

        active = await self._post(
            client_factory,
            {
                "id": "evt_1",
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_1",
                        "customer": "cus_life",
                        "status": "active",
                        "current_period_start": now,
                        "current_period_end": now + 86400 * 30,
                        "cancel_at_period_end": True,
                    }
                },
            },
        )
        assert active.status_code == 200 and active.json() == {"status": "ok"}
        await db_session.refresh(sub)
        await db_session.refresh(user)
        assert (sub.plan, sub.status, sub.stripe_subscription_id) == ("pro", "active", "sub_1")
        assert sub.cancel_at_period_end is True and sub.current_period_end is not None
        assert user.tier == "pro"

        past_due = await self._post(
            client_factory,
            {
                "id": "evt_2",
                "type": "customer.subscription.updated",
                "data": {"object": {"id": "sub_1", "customer": "cus_life", "status": "past_due"}},
            },
        )
        assert past_due.status_code == 200
        await db_session.refresh(user)
        assert user.tier == "free"

        deleted = await self._post(
            client_factory,
            {
                "id": "evt_3",
                "type": "customer.subscription.deleted",
                "data": {"object": {"id": "sub_1", "customer": "cus_life"}},
            },
        )
        assert deleted.status_code == 200
        await db_session.refresh(sub)
        assert (sub.plan, sub.status, sub.stripe_subscription_id) == ("free", "canceled", None)

    async def test_unknown_customer_and_ignored_events_are_acknowledged(self, client_factory, saas):
        for event_type, obj in (
            ("customer.subscription.updated", {"customer": "cus_ghost", "status": "active"}),
            ("customer.subscription.deleted", {"customer": "cus_ghost"}),
            ("checkout.session.completed", {"customer": "cus_ghost"}),
            ("invoice.paid", {}),
        ):
            resp = await self._post(
                client_factory, {"id": "evt", "type": event_type, "data": {"object": obj}}
            )
            assert resp.status_code == 200, event_type

    async def test_webhook_cannot_upgrade_another_customers_user(
        self, client_factory, make_user, db_session, saas
    ):
        victim = await make_user(tier="free")
        await _subscription(db_session, victim, customer="cus_victim")
        resp = await self._post(
            client_factory,
            {
                "id": "evt",
                "type": "customer.subscription.updated",
                "data": {"object": {"id": "s", "customer": "cus_someone_else", "status": "active"}},
            },
        )
        assert resp.status_code == 200
        await db_session.refresh(victim)
        assert victim.tier == "free"

    async def test_cancel_subscription_service(self, make_user, db_session, saas):
        user = await make_user()
        with pytest.raises(ValueError):
            await billing_service.cancel_subscription(db_session, user.id)
        sub = await _subscription(db_session, user, customer="cus_c")
        sub.stripe_subscription_id = "sub_c"
        await db_session.flush()
        with patch("stripe.Subscription.modify") as modify:
            await billing_service.cancel_subscription(db_session, user.id)
        modify.assert_called_once_with("sub_c", cancel_at_period_end=True)
        assert sub.cancel_at_period_end is True


class TestUsageMetering:
    async def test_record_usage_accumulates_per_day(self, make_user, db_session):
        user = await make_user()
        await billing_service.record_usage(db_session, user.id, ai_calls=2, tokens_input=10)
        await billing_service.record_usage(db_session, user.id, uploads=1, tokens_output=5)
        rows = (
            (await db_session.execute(select(UsageRecord).where(UsageRecord.user_id == user.id)))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert (rows[0].ai_calls_count, rows[0].uploads_count) == (2, 1)
        assert (rows[0].ai_tokens_input, rows[0].ai_tokens_output) == (10, 5)

    async def test_record_agent_usage_resets_the_adapter_counter(self, make_user, db_session):
        user = await make_user()
        agent = FakeAgent()
        agent.usage.add(100, 50)
        agent.usage.add(1, 1)
        await billing_service.record_agent_usage(db_session, user.id, agent)
        row = (
            await db_session.execute(select(UsageRecord).where(UsageRecord.user_id == user.id))
        ).scalar_one()
        assert (row.ai_calls_count, row.ai_tokens_input, row.ai_tokens_output) == (2, 101, 51)
        assert agent.usage.calls == 0
        await billing_service.record_agent_usage(db_session, user.id, agent)  # nothing pending
        await db_session.refresh(row)
        assert row.ai_calls_count == 2


class TestQuotas:
    async def test_ai_quota_blocks_at_the_limit_for_free_not_for_pro(
        self, make_user, db_session, saas
    ):
        free, pro = await make_user(tier="free"), await make_user(tier="pro")
        for user in (free, pro):
            await billing_service.record_usage(db_session, user.id, ai_calls=100)
        with patch("app.config.settings.free_max_ai_calls_per_day", 100):
            with pytest.raises(QuotaExceededError):
                await quota_service.check_ai_quota(db_session, free.id, "free")
            await quota_service.check_ai_quota(db_session, pro.id, "pro")
            # A whole pipeline run must fit, not just one call.
            near = await make_user(tier="free")
            await billing_service.record_usage(db_session, near.id, ai_calls=98)
            with pytest.raises(QuotaExceededError):
                await quota_service.check_ai_quota(
                    db_session, near.id, "free", calls=quota_service.PIPELINE_AI_CALLS_PER_UPLOAD
                )

    async def test_quota_does_not_apply_when_self_hosted(self, make_user, db_session):
        user = await make_user(tier="free")
        await billing_service.record_usage(db_session, user.id, ai_calls=10_000, uploads=10_000)
        await quota_service.check_ai_quota(db_session, user.id, "free")
        await quota_service.check_upload_quota(db_session, user.id, "free")
        await quota_service.check_course_quota(db_session, user.id, "free")

    async def test_course_quota(self, make_user, db_session, saas):
        from app.models.course import Course

        user = await make_user(tier="free")
        await quota_service.check_course_quota(db_session, user.id, "free")
        db_session.add(Course(id=generate_id(), code="Q1", name="Q1", user_id=user.id))
        await db_session.flush()
        with pytest.raises(QuotaExceededError):
            await quota_service.check_course_quota(db_session, user.id, "free")

    async def test_global_ceiling_counts_only_instance_funded_users(self, make_user, db_session):
        from app.models.user_settings import UserSettings

        mine = await make_user()
        byo = await make_user()
        db_session.add(
            UserSettings(
                id=generate_id(),
                user_id=byo.id,
                settings_json={"agent_backend": "openai", "openai_api_key": "sk-x"},
                theme="system",
            )
        )
        await db_session.flush()
        await billing_service.record_usage(db_session, byo.id, ai_calls=5_000)
        with patch("app.config.settings.global_max_ai_calls_per_day", 50):
            baseline, _ = await quota_service.get_global_usage_today(db_session)
            await quota_service.check_global_ai_ceiling(
                db_session
            )  # BYO spend is not the operator's
            await billing_service.record_usage(db_session, mine.id, ai_calls=max(50 - baseline, 1))
            with pytest.raises(GlobalCeilingError):
                await quota_service.check_global_ai_ceiling(db_session)
            with pytest.raises(GlobalCeilingError):
                await quota_service.check_ai_quota(db_session, mine.id, "pro")
            # The BYO user is exempt from the operator's ceiling.
            await quota_service.check_ai_quota(db_session, byo.id, "pro")
        with patch("app.config.settings.global_max_ai_tokens_per_day", 1):
            await billing_service.record_usage(db_session, mine.id, tokens_input=10)
            with pytest.raises(GlobalCeilingError):
                await quota_service.check_global_ai_ceiling(db_session)

    async def test_quota_exceeded_is_http_402_with_context(
        self, client_factory, make_user, db_session
    ):
        user = await make_user(tier="free")
        await billing_service.record_usage(db_session, user.id, ai_calls=1)
        with (
            patch("app.config.settings.self_hosted", False),
            patch("app.config.settings.free_max_ai_calls_per_day", 1),
        ):
            resp = await client_factory(user).post("/api/qa/ask", json={"question": "q"})
        assert resp.status_code == 402
        assert "ai_calls" in resp.text or "limit" in resp.text.lower()
