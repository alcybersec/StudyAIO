"""Tests for core auth module (password hashing + JWT)."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.core.auth import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_magic_link_token,
    hash_password,
    is_token_invalidated,
    verify_password,
)
from app.core.exceptions import AuthenticationError


class TestPasswordHashing:
    """Password hashing with Argon2id."""

    def test_hash_password_returns_argon2_hash(self):
        hashed = hash_password("MyP@ssw0rd!")
        assert hashed.startswith("$argon2id$")

    def test_verify_correct_password(self):
        hashed = hash_password("MyP@ssw0rd!")
        assert verify_password("MyP@ssw0rd!", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("MyP@ssw0rd!")
        assert verify_password("WrongPassword", hashed) is False

    def test_different_passwords_different_hashes(self):
        h1 = hash_password("password1")
        h2 = hash_password("password2")
        assert h1 != h2

    def test_same_password_different_salts(self):
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2  # Different salts


class TestJWT:
    """JWT creation and verification."""

    def test_create_access_token_returns_string(self):
        token = create_access_token("user-123", "user", "free")
        assert isinstance(token, str)
        assert len(token) > 10

    def test_decode_access_token(self):
        token = create_access_token("user-123", "admin", "pro")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"
        assert payload["tier"] == "pro"
        assert payload["type"] == "access"

    def test_create_refresh_token_returns_string(self):
        token = create_refresh_token("user-456")
        assert isinstance(token, str)

    def test_decode_refresh_token(self):
        token = create_refresh_token("user-456")
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"
        assert "role" not in payload

    def test_expired_token_raises(self):
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.jwt_access_token_expire_minutes = 0
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_secret_key.get_secret_value.return_value = "test-secret"
            token = create_access_token("user-123", "user", "free")

        # Token created with 0 min expiry is already expired
        time.sleep(1)
        with (
            pytest.raises(AuthenticationError, match="expired"),
            patch("app.core.auth.settings") as mock_settings,
        ):
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_secret_key.get_secret_value.return_value = "test-secret"
            decode_token(token)

    def test_tampered_token_raises(self):
        token = create_access_token("user-123", "user", "free")
        # Tamper with the token
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(AuthenticationError, match="Invalid token"):
            decode_token(tampered)

    def test_wrong_secret_raises(self):
        from unittest.mock import patch

        token = create_access_token("user-123", "user", "free")
        # Decode with a different secret should fail
        with (
            pytest.raises(AuthenticationError, match="Invalid token"),
            patch("app.core.auth.settings") as mock_settings,
        ):
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_secret_key.get_secret_value.return_value = (
                "completely-wrong-secret-key-value"
            )
            decode_token(token)

    def test_token_contains_iat_and_exp(self):
        token = create_access_token("user-123", "user", "free")
        payload = decode_token(token)
        assert "iat" in payload
        assert "exp" in payload
        assert payload["exp"] > payload["iat"]


class TestIsTokenInvalidated:
    """Session cutoff checks against users.tokens_valid_from."""

    def test_no_cutoff_never_invalidates(self):
        """tokens_valid_from=None (users predating the column) = unrestricted."""
        payload = decode_token(create_access_token("user-1", "user", "free"))
        assert is_token_invalidated(payload, None) is False

    def test_token_issued_before_cutoff_is_invalid(self):
        """A token minted before the reset second must not survive it."""
        cutoff = datetime.now(UTC)
        payload = {"sub": "user-1", "type": "access", "iat": int(cutoff.timestamp()) - 3600}
        assert is_token_invalidated(payload, cutoff) is True

    def test_token_issued_after_cutoff_is_valid(self):
        """Tokens minted after the reset keep working (fresh login)."""
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        payload = {"sub": "user-1", "type": "access", "iat": int(cutoff.timestamp()) + 3600}
        assert is_token_invalidated(payload, cutoff) is False

    def test_token_minted_in_same_second_as_cutoff_is_invalid(self):
        """iat has 1s granularity: a same-second token must NOT survive.

        Deterministic by construction — the cutoff is derived from the
        token's own iat, so the two share a second regardless of timing.
        """
        token = create_access_token("user-1", "user", "free")
        payload = decode_token(token)
        cutoff = datetime.fromtimestamp(payload["iat"], tz=UTC)
        assert is_token_invalidated(payload, cutoff) is True

    def test_subsecond_cutoff_still_rejects_same_second_token(self):
        """A cutoff with microsecond precision still floors into the token's second."""
        now = datetime.now(UTC)  # e.g. ...10.742s
        payload = {"sub": "user-1", "type": "access", "iat": int(now.timestamp())}  # ...10
        assert is_token_invalidated(payload, now) is True

    def test_token_without_iat_fails_closed(self):
        """Every token we mint carries iat; one without it is rejected."""
        cutoff = datetime.now(UTC)
        assert is_token_invalidated({"sub": "user-1", "type": "access"}, cutoff) is True

    def test_naive_cutoff_datetime_treated_as_utc(self):
        """A driver that drops the tz offset must not break the comparison."""
        now_utc = datetime.now(UTC)
        naive_cutoff = now_utc.replace(tzinfo=None)
        payload = {"sub": "user-1", "type": "access", "iat": int(now_utc.timestamp()) + 10}
        assert is_token_invalidated(payload, naive_cutoff) is False


class TestMagicLinkToken:
    """Magic link token generation."""

    def test_generate_magic_link_token_length(self):
        token = generate_magic_link_token()
        assert isinstance(token, str)
        assert len(token) == 43  # base64url of 32 bytes

    def test_generate_unique_tokens(self):
        tokens = {generate_magic_link_token() for _ in range(100)}
        assert len(tokens) == 100


class TestCookieConstants:
    """Cookie name constants."""

    def test_cookie_names(self):
        assert ACCESS_TOKEN_COOKIE == "access_token"
        assert REFRESH_TOKEN_COOKIE == "refresh_token"
