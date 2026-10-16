"""Tests for billing service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services import billing_service


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_subscription():
    """Create a mock Subscription object."""
    sub = MagicMock()
    sub.id = "sub-1"
    sub.user_id = "user-1"
    sub.stripe_customer_id = "cus_test123"
    sub.stripe_subscription_id = "sub_test123"
    sub.plan = "pro"
    sub.status = "active"
    sub.cancel_at_period_end = False
    return sub


class TestGetSubscription:
    """Tests for get_subscription."""

    @pytest.mark.asyncio
    async def test_returns_subscription(self, mock_session, mock_subscription):
        """Returns subscription when found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_session.execute.return_value = mock_result

        result = await billing_service.get_subscription(mock_session, "user-1")
        assert result == mock_subscription

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_session):
        """Returns None when no subscription exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await billing_service.get_subscription(mock_session, "user-1")
        assert result is None


class TestGetOrCreateSubscription:
    """Tests for get_or_create_subscription."""

    @pytest.mark.asyncio
    async def test_returns_existing(self, mock_session, mock_subscription):
        """Returns existing subscription if present."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_session.execute.return_value = mock_result

        result = await billing_service.get_or_create_subscription(
            mock_session, "user-1", "cus_test123"
        )
        assert result == mock_subscription
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new(self, mock_session):
        """Creates a new subscription when none exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await billing_service.get_or_create_subscription(mock_session, "user-1", "cus_new123")
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.user_id == "user-1"
        assert added.stripe_customer_id == "cus_new123"
        assert added.plan == "free"


class TestCreateCheckoutSession:
    """Tests for create_checkout_session."""

    @pytest.mark.asyncio
    async def test_creates_checkout_with_existing_customer(self, mock_session, mock_subscription):
        """Creates checkout session using existing Stripe customer."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_session.execute.return_value = mock_result

        mock_checkout = MagicMock()
        mock_checkout.url = "https://checkout.stripe.com/test"
        mock_checkout.id = "cs_test123"

        with patch("stripe.checkout.Session.create", return_value=mock_checkout) as mock_create:
            with patch("stripe.api_key", ""):
                url = await billing_service.create_checkout_session(
                    mock_session, "user-1", "https://ok.com", "https://cancel.com"
                )

        assert url == "https://checkout.stripe.com/test"
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["customer"] == "cus_test123"
        assert call_kwargs["mode"] == "subscription"

    @pytest.mark.asyncio
    async def test_creates_customer_if_none(self, mock_session):
        """Creates a Stripe customer when user has no subscription."""
        # First call: get_subscription returns None; second: get_or_create returns new
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] <= 2:
                result.scalar_one_or_none.return_value = None
            else:
                sub = MagicMock()
                sub.stripe_customer_id = "cus_new"
                result.scalar_one_or_none.return_value = sub
            return result

        mock_session.execute.side_effect = execute_side_effect

        mock_customer = MagicMock()
        mock_customer.id = "cus_new"

        mock_checkout = MagicMock()
        mock_checkout.url = "https://checkout.stripe.com/new"
        mock_checkout.id = "cs_new"

        with (
            patch("stripe.Customer.create", return_value=mock_customer),
            patch("stripe.checkout.Session.create", return_value=mock_checkout),
            patch("stripe.api_key", ""),
        ):
            url = await billing_service.create_checkout_session(
                mock_session, "user-1", "https://ok.com", "https://cancel.com"
            )

        assert url == "https://checkout.stripe.com/new"


class TestCreatePortalSession:
    """Tests for create_portal_session."""

    @pytest.mark.asyncio
    async def test_creates_portal(self, mock_session, mock_subscription):
        """Creates a billing portal session."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_session.execute.return_value = mock_result

        mock_portal = MagicMock()
        mock_portal.url = "https://billing.stripe.com/portal"

        with (
            patch("stripe.billing_portal.Session.create", return_value=mock_portal),
            patch("stripe.api_key", ""),
        ):
            url = await billing_service.create_portal_session(mock_session, "user-1")

        assert url == "https://billing.stripe.com/portal"

    @pytest.mark.asyncio
    async def test_raises_when_no_subscription(self, mock_session):
        """Raises ValueError when user has no subscription."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="No subscription found"):
            await billing_service.create_portal_session(mock_session, "user-1")


class TestHandleWebhookEvent:
    """Tests for handle_webhook_event."""

    @pytest.mark.asyncio
    async def test_subscription_updated_active(self, mock_session, mock_subscription):
        """Handles subscription.updated with active status."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_session.execute.return_value = mock_result

        mock_subscription.plan = "free"  # Will be updated to pro

        data = {
            "object": {
                "id": "sub_test123",
                "customer": "cus_test123",
                "status": "active",
                "current_period_start": 1700000000,
                "current_period_end": 1702592000,
                "cancel_at_period_end": False,
            }
        }

        await billing_service.handle_webhook_event(
            mock_session, "customer.subscription.updated", data
        )

        assert mock_subscription.plan == "pro"
        assert mock_subscription.status == "active"

    @pytest.mark.asyncio
    async def test_subscription_deleted(self, mock_session, mock_subscription):
        """Handles subscription.deleted by downgrading to free."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_session.execute.return_value = mock_result

        data = {"object": {"customer": "cus_test123"}}

        await billing_service.handle_webhook_event(
            mock_session, "customer.subscription.deleted", data
        )

        assert mock_subscription.plan == "free"
        assert mock_subscription.status == "canceled"

    @pytest.mark.asyncio
    async def test_ignores_unknown_events(self, mock_session):
        """Silently ignores unhandled event types."""
        await billing_service.handle_webhook_event(
            mock_session, "invoice.payment_failed", {"object": {}}
        )
        # No error raised


