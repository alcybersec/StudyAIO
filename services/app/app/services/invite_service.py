"""Invite code issuing and redemption.

Gates registration when `REGISTRATION_MODE=invite` — the shape a closed beta
needs: hand out one code per tester, revoke the ones that leak.
"""

import secrets
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InviteError
from app.core.utils import generate_id
from app.models.invite_code import InviteCode

logger = structlog.get_logger()

# Unambiguous alphabet — no 0/O, 1/I/L. Codes get read off a screen and typed
# by hand, so the pairs people confuse are worth losing.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
CODE_PREFIX = "BETA-"

MAX_CODE_GENERATION_ATTEMPTS = 5


def generate_code() -> str:
    """Generate a random, human-transcribable invite code.

    Returns:
        A code like "BETA-7F3KQ2MN".
    """
    body = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return f"{CODE_PREFIX}{body}"


def normalize_code(code: str) -> str:
    """Normalize a user-supplied code for lookup.

    Uppercases and strips surrounding whitespace so a tester pasting
    " beta-7f3kq2mn " still matches.

    Args:
        code: The raw code as typed.

    Returns:
        The normalized code.
    """
    return code.strip().upper()


async def create_invite(
    session: AsyncSession,
    created_by: str | None = None,
    max_uses: int = 1,
    expires_in_days: int | None = 30,
    note: str | None = None,
) -> InviteCode:
    """Mint a new invite code.

    Args:
        session: Database session.
        created_by: ID of the admin issuing the code.
        max_uses: How many registrations the code allows.
        expires_in_days: Days until expiry; None for no expiry.
        note: Free-text label, e.g. the tester's name.

    Returns:
        The persisted invite code.

    Raises:
        InviteError: If max_uses is below 1 or expires_in_days is negative.
    """
    if max_uses < 1:
        raise InviteError("max_uses must be at least 1")
    if expires_in_days is not None and expires_in_days < 1:
        raise InviteError("expires_in_days must be at least 1")

    expires_at = (
        datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days is not None else None
    )

    # Retry on the astronomically unlikely collision rather than 500.
    for _ in range(MAX_CODE_GENERATION_ATTEMPTS):
        code = generate_code()
        existing = await session.execute(select(InviteCode).where(InviteCode.code == code))
        if existing.scalar_one_or_none() is None:
            break
    else:  # pragma: no cover - requires 5 consecutive collisions
        raise InviteError("Could not generate a unique invite code")

    invite = InviteCode(
        id=generate_id(),
        code=code,
        created_by=created_by,
        note=note,
        max_uses=max_uses,
        expires_at=expires_at,
    )
    session.add(invite)
    await session.flush()
    logger.info("invite_code_created", invite_id=invite.id, max_uses=max_uses)
    return invite


async def list_invites(session: AsyncSession) -> list[InviteCode]:
    """List every invite code, newest first.

    Args:
        session: Database session.

    Returns:
        All invite codes.
    """
    result = await session.execute(select(InviteCode).order_by(InviteCode.created_at.desc()))
    return list(result.scalars().all())


async def get_invite(session: AsyncSession, invite_id: str) -> InviteCode | None:
    """Fetch one invite code by ID.

    Args:
        session: Database session.
        invite_id: The invite's ID.

    Returns:
        The invite, or None.
    """
    result = await session.execute(select(InviteCode).where(InviteCode.id == invite_id))
    return result.scalar_one_or_none()


async def revoke_invite(session: AsyncSession, invite_id: str) -> InviteCode | None:
    """Revoke an invite code so it can no longer be redeemed.

    Idempotent — revoking an already-revoked code keeps the original timestamp.

    Args:
        session: Database session.
        invite_id: The invite's ID.

    Returns:
        The revoked invite, or None if not found.
    """
    invite = await get_invite(session, invite_id)
    if invite is None:
        return None
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(UTC)
        await session.flush()
        logger.info("invite_code_revoked", invite_id=invite_id)
    return invite


async def redeem_invite(session: AsyncSession, code: str) -> InviteCode:
    """Validate an invite code and consume one use.

    Takes a row lock so two simultaneous registrations cannot both spend the
    last use of a single-use code.

    Args:
        session: Database session.
        code: The code as supplied by the registrant.

    Returns:
        The redeemed invite code.

    Raises:
        InviteError: If the code is unknown, revoked, expired, or used up.
    """
    if not code or not code.strip():
        raise InviteError("An invite code is required to register")

    result = await session.execute(
        select(InviteCode).where(InviteCode.code == normalize_code(code)).with_for_update()
    )
    invite = result.scalar_one_or_none()

    # Deliberately identical messages for unknown/spent/expired codes — a
    # distinct "that code exists but is used up" tells a stranger they guessed
    # a real code.
    if invite is None or not invite.is_redeemable():
        logger.info("invite_code_rejected", found=invite is not None)
        raise InviteError("That invite code is not valid")

    invite.used_count += 1
    await session.flush()
    logger.info(
        "invite_code_redeemed",
        invite_id=invite.id,
        used_count=invite.used_count,
        max_uses=invite.max_uses,
    )
    return invite
