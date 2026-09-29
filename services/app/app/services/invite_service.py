"""Invite code issuing and redemption.

Gates registration when `REGISTRATION_MODE=invite` — the shape a closed beta
needs: hand out one code per tester, revoke the ones that leak.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import generate_magic_link_token, hash_magic_link_token
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


@dataclass(frozen=True)
class MintedInvite:
    """A freshly created email invite and its raw token.

    The token is returned exactly once, here. Only its hash is persisted, so
    there is no way to recover it afterwards — losing it means issuing a new
    invite, which is the same trade `MagicLink` makes.
    """

    invite: InviteCode
    raw_token: str


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


async def create_email_invite(
    session: AsyncSession,
    email: str,
    created_by: str | None = None,
    expires_in_days: int | None = 14,
    note: str | None = None,
) -> MintedInvite:
    """Mint an invite addressed to one email address.

    Single-use by construction. That is what makes `accepted_at` mean something:
    a multi-use invite tied to one address could be forwarded and redeemed by
    someone else, and the funnel would still record it as that person accepting.

    A shorter default expiry than shared codes (14 days vs 30) because an
    addressed invite is sent the moment it is made, so its clock starts
    immediately.

    Args:
        session: Database session.
        email: Where the invite is being sent.
        created_by: ID of the admin issuing it.
        expires_in_days: Days until expiry; None for no expiry.
        note: Free-text label, e.g. the tester's name.

    Returns:
        The persisted invite and its raw token — the token is never recoverable
        after this call returns.

    Raises:
        InviteError: If the email is blank or expires_in_days is negative.
    """
    email = (email or "").strip().lower()
    if not email:
        raise InviteError("An email address is required")
    if expires_in_days is not None and expires_in_days < 1:
        raise InviteError("expires_in_days must be at least 1")

    invite = await create_invite(
        session,
        created_by=created_by,
        max_uses=1,
        expires_in_days=expires_in_days,
        note=note,
    )
    raw_token = generate_magic_link_token()
    invite.email = email
    invite.token_hash = hash_magic_link_token(raw_token)
    await session.flush()
    # The address is logged, the token never is. An invite link in a log line is
    # a working credential for anyone who can read logs.
    logger.info("invite_email_created", invite_id=invite.id, email=email)
    return MintedInvite(invite=invite, raw_token=raw_token)


async def mark_invite_sent(session: AsyncSession, invite: InviteCode) -> None:
    """Record that the invite email actually went out.

    Kept separate from creation so a send failure leaves `sent_at` NULL rather
    than claiming a delivery that did not happen — the admin list shows created
    but unsent invites for exactly that reason.

    Args:
        session: Database session.
        invite: The invite that was delivered.
    """
    invite.sent_at = datetime.now(UTC)
    await session.flush()


async def resend_email_invite(
    session: AsyncSession,
    invite_id: str,
    expires_in_days: int | None = 14,
) -> MintedInvite | None:
    """Issue a fresh link for an existing email invite.

    **Rotates the token**, because the original is unrecoverable — only its hash
    was ever stored. That is not a limitation to work around: a resend that
    reissued the same credential would mean the old email, wherever it now sits,
    stays live forever. After this the previous link stops working.

    The expiry is renewed too. The common reason to resend is that the first
    link expired, and handing someone a fresh token that is already dead would
    be a strange thing to do.

    Expired invites are deliberately resendable; revoked and already-accepted
    ones are not. Revoking is a decision someone made, and re-inviting past it
    should be explicit rather than a side effect of a Resend button. An accepted
    invite has nothing left to give: the account exists, and the person needs a
    password reset, not an invitation.

    Args:
        session: Database session.
        invite_id: The invite to reissue.
        expires_in_days: Fresh expiry window; None for no expiry.

    Returns:
        The invite and its new raw token, or None if no such invite.

    Raises:
        InviteError: If it is a shared code, revoked, or already accepted.
    """
    invite = await get_invite(session, invite_id)
    if invite is None:
        return None
    if not invite.is_email_invite:
        raise InviteError("Only email invites can be resent")
    if invite.revoked_at is not None:
        raise InviteError("That invite was revoked")
    if invite.used_count >= invite.max_uses:
        raise InviteError("That invite has already been accepted")

    raw_token = generate_magic_link_token()
    invite.token_hash = hash_magic_link_token(raw_token)
    # Back to unsent: the row must not claim a delivery that has not happened
    # yet, and the admin list reads sent_at to show exactly that.
    invite.sent_at = None
    if expires_in_days is not None:
        invite.expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
    await session.flush()
    logger.info("invite_email_resent", invite_id=invite.id, email=invite.email)
    return MintedInvite(invite=invite, raw_token=raw_token)


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


async def redeem_invite(session: AsyncSession, code: str, email: str | None = None) -> InviteCode:
    """Validate an invite code *or* an email-invite token and consume one use.

    Takes a row lock so two simultaneous registrations cannot both spend the
    last use of a single-use code.

    Args:
        session: Database session.
        code: What the registrant supplied — a shared code like "BETA-7F3KQ2MN"
            or the raw token from an emailed invite link.
        email: The address being registered. An email invite is only redeemable
            by the address it was sent to; shared codes ignore this.

    Returns:
        The redeemed invite code.

    Raises:
        InviteError: If the code is unknown, revoked, expired, or used up.
    """
    presented = (code or "").strip()
    if not presented:
        raise InviteError("An invite code is required to register")

    # One field accepts both flavours, so the registration form and the emailed
    # link share a path. The prefix is decisive because code generation is ours:
    # every shared code starts with it, and a 43-char url-safe token never can.
    #
    # Order matters. normalize_code() uppercases, which is right for a
    # transcribed code and destroys a base64url token — so the branch is chosen
    # from the raw value before any normalisation.
    if presented.upper().startswith(CODE_PREFIX):
        lookup = InviteCode.code == normalize_code(presented)
    else:
        lookup = InviteCode.token_hash == hash_magic_link_token(presented)

    result = await session.execute(select(InviteCode).where(lookup).with_for_update())
    invite = result.scalar_one_or_none()

    # Deliberately identical messages for unknown/spent/expired/revoked, and for
    # codes and tokens alike — a distinct "that exists but is used up" tells a
    # stranger they guessed something real.
    if invite is None or not invite.is_redeemable():
        logger.info("invite_code_rejected", found=invite is not None)
        raise InviteError("That invite code is not valid")

    # An email invite names its recipient, so being sent the link is not the same
    # as being entitled to it. Without this, a forwarded link registers anyone,
    # and accepted_at still credits the person it was addressed to -- the funnel
    # would quietly attribute the signup to the wrong human.
    #
    # Checked AFTER the redeemable test so the generic rejection above stays
    # identical for unknown, spent, expired and revoked. Reaching this branch
    # requires already holding a valid token, so naming the reason tells the
    # holder nothing they could not establish anyway, and saves a real invitee
    # from silently failing when they signed up with the wrong address.
    #
    # Raised BEFORE the use is consumed: a forward used by the wrong person must
    # not burn the invitation the right person is still waiting to accept.
    if invite.email is not None:
        presented_email = (email or "").strip().lower()
        if presented_email != invite.email:
            logger.info("invite_email_mismatch", invite_id=invite.id)
            raise InviteError("That invite was sent to a different email address")

    invite.used_count += 1
    # Set once. A shared code redeemed ten times records when it was FIRST
    # accepted; overwriting would silently retarget the funnel's conversion at
    # the most recent registrant.
    if invite.accepted_at is None:
        invite.accepted_at = datetime.now(UTC)
    await session.flush()
    logger.info(
        "invite_code_redeemed",
        invite_id=invite.id,
        used_count=invite.used_count,
        max_uses=invite.max_uses,
        email_invite=invite.is_email_invite,
    )
    return invite
