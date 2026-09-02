"""Tests for auth dependency functions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import get_current_user, get_optional_user, require_plan, require_role
from app.core.auth import create_access_token, decode_token
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.models.user import User


def _make_mock_user(**overrides):
    defaults = {
        "id": "user-001",
        "email": "test@example.com",
        "username": "testuser",
        "role": "user",
        "tier": "free",
        "is_active": True,
        "tokens_valid_from": None,
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def _make_request_with_cookie(token: str | None = None):
    request = MagicMock()
    if token:
        request.cookies = {"access_token": token}
    else:
        request.cookies = {}
    return request


class TestGetCurrentUser:
    """get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        user = _make_mock_user()
        token = create_access_token("user-001", "user", "free")
        request = _make_request_with_cookie(token)

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        session.execute.return_value = result

        returned = await get_current_user(request, session)
        assert returned.id == "user-001"

    @pytest.mark.asyncio
    async def test_no_cookie_raises(self):
        request = _make_request_with_cookie(None)
        session = AsyncMock()

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await get_current_user(request, session)

    @pytest.mark.asyncio
    async def test_expired_token_raises(self):
        from unittest.mock import patch

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.jwt_access_token_expire_minutes = 0
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_secret_key.get_secret_value.return_value = (
                "test-secret-key-value-for-testing"
            )
            token = create_access_token("user-001", "user", "free")

        import time

        time.sleep(1)

        request = _make_request_with_cookie(token)
        session = AsyncMock()

        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_secret_key.get_secret_value.return_value = (
                "test-secret-key-value-for-testing"
            )
            with pytest.raises(AuthenticationError, match="expired"):
                await get_current_user(request, session)

    @pytest.mark.asyncio
    async def test_user_not_found_raises(self):
        token = create_access_token("nonexistent", "user", "free")
        request = _make_request_with_cookie(token)

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        with pytest.raises(AuthenticationError, match="User not found"):
            await get_current_user(request, session)

    @pytest.mark.asyncio
    async def test_inactive_user_raises(self):
        user = _make_mock_user(is_active=False)
        token = create_access_token("user-001", "user", "free")
        request = _make_request_with_cookie(token)

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        session.execute.return_value = result

        with pytest.raises(AuthenticationError, match="deactivated"):
            await get_current_user(request, session)

    @pytest.mark.asyncio
    async def test_refresh_token_rejected(self):
        from app.core.auth import create_refresh_token

        token = create_refresh_token("user-001")
        request = _make_request_with_cookie(token)
        session = AsyncMock()

        with pytest.raises(AuthenticationError, match="Invalid token type"):
            await get_current_user(request, session)


class TestGetCurrentUserSessionInvalidation:
    """get_current_user must reject tokens that predate users.tokens_valid_from."""

    def _session_returning(self, user):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        session.execute.return_value = result
        return session

    @pytest.mark.asyncio
    async def test_access_token_minted_before_password_reset_is_rejected(self):
        """An access token issued before the reset must not survive it."""
        token = create_access_token("user-001", "user", "free")
        request = _make_request_with_cookie(token)
        # Reset happened after the token was minted (a moment ago is enough).
        user = _make_mock_user(tokens_valid_from=datetime.now(UTC))

        with pytest.raises(AuthenticationError, match="invalidated"):
            await get_current_user(request, self._session_returning(user))

    @pytest.mark.asyncio
    async def test_access_token_minted_in_reset_second_is_rejected(self):
        """Worst case: token and reset share a second — fail closed.

        The cutoff is derived from the token's own iat so both share a
        second deterministically, regardless of when the test runs.
        """
        token = create_access_token("user-001", "user", "free")
        iat = decode_token(token)["iat"]
        request = _make_request_with_cookie(token)
        user = _make_mock_user(tokens_valid_from=datetime.fromtimestamp(iat, tz=UTC))

        with pytest.raises(AuthenticationError, match="invalidated"):
            await get_current_user(request, self._session_returning(user))

    @pytest.mark.asyncio
    async def test_access_token_minted_after_password_reset_still_works(self):
        """Tokens minted after the reset (a fresh login) keep working."""
        token = create_access_token("user-001", "user", "free")
        request = _make_request_with_cookie(token)
        user = _make_mock_user(tokens_valid_from=datetime.now(UTC) - timedelta(hours=1))

        returned = await get_current_user(request, self._session_returning(user))
        assert returned.id == "user-001"

    @pytest.mark.asyncio
    async def test_no_cutoff_keeps_tokens_working(self):
        """tokens_valid_from=None (all pre-existing users) = unrestricted."""
        token = create_access_token("user-001", "user", "free")
        request = _make_request_with_cookie(token)
        user = _make_mock_user(tokens_valid_from=None)

        returned = await get_current_user(request, self._session_returning(user))
        assert returned.id == "user-001"

    @pytest.mark.asyncio
    async def test_cutoff_from_change_password_applies_to_access_tokens(self):
        """The cutoff change_password stamps rejects older access tokens too."""
        token = create_access_token("user-001", "user", "free")
        request = _make_request_with_cookie(token)
        # change_password stamps now(); the token above was minted just before.
        user = _make_mock_user(tokens_valid_from=datetime.now(UTC))

        with pytest.raises(AuthenticationError, match="invalidated"):
            await get_current_user(request, self._session_returning(user))


class TestGetOptionalUser:
    """get_optional_user dependency."""

    @pytest.mark.asyncio
    async def test_no_cookie_returns_none(self):
        request = _make_request_with_cookie(None)
        session = AsyncMock()
        result = await get_optional_user(request, session)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        user = _make_mock_user()
        token = create_access_token("user-001", "user", "free")
        request = _make_request_with_cookie(token)

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        session.execute.return_value = result

        returned = await get_optional_user(request, session)
        assert returned.id == "user-001"


class TestRequireRole:
    """require_role dependency factory."""

    @pytest.mark.asyncio
    async def test_allowed_role_passes(self):
        user = _make_mock_user(role="admin")
        check = require_role("admin", "user")
        result = await check(user=user)
        assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_disallowed_role_raises(self):
        user = _make_mock_user(role="demo")
        check = require_role("admin")
        with pytest.raises(AuthorizationError, match="not authorized"):
            await check(user=user)


class TestRequirePlan:
    """require_plan dependency factory."""

    @pytest.mark.asyncio
    async def test_self_hosted_bypasses(self):
        user = _make_mock_user(tier="free")
        check = require_plan("pro")
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.self_hosted = True
            result = await check(user=user)
        assert result.tier == "free"  # Bypassed

    @pytest.mark.asyncio
    async def test_wrong_tier_raises_when_not_self_hosted(self):
        user = _make_mock_user(tier="free")
        check = require_plan("pro")
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.self_hosted = False
            with pytest.raises(AuthorizationError, match="not authorized"):
                await check(user=user)

    @pytest.mark.asyncio
    async def test_correct_tier_passes(self):
        user = _make_mock_user(tier="pro")
        check = require_plan("pro")
        with patch("app.api.deps.settings") as mock_settings:
            mock_settings.self_hosted = False
            result = await check(user=user)
        assert result.tier == "pro"
