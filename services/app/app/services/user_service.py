"""Business logic for user registration, authentication, and profile management."""

import json
from datetime import UTC, datetime, timedelta
from typing import NamedTuple
from urllib.parse import quote_plus

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import (
    generate_magic_link_token,
    hash_magic_link_token,
    hash_password,
    verify_password,
)
from app.core.exceptions import AuthenticationError, AuthorizationError, UserExistsError
from app.core.security import generate_backup_codes, verify_totp
from app.core.utils import generate_id
from app.models.magic_link import MagicLink
from app.models.oauth_account import OAuthAccount
from app.models.user import User

logger = structlog.get_logger()

# Password validation
MIN_PASSWORD_LENGTH = 8


class MintedMagicLink(NamedTuple):
    """A freshly minted magic link plus its raw token.

    Only the token's hash is persisted on the link; the raw value exists in
    memory solely so the caller can build the delivery URL.
    """

    link: MagicLink
    raw_token: str


def _validate_password(password: str) -> None:
    """Validate password meets minimum requirements.

    Args:
        password: The plaintext password to validate.

    Raises:
        ValueError: If password doesn't meet requirements.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


async def register_user(
    session: AsyncSession,
    email: str,
    username: str,
    password: str,
) -> User:
    """Register a new user.

    Args:
        session: Database session.
        email: User email.
        username: Display username.
        password: Plaintext password.

    Returns:
        Created User.

    Raises:
        UserExistsError: If email or username already taken.
        ValueError: If password doesn't meet requirements.
    """
    _validate_password(password)

    # Check email uniqueness
    result = await session.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise UserExistsError("email")

    # Check username uniqueness
    result = await session.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise UserExistsError("username")

    user = User(
        id=generate_id(),
        email=email,
        username=username,
        hashed_password=hash_password(password),
        role="user",
        tier="free",
    )
    session.add(user)
    await session.flush()
    logger.info("user_registered", user_id=user.id, email=email)
    return user


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Authenticate a user with email and password.

    Args:
        session: Database session.
        email: User email.
        password: Plaintext password.

    Returns:
        Authenticated User.

    Raises:
        AuthenticationError: If credentials are invalid or user is inactive.
    """
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("Invalid email or password")

    if not user.hashed_password:
        raise AuthenticationError("Invalid email or password")

    if not verify_password(password, user.hashed_password):
        raise AuthenticationError("Invalid email or password")

    if not user.is_active:
        raise AuthenticationError("Account is deactivated")

    user.last_login_at = datetime.now(UTC)
    await session.flush()
    logger.info("user_authenticated", user_id=user.id)
    return user


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    """Fetch a user by ID.

    Args:
        session: Database session.
        user_id: User UUID.

    Returns:
        User or None if not found.
    """
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Fetch a user by email.

    Args:
        session: Database session.
        email: User email.

    Returns:
        User or None if not found.
    """
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def update_profile(
    session: AsyncSession,
    user_id: str,
    username: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Update user profile fields.

    Args:
        session: Database session.
        user_id: User UUID.
        username: New username (optional).
        avatar_url: New avatar URL (optional).

    Returns:
        Updated User.

    Raises:
        ValueError: If user not found.
        UserExistsError: If new username is taken.
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise ValueError("User not found")

    if username and username != user.username:
        result = await session.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            raise UserExistsError("username")
        user.username = username

    if avatar_url is not None:
        user.avatar_url = avatar_url

    await session.flush()
    return user


async def change_password(
    session: AsyncSession,
    user_id: str,
    old_password: str,
    new_password: str,
) -> None:
    """Change a user's password.

    Args:
        session: Database session.
        user_id: User UUID.
        old_password: Current password for verification.
        new_password: New password.

    Raises:
        ValueError: If user not found or new password is too weak.
        AuthenticationError: If old password is wrong.
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise ValueError("User not found")

    if not user.hashed_password or not verify_password(old_password, user.hashed_password):
        raise AuthenticationError("Current password is incorrect")

    _validate_password(new_password)
    user.hashed_password = hash_password(new_password)
    # Revoke every token issued before now — a password change ends all
    # sessions, not just the one that requested it.
    user.tokens_valid_from = datetime.now(UTC)
    await session.flush()
    logger.info("password_changed", user_id=user_id)


