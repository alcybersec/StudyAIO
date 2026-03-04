"""Edge-case tests for auth endpoints and flows."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.auth import create_access_token, hash_password
from app.models.user import User


def _make_db_user(**overrides) -> User:
    from datetime import datetime

    defaults = {
        "id": "user-001",
        "email": "test@example.com",
        "username": "testuser",
        "hashed_password": hash_password("TestPass1!"),
        "role": "user",
        "tier": "free",
        "is_active": True,
        "email_verified": False,
        "mfa_enabled": False,
        "mfa_secret": None,
        "avatar_url": None,
        "backup_codes": None,
        "last_login_at": None,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


class TestMFALogin:
    """MFA during login flow."""

    @pytest.mark.asyncio
    async def test_login_mfa_enabled_no_code_returns_403(self, async_client, mock_session):
        user = _make_db_user(mfa_enabled=True, mfa_secret="JBSWY3DPEHPK3PXP")

        with patch("app.api.auth.user_service.authenticate_user", new_callable=AsyncMock, return_value=user):
            response = await async_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "TestPass1!"},
            )
        assert response.status_code == 403
        assert "MFA code required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_mfa_enabled_wrong_code_returns_403(self, async_client, mock_session):
        user = _make_db_user(mfa_enabled=True, mfa_secret="JBSWY3DPEHPK3PXP")

        with (
            patch("app.api.auth.user_service.authenticate_user", new_callable=AsyncMock, return_value=user),
            patch("app.api.auth.verify_totp", return_value=False),
        ):
            response = await async_client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "TestPass1!",
                    "totp_code": "000000",
                },
            )
        assert response.status_code == 403
        assert "Invalid MFA code" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_mfa_enabled_valid_code_returns_200(self, async_client, mock_session):
        user = _make_db_user(mfa_enabled=True, mfa_secret="JBSWY3DPEHPK3PXP")

        with (
            patch("app.api.auth.user_service.authenticate_user", new_callable=AsyncMock, return_value=user),
            patch("app.api.auth.verify_totp", return_value=True),
        ):
            response = await async_client.post(
                "/api/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "TestPass1!",
                    "totp_code": "123456",
                },
            )
        assert response.status_code == 200
        assert "access_token" in response.cookies


class TestTokenTampering:
    """JWT tamper resistance."""

    @pytest.mark.asyncio
    async def test_tampered_access_token_returns_401(self, async_client):
        token = create_access_token("user-001", "user", "free")
        # Flip some chars in the signature
        tampered = token[:-10] + "XXXXXXXXXX"
        response = await async_client.get(
            "/api/auth/me",
            cookies={"access_token": tampered},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_token_returns_401(self, async_client):
        response = await async_client.get(
            "/api/auth/me",
            cookies={"access_token": ""},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_garbage_token_returns_401(self, async_client):
        response = await async_client.get(
            "/api/auth/me",
            cookies={"access_token": "not.a.jwt"},
        )
        assert response.status_code == 401


class TestPasswordValidation:
    """Password minimum length."""

    @pytest.mark.asyncio
    async def test_register_password_too_short_422(self, async_client):
        response = await async_client.post(
            "/api/auth/register",
            json={"email": "a@b.com", "username": "usr", "password": "Ab1!"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_password_exactly_8_chars(self, async_client, mock_session):
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_none

        user = _make_db_user(email="a@b.com", username="usr")
        with patch("app.api.auth.user_service.register_user", new_callable=AsyncMock, return_value=user):
            response = await async_client.post(
                "/api/auth/register",
                json={"email": "a@b.com", "username": "usr", "password": "Exactly8"},
            )
        assert response.status_code == 201


class TestLoginRateLimit:
    """Rate limiting on login endpoint."""

    @pytest.mark.asyncio
    async def test_login_rate_limit(self, async_client, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        # Make 5 requests (limit is 5/minute)
        for _ in range(5):
            await async_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "wrong"},
            )

        # 6th should be rate limited
        response = await async_client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrong"},
        )
        assert response.status_code == 429


class TestExistingEndpointsUnaffected:
    """Verify existing endpoints still work without auth."""

    @pytest.mark.asyncio
    async def test_health_no_auth(self, async_client):
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_courses_no_auth(self, async_client, mock_session):
        result = MagicMock()
        result.all.return_value = []
        mock_session.execute.return_value = result

        response = await async_client.get("/api/courses")
        assert response.status_code == 200
