"""Tests for core auth module (password hashing + JWT)."""

import time
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
