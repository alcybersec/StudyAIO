"""Tests for billing API endpoints."""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import QuotaExceededError


@pytest.fixture
def free_user(make_user):
    """A free-tier user for billing tests."""
    return make_user(
        id="user-free",
        email="free@test.com",
        username="freeuser",
        role="user",
        tier="free",
    )


@pytest.fixture
def pro_user(make_user):
    """A pro-tier user for billing tests."""
    return make_user(
        id="user-pro",
        email="pro@test.com",
        username="prouser",
        role="user",
        tier="pro",
    )


@pytest.fixture
async def billing_client(mock_session, free_user):
    """Async client with a free-tier user and self_hosted=False."""
    from app.api.deps import get_current_user, get_current_user_or_default
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    async def override_session():
        yield mock_session

    async def override_user():
        return free_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user_or_default] = override_user
    app.dependency_overrides[get_current_user] = override_user

    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.config.settings.data_dir", tmpdir):
            with patch("app.config.settings.self_hosted", False):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def billing_client_pro(mock_session, pro_user):
    """Async client with a pro-tier user."""
    from app.api.deps import get_current_user, get_current_user_or_default
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    async def override_session():
        yield mock_session

    async def override_user():
        return pro_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user_or_default] = override_user
    app.dependency_overrides[get_current_user] = override_user

    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.config.settings.data_dir", tmpdir):
            with patch("app.config.settings.self_hosted", False):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def billing_client_selfhosted(mock_session, free_user):
    """Async client with self_hosted=True."""
    from app.api.deps import get_current_user, get_current_user_or_default
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    async def override_session():
        yield mock_session

    async def override_user():
        return free_user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user_or_default] = override_user
    app.dependency_overrides[get_current_user] = override_user

    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.config.settings.data_dir", tmpdir):
            with patch("app.config.settings.self_hosted", True):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    yield client

    app.dependency_overrides.clear()


class TestCreateCheckout:
    """Tests for POST /api/billing/checkout."""

    @pytest.mark.asyncio
    @patch("app.api.billing.billing_service")
    async def test_creates_checkout_session(self, mock_billing, billing_client):
        """Creates a Stripe checkout session for free user."""
        mock_billing.create_checkout_session = AsyncMock(
            return_value="https://checkout.stripe.com/test"
        )

        resp = await billing_client.post(
            "/api/billing/checkout",
            json={"success_url": "https://app.com/ok", "cancel_url": "https://app.com/cancel"},
        )
        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"

    @pytest.mark.asyncio
    async def test_rejects_self_hosted(self, billing_client_selfhosted):
        """Returns 400 in self-hosted mode."""
        resp = await billing_client_selfhosted.post(
            "/api/billing/checkout",
            json={"success_url": "https://app.com/ok", "cancel_url": "https://app.com/cancel"},
        )
        assert resp.status_code == 400
        assert "self-hosted" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_rejects_pro_user(self, billing_client_pro):
        """Returns 400 for already-Pro user."""
        resp = await billing_client_pro.post(
            "/api/billing/checkout",
            json={"success_url": "https://app.com/ok", "cancel_url": "https://app.com/cancel"},
        )
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()


class TestCreatePortal:
    """Tests for POST /api/billing/portal."""

    @pytest.mark.asyncio
    @patch("app.api.billing.billing_service")
    async def test_creates_portal_session(self, mock_billing, billing_client):
        """Creates a Stripe portal session."""
        mock_billing.create_portal_session = AsyncMock(
            return_value="https://billing.stripe.com/portal"
        )

        resp = await billing_client.post("/api/billing/portal")
        assert resp.status_code == 200
        assert resp.json()["portal_url"] == "https://billing.stripe.com/portal"

    @pytest.mark.asyncio
    @patch("app.api.billing.billing_service")
    async def test_404_when_no_subscription(self, mock_billing, billing_client):
        """Returns 404 when user has no subscription."""
        mock_billing.create_portal_session = AsyncMock(
            side_effect=ValueError("No subscription found for user")
        )

        resp = await billing_client.post("/api/billing/portal")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_rejects_self_hosted(self, billing_client_selfhosted):
        """Returns 400 in self-hosted mode."""
        resp = await billing_client_selfhosted.post("/api/billing/portal")
        assert resp.status_code == 400


class TestGetBillingOverview:
    """Tests for GET /api/billing/subscription."""

    @pytest.mark.asyncio
    @patch("app.api.billing.quota_service")
    @patch("app.api.billing.billing_service")
    async def test_returns_overview(self, mock_billing, mock_quota, billing_client):
        """Returns subscription and usage data."""
        mock_sub = MagicMock()
        mock_sub.plan = "free"
        mock_sub.status = "inactive"
        mock_sub.current_period_start = None
        mock_sub.current_period_end = None
        mock_sub.cancel_at_period_end = False
        mock_billing.get_subscription = AsyncMock(return_value=mock_sub)

        usage = MagicMock()
        usage.ai_calls_count = 5
        mock_quota.get_usage_today = AsyncMock(return_value=usage)
        mock_quota.get_monthly_upload_count = AsyncMock(return_value=2)
        mock_quota.get_course_count = AsyncMock(return_value=1)
        mock_quota.FREE_MAX_AI_CALLS_PER_DAY = 20
        mock_quota.FREE_MAX_UPLOADS_PER_MONTH = 5
        mock_quota.FREE_MAX_COURSES = 1

        resp = await billing_client.get("/api/billing/subscription")
        assert resp.status_code == 200
        data = resp.json()
        assert data["subscription"]["plan"] == "free"
        assert data["usage"]["ai_calls_today"] == 5
        assert data["usage"]["uploads_this_month"] == 2
        assert data["usage"]["courses_count"] == 1
        assert data["usage"]["ai_calls_limit"] == 20
        assert data["usage"]["uploads_limit"] == 5

    @pytest.mark.asyncio
    @patch("app.api.billing.quota_service")
    @patch("app.api.billing.billing_service")
    async def test_no_limits_when_no_subscription(self, mock_billing, mock_quota, billing_client_pro):
        """Pro users see no limits."""
        mock_billing.get_subscription = AsyncMock(return_value=None)

        mock_quota.get_usage_today = AsyncMock(return_value=None)
        mock_quota.get_monthly_upload_count = AsyncMock(return_value=10)
        mock_quota.get_course_count = AsyncMock(return_value=5)
        mock_quota.FREE_MAX_AI_CALLS_PER_DAY = 20
        mock_quota.FREE_MAX_UPLOADS_PER_MONTH = 5
        mock_quota.FREE_MAX_COURSES = 1

        resp = await billing_client_pro.get("/api/billing/subscription")
        assert resp.status_code == 200
        data = resp.json()
        assert data["usage"]["ai_calls_limit"] is None
        assert data["usage"]["uploads_limit"] is None


class TestQuotaExceededHandler:
    """Tests for 402 Payment Required error handler."""

    @pytest.mark.asyncio
    async def test_quota_exceeded_returns_402(self, billing_client):
        """QuotaExceededError is handled as 402."""
        # Patch an endpoint to raise QuotaExceededError
        with patch(
            "app.api.billing.billing_service.create_checkout_session",
            side_effect=QuotaExceededError(
                resource="uploads", limit=5, period="month"
            ),
        ):
            resp = await billing_client.post(
                "/api/billing/checkout",
                json={"success_url": "https://ok.com", "cancel_url": "https://cancel.com"},
            )
            assert resp.status_code == 402
            data = resp.json()
            assert data["resource"] == "uploads"
            assert data["limit"] == 5
            assert data["period"] == "month"
