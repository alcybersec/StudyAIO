"""Tests for email verification delivery on register and resend-verification."""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import UserExistsError
from app.models.user import User


def _make_user(email_verified: bool) -> User:
    """Create a mock User for the verification endpoints."""
    user = MagicMock(spec=User)
    user.id = "user-001"
    user.email = "real@example.com"
    user.username = "testuser"
    user.role = "user"
    user.tier = "free"
    user.is_active = True
    user.email_verified = email_verified
    user.mfa_enabled = False
    user.avatar_url = None
    user.last_login_at = None
    return user


def _make_link() -> MagicMock:
    """Create a mock freshly-minted verification link."""
    link = MagicMock()
    link.token = "verify-token-123"
    return link


def _make_auth_client(mock_session, user: User):
    """Yield an httpx client authenticated as `user` via get_current_user."""
    from app.api.deps import get_current_user
    from app.core.database import get_session
    from app.main import app

    async def override_session():
        yield mock_session

    async def override_user():
        return user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user

    from app.core.rate_limit import limiter

    limiter.reset()

    import contextlib

    @contextlib.asynccontextmanager
    async def _client():
        with tempfile.TemporaryDirectory() as tmpdir, patch("app.config.settings.data_dir", tmpdir):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                yield client
        app.dependency_overrides.clear()

    return _client()


@pytest.fixture
async def unverified_client(mock_session):
    """Async client authenticated as an unverified user via get_current_user."""
    async with _make_auth_client(mock_session, _make_user(email_verified=False)) as client:
        yield client


@pytest.fixture
async def verified_client(mock_session):
    """Async client authenticated as an already-verified user."""
    async with _make_auth_client(mock_session, _make_user(email_verified=True)) as client:
        yield client


class TestRegisterVerification:
    """POST /api/auth/register — verification link delivery."""

    @pytest.mark.asyncio
    async def test_register_mints_and_delivers_verification_link(self, async_client, mock_session):
        """A new password-registered user gets a verification email with their token."""
        user = _make_user(email_verified=False)
        link = _make_link()

        with (
            patch(
                "app.api.auth.user_service.register_user",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                new_callable=AsyncMock,
                return_value=link,
            ) as mock_create,
            patch(
                "app.api.auth.user_service.deliver_email_verification",
                new_callable=AsyncMock,
            ) as mock_deliver,
        ):
            response = await async_client.post(
                "/api/auth/register",
                json={
                    "email": "new@example.com",
                    "username": "newuser",
                    "password": "StrongPass1!",
                },
            )

        assert response.status_code == 201
        mock_create.assert_awaited_once()
        mock_deliver.assert_awaited_once_with("new@example.com", "verify-token-123")

    @pytest.mark.asyncio
    async def test_register_delivers_after_commit(self, async_client, mock_session):
        """The token must be committed before the email goes out."""
        user = _make_user(email_verified=False)
        link = _make_link()
        order: list[str] = []

        mock_session.commit = AsyncMock(side_effect=lambda: order.append("commit"))

        with (
            patch(
                "app.api.auth.user_service.register_user",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                new_callable=AsyncMock,
                return_value=link,
            ),
            patch(
                "app.api.auth.user_service.deliver_email_verification",
                new_callable=AsyncMock,
            ) as mock_deliver,
        ):
            mock_deliver.side_effect = lambda *a: order.append("deliver")

            await async_client.post(
                "/api/auth/register",
                json={
                    "email": "new@example.com",
                    "username": "newuser",
                    "password": "StrongPass1!",
                },
            )

        assert order == ["commit", "deliver"]

    @pytest.mark.asyncio
    async def test_register_still_201_when_delivery_fails(self, async_client, mock_session):
        """A broken mail server must not fail registration."""
        user = _make_user(email_verified=False)
        link = _make_link()

        with (
            patch(
                "app.api.auth.user_service.register_user",
                new_callable=AsyncMock,
                return_value=user,
            ),
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                new_callable=AsyncMock,
                return_value=link,
            ),
            patch(
                "app.api.auth.user_service.deliver_email_verification",
                new_callable=AsyncMock,
                side_effect=RuntimeError("smtp exploded"),
            ),
        ):
            response = await async_client.post(
                "/api/auth/register",
                json={
                    "email": "new@example.com",
                    "username": "newuser",
                    "password": "StrongPass1!",
                },
            )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_register_duplicate_email_mints_nothing(self, async_client, mock_session):
        """A registration that fails must not leave a verification link behind."""
        with (
            patch(
                "app.api.auth.user_service.register_user",
                new_callable=AsyncMock,
                side_effect=UserExistsError("email"),
            ),
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                new_callable=AsyncMock,
            ) as mock_create,
            patch(
                "app.api.auth.user_service.deliver_email_verification",
                new_callable=AsyncMock,
            ) as mock_deliver,
        ):
            response = await async_client.post(
                "/api/auth/register",
                json={
                    "email": "taken@example.com",
                    "username": "newuser",
                    "password": "StrongPass1!",
                },
            )

        assert response.status_code == 409
        mock_create.assert_not_awaited()
        mock_deliver.assert_not_awaited()


