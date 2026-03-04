"""Authentication utilities: password hashing, JWT creation/verification."""

import secrets
from datetime import UTC, datetime, timedelta

import jwt
import structlog
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings
from app.core.exceptions import AuthenticationError

logger = structlog.get_logger()

# Cookie names
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"

# Argon2id hasher (sensible defaults from argon2-cffi)
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password using Argon2id.

    Args:
        password: The plaintext password.

    Returns:
        Argon2id hash string.
    """
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash.

    Args:
        plain_password: The plaintext password.
        hashed_password: The stored Argon2id hash.

    Returns:
        True if the password matches.
    """
    try:
        return _hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: str, role: str, tier: str) -> str:
    """Create a short-lived JWT access token.

    Args:
        user_id: User's UUID.
        role: User role (demo/user/admin).
        tier: User tier (free/pro).

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "tier": tier,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived JWT refresh token.

    Args:
        user_id: User's UUID.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Args:
        token: The JWT string.

    Returns:
        Decoded payload dict with 'sub', 'type', 'role' (if access), etc.

    Raises:
        AuthenticationError: If the token is invalid, expired, or tampered.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise AuthenticationError("Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {e}") from e


def generate_magic_link_token() -> str:
    """Generate a cryptographically secure token for magic links.

    Returns:
        URL-safe random token string (43 chars).
    """
    return secrets.token_urlsafe(32)