class TestRecordUsage:
    """Tests for record_usage."""

    @staticmethod
    def _sql(mock_session) -> str:
        from sqlalchemy.dialects import postgresql

        stmt = mock_session.execute.call_args[0][0]
        return str(stmt.compile(dialect=postgresql.dialect()))

    @pytest.mark.asyncio
    async def test_is_one_atomic_upsert_not_read_modify_write(self, mock_session):
        """Concurrent calls must not lose increments (COST-01 lost-update race)."""
        await billing_service.record_usage(mock_session, "user-1", ai_calls=1, uploads=1)

        mock_session.execute.assert_awaited_once()
        sql = self._sql(mock_session)
        assert "ON CONFLICT" in sql
        # increments are computed by the database from the stored value
        assert "usage_records.ai_calls_count +" in sql
        assert "usage_records.uploads_count +" in sql
        # nothing is read into Python and written back
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_carries_the_deltas_and_owner(self, mock_session):
        """The inserted row holds this call's deltas for this user."""
        await billing_service.record_usage(
            mock_session, "user-1", ai_calls=2, tokens_input=50, tokens_output=7
        )

        params = mock_session.execute.call_args[0][0].compile().params
        assert params["user_id"] == "user-1"
        assert params["ai_calls_count"] == 2
        assert params["ai_tokens_input"] == 50
        assert params["ai_tokens_output"] == 7


class TestEstimateTokens:
    """Per-call token estimate used when the adapter reports none."""

    def test_floor_applies_to_short_text(self):
        assert billing_service.estimate_tokens("hi") == settings.ai_call_estimate_min_tokens

    def test_scales_with_length(self):
        big = "x" * (settings.ai_call_estimate_min_tokens * 40)
        assert billing_service.estimate_tokens(big) == len(big) // 4


class TestRecordAiCall:
    """record_ai_call prefers real adapter tokens, else an estimate."""

    @pytest.mark.asyncio
    async def test_uses_adapter_tokens_when_reported(self, mock_session):
        agent = MagicMock()
        agent.usage.calls = 1
        agent.usage.input_tokens = 900
        agent.usage.output_tokens = 100
        with patch.object(billing_service, "record_usage", AsyncMock()) as rec:
            await billing_service.record_ai_call(mock_session, "u1", agent=agent)
        rec.assert_awaited_once_with(
            mock_session, "u1", ai_calls=1, tokens_input=900, tokens_output=100
        )

    @pytest.mark.asyncio
    async def test_estimates_when_adapter_reports_zero_tokens(self, mock_session):
        agent = MagicMock()
        agent.usage.calls = 1
        agent.usage.input_tokens = 0
        agent.usage.output_tokens = 0
        with patch.object(billing_service, "record_usage", AsyncMock()) as rec:
            await billing_service.record_ai_call(
                mock_session, "u1", agent=agent, prompt_text="q", output_text="a"
            )
        kw = rec.await_args.kwargs
        assert kw["ai_calls"] == 1
        assert kw["tokens_input"] >= settings.ai_call_estimate_min_tokens
        assert kw["tokens_output"] >= 1

    @pytest.mark.asyncio
    async def test_never_raises(self, mock_session):
        with patch.object(billing_service, "record_usage", AsyncMock(side_effect=RuntimeError)):
            await billing_service.record_ai_call(mock_session, "u1")


class TestCancelSubscription:
    """Tests for cancel_subscription."""

    @pytest.mark.asyncio
    async def test_cancels_at_period_end(self, mock_session, mock_subscription):
        """Sets cancel_at_period_end on the Stripe subscription."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        mock_session.execute.return_value = mock_result

        with (
            patch("stripe.Subscription.modify") as mock_modify,
            patch("stripe.api_key", ""),
        ):
            await billing_service.cancel_subscription(mock_session, "user-1")

        mock_modify.assert_called_once_with("sub_test123", cancel_at_period_end=True)
        assert mock_subscription.cancel_at_period_end is True

    @pytest.mark.asyncio
    async def test_raises_when_no_subscription(self, mock_session):
        """Raises ValueError when no subscription."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="No active subscription"):
            await billing_service.cancel_subscription(mock_session, "user-1")


class TestNoStripeCustomerIdInLogs:
    """Stripe customer ids are account identifiers: never logged raw (floor 2)."""

    CUS = "cus_SENTINEL123456"

    @pytest.mark.asyncio
    async def test_logs_carry_no_customer_id(self, mock_session):
        import structlog

        none_result = MagicMock()
        none_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = none_result
        mock_session.add = MagicMock()
        with structlog.testing.capture_logs() as logs:
            await billing_service.get_or_create_subscription(mock_session, "u1", self.CUS)
            await billing_service.handle_webhook_event(
                mock_session, "checkout.session.completed", {"object": {"customer": self.CUS}}
            )
            await billing_service._handle_subscription_update(mock_session, {"customer": self.CUS})
            await billing_service._handle_subscription_deleted(mock_session, {"customer": self.CUS})
        events = [entry["event"] for entry in logs]
        assert "subscription_created" in events
        assert "checkout_completed" in events
        assert events.count("webhook_subscription_not_found") == 2
        assert "cus_" not in repr(logs)

    def test_fingerprint_is_short_stable_and_not_the_id(self):
        fp = billing_service.customer_fingerprint(self.CUS)
        assert fp == billing_service.customer_fingerprint(self.CUS)
        assert len(fp) == 8
        assert fp != billing_service.customer_fingerprint("cus_other")
        assert billing_service.customer_fingerprint(None) is None