async def request_password_reset(
    session: AsyncSession,
    email: str,
) -> MintedMagicLink | None:
    """Create a password reset magic link for a user.

    Invalidates any earlier unused password reset links for the same user, so
    only the most recently requested token is redeemable. Persists only the
    SHA-256 hash of the token; the raw token is returned for delivery and is
    never stored.

    Args:
        session: Database session.
        email: User email.

    Returns:
        MintedMagicLink if user exists, None otherwise (no email leak).
    """
    user = await get_user_by_email(session, email)
    if not user:
        return None

    now = datetime.now(UTC)

    # Revoke outstanding reset links so N requests never leave N usable tokens.
    await session.execute(
        update(MagicLink)
        .where(
            MagicLink.user_id == user.id,
            MagicLink.link_type == "password_reset",
            MagicLink.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw_token = generate_magic_link_token()
    link = MagicLink(
        id=generate_id(),
        user_id=user.id,
        token_hash=hash_magic_link_token(raw_token),
        link_type="password_reset",
        expires_at=now + timedelta(hours=1),
    )
    session.add(link)
    await session.flush()
    logger.info("password_reset_requested", user_id=user.id)
    return MintedMagicLink(link=link, raw_token=raw_token)


async def deliver_password_reset(email: str, token: str) -> bool:
    """Email the password reset link for a freshly minted token.

    Best-effort by design: the caller has already returned 202 to avoid leaking
    whether an account exists, so a mail failure must not surface as an error.

    Call this *after* the session has been committed — otherwise the link can
    reach the user before the token row is durable.

    Args:
        email: Recipient address.
        token: The magic link token from `request_password_reset`.

    Returns:
        True if the email was sent.
    """
    from app.services import email_service

    reset_url = f"{settings.app_base_url.rstrip('/')}/reset-password?token={quote_plus(token)}"

    try:
        sent = await email_service.send_password_reset(email, reset_url)
    except Exception:
        logger.warning("password_reset_email_error", exc_info=True)
        sent = False

    if not sent:
        if settings.self_hosted:
            # No mail server on a single-user box is normal. The link is the only
            # way back into the account, so put it where the operator can find it.
            logger.info("password_reset_link_not_emailed", reset_url=reset_url)
        else:
            # Never log the URL in SaaS — it is a bearer credential for the account.
            logger.warning("password_reset_email_undeliverable")

    return sent


async def reset_password_with_token(
    session: AsyncSession,
    token: str,
    new_password: str,
) -> None:
    """Reset a user's password using a magic link token.

    Args:
        session: Database session.
        token: Magic link token.
        new_password: New password.

    Raises:
        AuthenticationError: If token is invalid, expired, or already used.
        ValueError: If new password doesn't meet requirements.
    """
    result = await session.execute(
        select(MagicLink).where(
            MagicLink.token_hash == hash_magic_link_token(token),
            MagicLink.link_type == "password_reset",
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        raise AuthenticationError("Invalid reset token")

    if link.used_at is not None:
        raise AuthenticationError("Reset token already used")

    if datetime.now(UTC) > link.expires_at:
        raise AuthenticationError("Reset token has expired")

    _validate_password(new_password)

    # Mark token as used
    link.used_at = datetime.now(UTC)

    # Update password
    user = await get_user_by_id(session, link.user_id)
    if user:
        user.hashed_password = hash_password(new_password)
        # Revoke every token issued before now — resetting the password is
        # how a compromised account locks an attacker out, so any session
        # that predates the reset must die with it.
        user.tokens_valid_from = datetime.now(UTC)
        await session.flush()
        logger.info("password_reset_completed", user_id=user.id)


async def verify_email_token(session: AsyncSession, token: str) -> None:
    """Verify a user's email using a magic link token.

    Args:
        session: Database session.
        token: Magic link token.

    Raises:
        AuthenticationError: If token is invalid, expired, or used.
    """
    result = await session.execute(
        select(MagicLink).where(
            MagicLink.token_hash == hash_magic_link_token(token),
            MagicLink.link_type == "email_verification",
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        raise AuthenticationError("Invalid verification token")

    if link.used_at is not None:
        raise AuthenticationError("Verification token already used")

    if datetime.now(UTC) > link.expires_at:
        raise AuthenticationError("Verification token has expired")

    link.used_at = datetime.now(UTC)

    user = await get_user_by_id(session, link.user_id)
    if user:
        user.email_verified = True
        await session.flush()
        logger.info("email_verified", user_id=user.id)


async def enable_mfa(
    session: AsyncSession,
    user_id: str,
    totp_code: str,
    secret: str,
) -> list[str]:
    """Enable MFA for a user after verifying a TOTP code.

    Args:
        session: Database session.
        user_id: User UUID.
        totp_code: 6-digit TOTP code to verify.
        secret: The TOTP secret being enrolled.

    Returns:
        List of backup codes.

    Raises:
        ValueError: If user not found.
        AuthorizationError: If TOTP code is invalid.
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise ValueError("User not found")

    if not verify_totp(secret, totp_code):
        raise AuthorizationError("Invalid TOTP code")

    backup_codes = generate_backup_codes()
    user.mfa_secret = secret
    user.mfa_enabled = True
    user.backup_codes = json.dumps(backup_codes)
    await session.flush()
    logger.info("mfa_enabled", user_id=user_id)
    return backup_codes


async def disable_mfa(
    session: AsyncSession,
    user_id: str,
    totp_code: str,
) -> None:
    """Disable MFA for a user.

    Args:
        session: Database session.
        user_id: User UUID.
        totp_code: TOTP code to verify before disabling.

    Raises:
        ValueError: If user not found or MFA not enabled.
        AuthorizationError: If TOTP code is invalid.
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise ValueError("User not found")

    if not user.mfa_enabled or not user.mfa_secret:
        raise ValueError("MFA is not enabled")

    if not verify_totp(user.mfa_secret, totp_code):
        raise AuthorizationError("Invalid TOTP code")

    user.mfa_secret = None
    user.mfa_enabled = False
    user.backup_codes = None
    # Dropping the second factor lowers account security — revoke existing
    # sessions so any token stolen before this change cannot be replayed.
    user.tokens_valid_from = datetime.now(UTC)
    await session.flush()
    logger.info("mfa_disabled", user_id=user_id)


async def create_or_link_oauth(
    session: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
    access_token: str | None = None,
    refresh_token: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Find or create a user via OAuth, linking the OAuth account.

    Args:
        session: Database session.
        provider: OAuth provider name (e.g. "google", "github").
        provider_user_id: User ID from the provider.
        email: Email from the provider.
        access_token: Provider access token.
        refresh_token: Provider refresh token.
        avatar_url: Profile picture URL from the provider.

    Returns:
        The existing or newly created User.

    Raises:
        AuthenticationError: If provider returns no email.
    """
    if not email:
        raise AuthenticationError(f"OAuth provider '{provider}' did not return an email")

    # Check if OAuth account already exists
    result = await session.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    )
    existing_oauth = result.scalar_one_or_none()

    if existing_oauth:
        # Update tokens
        existing_oauth.access_token = access_token
        existing_oauth.refresh_token = refresh_token
        user = await get_user_by_id(session, existing_oauth.user_id)
        if user:
            user.last_login_at = datetime.now(UTC)
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
        await session.flush()
        return user

    # Check if user with this email exists
    user = await get_user_by_email(session, email)

    if not user:
        # Create new user
        username = email.split("@")[0]
        # Ensure unique username
        base_username = username
        counter = 1
        while True:
            result = await session.execute(select(User).where(User.username == username))
            if not result.scalar_one_or_none():
                break
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            id=generate_id(),
            email=email,
            username=username,
            role="user",
            tier="free",
            email_verified=True,  # OAuth emails are pre-verified
            avatar_url=avatar_url,
        )
        session.add(user)
        await session.flush()
        logger.info("user_created_via_oauth", user_id=user.id, provider=provider)
    elif avatar_url and not user.avatar_url:
        user.avatar_url = avatar_url

    # Link OAuth account
    oauth_account = OAuthAccount(
        id=generate_id(),
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    session.add(oauth_account)
    user.last_login_at = datetime.now(UTC)
    await session.flush()
    logger.info("oauth_account_linked", user_id=user.id, provider=provider)
    return user