class TestResendVerification:
    """POST /api/auth/resend-verification"""

    @pytest.mark.asyncio
    async def test_resend_unverified_user_mints_and_delivers(self, unverified_client):
        """An unverified user gets a fresh link emailed to their own address."""
        link = _make_link()

        with (
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                new_callable=AsyncMock,
                return_value=link,
            ) as mock_create,
            patch(
                "app.api.auth.user_service.deliver_email_verification",
                new_callable=AsyncMock,
            ) as mock_deliver,
        ):
            response = await unverified_client.post("/api/auth/resend-verification")

        assert response.status_code == 202
        mock_create.assert_awaited_once()
        mock_deliver.assert_awaited_once_with("real@example.com", "verify-token-123")

    @pytest.mark.asyncio
    async def test_resend_already_verified_is_a_noop(self, verified_client):
        """No link and no email when there is nothing left to verify."""
        with (
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                new_callable=AsyncMock,
            ) as mock_create,
            patch(
                "app.api.auth.user_service.deliver_email_verification",
                new_callable=AsyncMock,
            ) as mock_deliver,
        ):
            response = await verified_client.post("/api/auth/resend-verification")

        assert response.status_code == 202
        assert response.json()["detail"] == "Email is already verified"
        mock_create.assert_not_awaited()
        mock_deliver.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resend_swallows_delivery_failure(self, unverified_client):
        """A dead mail server must not turn the 202 into a 500."""
        with (
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                new_callable=AsyncMock,
                return_value=_make_link(),
            ),
            patch(
                "app.api.auth.user_service.deliver_email_verification",
                new_callable=AsyncMock,
                side_effect=RuntimeError("smtp exploded"),
            ),
        ):
            response = await unverified_client.post("/api/auth/resend-verification")

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_resend_requires_authentication(self, async_client):
        """Without a session the endpoint is closed — it must not become an
        unauthenticated email-sending oracle."""
        response = await async_client.post("/api/auth/resend-verification")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_resend_rate_limited_after_3_attempts(self, unverified_client):
        """Mirrors the reset-request limit: 3/minute, then 429."""
        with (
            patch(
                "app.api.auth.user_service.create_email_verification_link",
                new_callable=AsyncMock,
                return_value=_make_link(),
            ),
            patch(
                "app.api.auth.user_service.deliver_email_verification",
                new_callable=AsyncMock,
            ),
        ):
            for i in range(3):
                response = await unverified_client.post("/api/auth/resend-verification")
                assert response.status_code == 202, f"Request {i + 1} should not be limited yet"

            response = await unverified_client.post("/api/auth/resend-verification")
            assert response.status_code == 429
