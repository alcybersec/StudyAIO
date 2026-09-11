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
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    OAuthAccountLinkRequiredError,
    OAuthEmailUnverifiedError,
    UserExistsError,
)
from app.core.security import (
    find_backup_code_hash,
    generate_backup_codes,
    hash_backup_codes,
    verify_totp,
)
from app.core.utils import generate_id, normalize_email
from app.models.magic_link import MagicLink
from app.models.oauth_account import OAuthAccount
from app.models.user import User

logger = structlog.get_logger()

# Password validation
MIN_PASSWORD_LENGTH = 8

# Email verification links live longer than reset links: nothing gates on the
# flag, so a slower journey through the inbox costs nothing.
EMAIL_VERIFICATION_TOKEN_HOURS = 24

#: A self-service reset is acted on immediately, so it expires fast.
PASSWORD_RESET_TOKEN_HOURS = 1

#: An admin-created account's first link has to survive being relayed to a
#: person who is not sitting at the keyboard.
ACCOUNT_SETUP_TOKEN_HOURS = 24


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

    # Normalized before the uniqueness check, not after: checking the raw
    # string would let `Alex@example.com` register alongside an existing
    # `alex@example.com` (issue #91).
    email = normalize_email(email)

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
    # Normalized here rather than at the route, so no caller can forget and
    # hand a user a "wrong password" for typing their own address in a
    # different case (issue #91).
    result = await session.execute(select(User).where(User.email == normalize_email(email)))
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
    """Fetch a user by email, regardless of the casing supplied.

    The address is normalized here rather than by each caller. Every route in
    is a place the bug could come back otherwise: `request_password_reset`
    returns 202 whether or not it found a row, so a miss there is silent, and
    `create_or_link_oauth` reads a miss as "no local account holds this
    address" and links an OAuth identity on the strength of it (issue #91,
    which partially reopened #70).

    Args:
        session: Database session.
        email: User email, in any casing.

    Returns:
        User or None if not found.
    """
    result = await session.execute(select(User).where(User.email == normalize_email(email)))
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
    expires_in_hours: int = PASSWORD_RESET_TOKEN_HOURS,
) -> MintedMagicLink | None:
    """Create a password reset magic link for a user.

    Invalidates any earlier unused password reset links for the same user, so
    only the most recently requested token is redeemable. Persists only the
    SHA-256 hash of the token; the raw token is returned for delivery and is
    never stored.

    Args:
        session: Database session.
        email: User email.
        expires_in_hours: Token lifetime. Defaults to one hour; admin-created
            accounts pass a longer window since the link has to be relayed.

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
        expires_at=now + timedelta(hours=expires_in_hours),
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


async def create_email_verification_link(session: AsyncSession, user: User) -> MintedMagicLink:
    """Create an email verification magic link for a user.

    Like `request_password_reset`, minting a new link does not revoke earlier
    ones — each stays valid until used or expired. Persists only the SHA-256
    hash of the token; the raw token is returned for delivery and never stored.

    Args:
        session: Database session.
        user: The user to verify.

    Returns:
        MintedMagicLink — the persisted link plus the raw token for the URL.
    """
    raw_token = generate_magic_link_token()
    link = MagicLink(
        id=generate_id(),
        user_id=user.id,
        token_hash=hash_magic_link_token(raw_token),
        link_type="email_verification",
        expires_at=datetime.now(UTC) + timedelta(hours=EMAIL_VERIFICATION_TOKEN_HOURS),
    )
    session.add(link)
    await session.flush()
    logger.info("email_verification_link_created", user_id=user.id)
    return MintedMagicLink(link=link, raw_token=raw_token)


async def deliver_email_verification(email: str, token: str) -> bool:
    """Email the verification link for a freshly minted token.

    Best-effort by design, mirroring `deliver_password_reset`: the caller has
    already responded, so a mail failure must not surface as an error.

    Call this *after* the session has been committed — otherwise the link can
    reach the user before the token row is durable.

    Args:
        email: Recipient address.
        token: The magic link token from `create_email_verification_link`.

    Returns:
        True if the email was sent.
    """
    from app.services import email_service

    verify_url = f"{settings.app_base_url.rstrip('/')}/verify-email?token={quote_plus(token)}"

    try:
        sent = await email_service.send_email_verification(email, verify_url)
    except Exception:
        logger.warning("email_verification_email_error", exc_info=True)
        sent = False

    if not sent:
        if settings.self_hosted:
            # No mail server on a single-user box is normal. Verification gates
            # nothing today, but the operator can still follow the link to set
            # the flag.
            logger.info("email_verification_link_not_emailed", verify_url=verify_url)
        else:
            # Never log the URL in SaaS — it proves control of the address.
            logger.warning("email_verification_undeliverable")

    return sent


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
        The raw backup codes, to be shown to the user once. They are not
        recoverable afterwards -- only their hashes are stored.

    Raises:
        ValueError: If user not found, or MFA is already enabled.
        AuthorizationError: If TOTP code is invalid.
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise ValueError("User not found")

    if user.mfa_enabled:
        # Enrolling over live MFA is how a hijacked session makes itself
        # durable: it swaps in a secret of its own and the account holder's
        # authenticator quietly stops working. Turning MFA off first needs a
        # current TOTP code, which a session hijacker does not have.
        raise ValueError("MFA is already enabled")

    if not verify_totp(secret, totp_code):
        raise AuthorizationError("Invalid TOTP code")

    backup_codes = generate_backup_codes()
    user.mfa_secret = secret
    user.mfa_enabled = True
    # Digests only. The column used to hold the codes themselves, which made
    # anything that could read the database an MFA bypass -- the same reasoning
    # that hashes magic link tokens (`core.auth.hash_magic_link_token`).
    user.backup_codes = json.dumps(hash_backup_codes(backup_codes))
    await session.flush()
    logger.info("mfa_enabled", user_id=user_id, backup_codes_issued=len(backup_codes))
    return backup_codes


async def consume_backup_code(
    session: AsyncSession,
    user: User,
    code: str,
) -> int | None:
    """Spend one of a user's MFA backup codes.

    Single-use, like a magic link: a matching code is removed from the account
    before this returns, so replaying it fails. Nothing is written on a
    mismatch, so a wrong guess cannot be used to burn a stranger's codes.

    Args:
        session: Database session.
        user: The already password-authenticated user. Callers must not reach
            this before verifying the password -- a backup code stands in for
            the second factor, not for the first.
        code: The code as submitted, in any form the user typed it.

    Returns:
        The number of codes left on the account, which may be 0, or None if the
        code matched nothing. A caller must not distinguish None from 0 in what
        it tells the user: "no codes left" and "wrong code" are the same answer.
    """
    if not user.backup_codes:
        return None

    try:
        stored = json.loads(user.backup_codes)
    except (TypeError, ValueError):
        # A value we cannot parse is a value we cannot authenticate against.
        # Fail closed and say so in the logs -- silently treating it as "no
        # codes" would hide a corrupted column indefinitely.
        logger.warning("backup_codes_unparseable", user_id=user.id)
        return None

    if not isinstance(stored, list):
        logger.warning("backup_codes_wrong_shape", user_id=user.id)
        return None

    hashes = [item for item in stored if isinstance(item, str)]
    matched = find_backup_code_hash(code, hashes)
    if matched is None:
        return None

    remaining = [item for item in hashes if item != matched]
    user.backup_codes = json.dumps(remaining)
    await session.flush()
    logger.info("backup_code_consumed", user_id=user.id, remaining=len(remaining))
    return len(remaining)


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


async def clear_mfa(session: AsyncSession, user_id: str) -> bool:
    """Turn MFA off for a user *without* a second factor. Admin-only.

    This is the escape hatch for the one failure `disable_mfa` cannot handle: a
    user who has lost their authenticator and their backup codes, and therefore
    cannot produce the TOTP code that turning MFA off requires. Before this
    existed the only recovery was direct SQL.

    **Why this is not attached to password reset.** Making a reset clear
    `mfa_enabled` is the convenient version, and it reduces the account to a
    single factor -- possession of the mailbox. Anyone who can read the user's
    email then walks through MFA, which is precisely the attacker MFA was added
    to stop. Recovery instead needs a human decision by someone who is not the
    requester, so it lives behind `require_role("admin")` where the identity
    check happens out of band.

    Sessions are revoked on the way out, matching `disable_mfa`: the account's
    security level just dropped, so a token minted before the drop must not
    survive it. That also signs out whoever had the account if the request was
    the result of a support-desk social-engineering attempt.

    Args:
        session: Database session.
        user_id: The account to unlock.

    Returns:
        True if MFA had been enabled, False if this was a no-op.

    Raises:
        ValueError: If user not found.
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise ValueError("User not found")

    was_enabled = bool(user.mfa_enabled)
    user.mfa_secret = None
    user.mfa_enabled = False
    user.backup_codes = None
    if was_enabled:
        # Only when something actually changed: stamping this on an account
        # that already had MFA off would sign the user out for nothing.
        user.tokens_valid_from = datetime.now(UTC)
    await session.flush()
    # Warning, not info: an administrator removing someone's second factor is
    # exactly the event an audit trail is read for.
    logger.warning("mfa_cleared_administratively", user_id=user_id, was_enabled=was_enabled)
    return was_enabled


async def create_or_link_oauth(
    session: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
    email_verified: bool = False,
    access_token: str | None = None,
    refresh_token: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Find or create a user via OAuth, linking the OAuth account.

    **Signing in with a known identity** (this provider + provider_user_id has
    been seen before) only refreshes tokens: the provider's user id is the
    identity, the email plays no part, and nothing about the account changes.

    **Everything else is an email-based decision** — creating an account for
    the address, or attaching this identity to an account that already holds
    it — and those are gated twice:

    1. ``email_verified`` must be true. An address the provider will not vouch
       for is a string the caller typed, and both decisions treat it as proof
       of identity (issue #70).
    2. An existing account **with a password** is never auto-linked. Before
       this, the identity was silently attached to whatever row held that
       email and full session cookies were minted (issue #70): an attacker who
       registered ``victim@example.com`` with their own password first would
       collect the victim's Google sign-in inside the attacker's account, keep
       their own password working, and read everything the victim then wrote.
       No round-trip proved the OAuth caller controlled the local account.

       The refusal is deliberate over the friendlier "email a confirmation
       link and link on redemption": that alternative makes linking equivalent
       to possession of the mailbox, which is exactly the thing being fixed
       here. Signing in with the password proves knowledge of a credential the
       mailbox does not hand over. Linking a provider to a password account
       therefore belongs behind an authenticated settings action; until one
       exists the user is told to sign in with their password.

    **An existing account with no password is different, and is still linked.**
    It is either OAuth-only or admin-created awaiting a setup link, and in both
    cases there is no password to bypass — the account's only route in already
    reduces to control of that mailbox (the pending setup link, or the
    provider that created it). A provider-verified address is that same proof,
    so linking is not an escalation. Where such an account has MFA enabled, the
    callback still challenges it before any cookie is set.

    Args:
        session: Database session.
        provider: OAuth provider name (e.g. "google", "github").
        provider_user_id: User ID from the provider.
        email: Email from the provider.
        email_verified: Whether the provider states it verified that address.
            Defaults to False so a caller that does not pass it fails closed.
        access_token: Provider access token.
        refresh_token: Provider refresh token.
        avatar_url: Profile picture URL from the provider.

    Returns:
        The existing or newly created User.

    Raises:
        AuthenticationError: If provider returns no email.
        OAuthEmailUnverifiedError: If the provider has not verified the email.
        OAuthAccountLinkRequiredError: If a password-backed account already
            holds that email.
    """
    if not email:
        raise AuthenticationError(f"OAuth provider '{provider}' did not return an email")

    # Normalized before any of the email-based decisions below. The lookup
    # would fold it anyway, but the create branch stores it verbatim, and a
    # provider that returns `Alex@example.com` would otherwise mint a second,
    # case-differing row for an address the instance already has (issue #91).
    email = normalize_email(email)

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

    # From here on the email decides what happens, so the provider has to
    # stand behind it. Checked *after* the known-identity branch on purpose:
    # a returning user whose provider email verification lapsed is still the
    # same identity, and locking them out would buy nothing.
    if not email_verified:
        logger.warning("oauth_email_unverified", provider=provider)
        raise OAuthEmailUnverifiedError(
            f"{provider} has not verified this email address. "
            "Verify it with the provider and try again."
        )

    # Check if user with this email exists
    user = await get_user_by_email(session, email)

    if user is not None and user.hashed_password:
        # See the docstring: proof of the provider email is not proof of this
        # account. Warning, not info -- in the takeover this is the moment the
        # attempt shows up.
        logger.warning(
            "oauth_link_refused_password_account",
            provider=provider,
            user_id=user.id,
        )
        raise OAuthAccountLinkRequiredError(
            "An account with this email address already exists and is protected by a "
            "password. Sign in with your password instead."
        )

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
            # Safe only because the `email_verified` gate above already
            # refused anything the provider would not vouch for.
            email_verified=True,
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
