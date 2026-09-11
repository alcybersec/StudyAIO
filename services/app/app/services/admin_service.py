"""Admin service — user management and system metrics."""

from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import LastAdminError, UserExistsError
from app.core.utils import generate_id, normalize_email
from app.models.artifact import LectureArtifact
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.course import Course
from app.models.exam import Exam
from app.models.magic_link import MagicLink
from app.models.oauth_account import OAuthAccount
from app.models.pipeline_run import PipelineRun
from app.models.study_session import StudySession
from app.models.subscription import Subscription
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.models.user_xp import UserXP
from app.services import account_service, quota_service, user_service

logger = structlog.get_logger()

VALID_ROLES = {"admin", "user", "demo"}
VALID_TIERS = {"free", "pro"}


async def list_users(
    session: AsyncSession,
    role: str | None = None,
    tier: str | None = None,
    is_active: bool | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """List users with optional filters.

    Args:
        session: Database session.
        role: Filter by role (admin, user, demo).
        tier: Filter by tier (free, pro).
        is_active: Filter by active status.
        offset: Pagination offset.
        limit: Pagination limit.

    Returns:
        Tuple of (list of user dicts, total count).
    """
    query = select(User)
    count_query = select(func.count(User.id))

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if tier:
        query = query.where(User.tier == tier)
        count_query = count_query.where(User.tier == tier)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "role": u.role,
            "tier": u.tier,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        }
        for u in users
    ], total


def _revoke_sessions(user: User) -> None:
    """Stamp the session cutoff, killing every token minted before now.

    The same lever `user_service` pulls on a password reset, a password change
    and an MFA disable: `is_token_invalidated` compares a token's `iat` against
    this column, so the access token (15 min) and the refresh token (7 days)
    that predate the stamp both stop working immediately.
    """
    user.tokens_valid_from = datetime.now(UTC)


async def _repoint_email(session: AsyncSession, user: User, email: str) -> None:
    """Move a user's login address, invalidating anything addressed to the old one.

    Three standing routes back into the account are cut, because an email change
    is used as remediation ("this address was wrong, or is no longer under the
    user's control") and each survives the change independently:

    1. **Unused magic links.** Password-reset and verification tokens are keyed
       on user_id and validated by hash, never against the address they were
       sent to, so a link already delivered to the old inbox would otherwise
       still redeem against the corrected account.
    2. **Existing sessions.** A token minted before the change is untouched by
       the change itself, so the sessions the repoint was meant to cut would
       outlive it — up to the 7-day refresh window (issue #60).
    3. **Linked OAuth identities.** `create_or_link_oauth` matches on
       `(provider, provider_user_id)` and returns on that branch before the
       email is looked at, so whoever controls the provider account linked to
       the *old* address would otherwise keep signing straight in as this user.
       Stamping `tokens_valid_from` does nothing about that: such a sign-in
       mints a *new* token, whose `iat` is after the cutoff. Only removing the
       link closes it. So (2) and (3) are not alternatives — (2) ends the
       sessions that exist, (3) ends the ability to mint more.

    Unlinking is unconditional rather than opt-in, so the safe behaviour is the
    default one. The cost falls on the legitimate user, who re-links by signing
    in with the provider again — automatic on an account with no password once
    the provider vouches for the new address, and on a password-backed account
    the deliberate "sign in with your password instead" refusal from issue #70.

    Raises:
        UserExistsError: If `email` already belongs to a different account.
    """
    email = normalize_email(email)
    clash = await session.execute(select(User).where(User.email == email, User.id != user.id))
    if clash.scalar_one_or_none():
        raise UserExistsError("email")
    user.email = email
    # A new address is unproven until its owner follows a link.
    user.email_verified = False
    await session.execute(
        update(MagicLink)
        .where(MagicLink.user_id == user.id, MagicLink.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )
    await session.execute(delete(OAuthAccount).where(OAuthAccount.user_id == user.id))
    _revoke_sessions(user)
    # Warning, not info: silently detaching someone's provider sign-in is
    # exactly the event a confused support ticket gets read against.
    logger.warning("admin_email_repointed", user_id=user.id)


async def update_user(
    session: AsyncSession,
    user_id: str,
    role: str | None = None,
    tier: str | None = None,
    is_active: bool | None = None,
    email: str | None = None,
    acting_admin_id: str | None = None,
) -> dict | None:
    """Update user role, tier, active status, or email.

    Changing the role, reactivating the account, or repointing the email each
    revokes the user's outstanding sessions (see the comments at the call sites
    and `_repoint_email`). A tier change does not — it moves a quota, not a
    privilege, and nothing in a token depends on it.

    Args:
        session: Database session.
        user_id: UUID of the user to update.
        role: New role (admin, user, demo).
        tier: New tier (free, pro).
        is_active: New active status.
        email: New email address.
        acting_admin_id: The admin performing the update, for the audit log.

    Returns:
        Updated user dict or None if not found.

    Raises:
        UserExistsError: If email is already used by another user.
    """
    user = await session.get(User, user_id)
    if not user:
        return None

    if role is not None and role not in ("admin", "user", "demo"):
        raise ValueError(f"Invalid role: {role}")
    if tier is not None and tier not in ("free", "pro"):
        raise ValueError(f"Invalid tier: {tier}")

    # Demotion and deactivation strip an admin just as surely as deletion does.
    # Guarding only `delete_user` would leave two open paths to a locked-out
    # instance, recoverable only with direct SQL access.
    await _guard_last_admin(session, user, role=role, is_active=is_active)

    # Both are read before anything is mutated, and both compare against the
    # stored value: only a *change* revokes sessions. A PATCH that echoes the
    # user's current role or active flag — which is what a form that submits
    # every field does — must not sign them out for nothing.
    role_changed = role is not None and role != user.role
    reactivated = is_active is True and not user.is_active

    old_email = user.email
    # Compared normalized, on the same reasoning as `role_changed` above: a
    # form that submits every field echoes the address back, and an admin
    # retyping it as `Alex@Example.com` is not requesting a change. Before this
    # the raw `!=` read that as one and ran the full destructive repoint —
    # sessions revoked, OAuth unlinked, links killed, verification cleared —
    # and then stored the new casing, which (lookups being exact-match) locked
    # the user out of an account they could not reset their way back into
    # (issue #91).
    email_repointed = False
    if email is not None:
        normalized_email = normalize_email(email)
        if normalized_email != user.email:
            if normalized_email == normalize_email(user.email):
                # Case- or whitespace-only difference against a row that
                # predates the folding migration. Same mailbox, so repointing
                # would be destructive for nothing; write the canonical form so
                # the row becomes findable and move on.
                user.email = normalized_email
            else:
                await _repoint_email(session, user, normalized_email)
                email_repointed = True

    if role is not None:
        user.role = role
    if tier is not None:
        user.tier = tier
    if is_active is not None:
        user.is_active = is_active

    # Reactivation: deactivation is a revocation, so restoring access must not
    # silently restore the sessions that were revoked with it. `get_current_user`
    # and `/auth/refresh` both reject an inactive user, which makes deactivation
    # look total — but it only *suspends* the tokens. A refresh token lives 7
    # days, so an account deactivated and reactivated inside that window hands
    # the pre-deactivation session straight back, still able to mint fresh
    # access tokens. Whatever prompted the deactivation, that is not the intent.
    #
    # Role change: `require_role` reads the database, so an admin demotion binds
    # at once — but `DemoAccountMiddleware` reads `role` from the JWT claim, so
    # demoting someone to `demo` leaves them writing for the remaining life of
    # their access token. The stamp is applied to any role change, not just the
    # demotions: the claim is stale either way, and "which role transitions are
    # really downgrades" is a judgement that would have to be re-made every time
    # a role is added.
    if reactivated or role_changed:
        _revoke_sessions(user)

    user.updated_at = datetime.now(UTC)
    await session.commit()

    logger.info(
        "admin_user_updated",
        user_id=user_id,
        role=role,
        tier=tier,
        is_active=is_active,
        old_email=old_email if email_repointed else None,
        new_email=user.email if email_repointed else None,
        sessions_revoked=reactivated or role_changed or email_repointed,
        by=acting_admin_id,
    )

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "tier": user.tier,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


async def get_system_metrics(session: AsyncSession) -> dict:
    """Get aggregate system metrics for the admin dashboard.

    Args:
        session: Database session.

    Returns:
        Dict with total_users, total_artifacts, total_courses,
        pipeline_runs_24h, storage info.
    """
    total_users = (await session.execute(select(func.count(User.id)))).scalar_one()

    total_artifacts = (await session.execute(select(func.count(LectureArtifact.id)))).scalar_one()

    total_courses = (await session.execute(select(func.count(Course.id)))).scalar_one()

    # Pipeline runs in the last 24 hours
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    pipeline_runs_24h = (
        await session.execute(
            select(func.count(PipelineRun.id)).where(PipelineRun.started_at >= cutoff)
        )
    ).scalar_one()

    # Storage: total file sizes
    total_storage_bytes = (
        await session.execute(select(func.coalesce(func.sum(LectureArtifact.file_size_bytes), 0)))
    ).scalar_one()

    ai_calls_today, ai_tokens_today = await quota_service.get_global_usage_today(session)

    return {
        "total_users": total_users,
        "total_artifacts": total_artifacts,
        "total_courses": total_courses,
        "pipeline_runs_24h": pipeline_runs_24h,
        "total_storage_bytes": total_storage_bytes,
        "total_storage_mb": round(total_storage_bytes / (1024 * 1024), 2),
        # Today's AI spend on the *instance's* credentials — the same scope
        # the ceiling enforces, so the ceiling is visible before it fires
        # rather than only when a user is turned away. Users on their own
        # provider key are excluded here for the same reason they are exempt.
        "ai_calls_today": ai_calls_today,
        "ai_tokens_today": ai_tokens_today,
        "ai_calls_ceiling": int(settings.global_max_ai_calls_per_day or 0),
        "ai_tokens_ceiling": int(settings.global_max_ai_tokens_per_day or 0),
    }


async def get_user_details(session: AsyncSession, user_id: str) -> dict | None:
    """Get comprehensive details for a single user.

    Aggregates 9 sections using best-effort pattern — each section
    is wrapped in try/except so partial data is returned on failure.

    Args:
        session: Database session.
        user_id: UUID of the user.

    Returns:
        Dict with profile (required) and 8 optional sections, or None if user not found.
    """
    # Profile (required — return None if user not found)
    user = await session.get(User, user_id)
    if not user:
        return None

    profile = {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "tier": user.tier,
        "is_active": user.is_active,
        "email_verified": user.email_verified,
        "mfa_enabled": user.mfa_enabled,
        "avatar_url": user.avatar_url,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }

    # Subscription (best-effort)
    subscription = None
    try:
        result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
        sub = result.scalars().first()
        if sub:
            subscription = {
                "plan": sub.plan,
                "status": sub.status,
                "current_period_start": sub.current_period_start.isoformat()
                if sub.current_period_start
                else None,
                "current_period_end": sub.current_period_end.isoformat()
                if sub.current_period_end
                else None,
                "cancel_at_period_end": sub.cancel_at_period_end,
            }
    except Exception:
        logger.warning("user_detail_subscription_failed", user_id=user_id, exc_info=True)

    # Storage (best-effort)
    storage = None
    try:
        total_result = await session.execute(
            select(
                func.coalesce(func.sum(LectureArtifact.file_size_bytes), 0),
                func.count(LectureArtifact.id),
            ).where(LectureArtifact.user_id == user_id)
        )
        row = total_result.one()
        total_bytes = row[0]
        total_files = row[1]

        status_result = await session.execute(
            select(
                LectureArtifact.status,
                func.count(LectureArtifact.id),
            )
            .where(LectureArtifact.user_id == user_id)
            .group_by(LectureArtifact.status)
        )
        status_breakdown = {r[0]: r[1] for r in status_result.all()}

        storage = {
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2) if total_bytes else 0.0,
            "total_files": total_files,
            "status_breakdown": status_breakdown,
        }
    except Exception:
        logger.warning("user_detail_storage_failed", user_id=user_id, exc_info=True)

    # Usage (best-effort)
    usage = None
    try:
        today = date.today()
        thirty_days_ago = today - timedelta(days=30)

        today_result = await session.execute(
            select(
                func.coalesce(func.sum(UsageRecord.ai_calls_count), 0),
                func.coalesce(func.sum(UsageRecord.ai_tokens_input), 0),
                func.coalesce(func.sum(UsageRecord.ai_tokens_output), 0),
                func.coalesce(func.sum(UsageRecord.uploads_count), 0),
            ).where(
                UsageRecord.user_id == user_id,
                UsageRecord.record_date == today,
            )
        )
        today_row = today_result.one()

        month_result = await session.execute(
            select(
                func.coalesce(func.sum(UsageRecord.ai_calls_count), 0),
                func.coalesce(func.sum(UsageRecord.ai_tokens_input), 0),
                func.coalesce(func.sum(UsageRecord.ai_tokens_output), 0),
                func.coalesce(func.sum(UsageRecord.uploads_count), 0),
            ).where(
                UsageRecord.user_id == user_id,
                UsageRecord.record_date >= thirty_days_ago,
            )
        )
        month_row = month_result.one()

        usage = {
            "today": {
                "ai_calls": today_row[0],
                "tokens_input": today_row[1],
                "tokens_output": today_row[2],
                "uploads": today_row[3],
            },
            "last_30_days": {
                "ai_calls": month_row[0],
                "tokens_input": month_row[1],
                "tokens_output": month_row[2],
                "uploads": month_row[3],
            },
        }
    except Exception:
        logger.warning("user_detail_usage_failed", user_id=user_id, exc_info=True)

    # Pipeline (best-effort)
    pipeline = None
    try:
        # Total/success/failed counts via join
        pipeline_base = (
            select(
                func.count(PipelineRun.id),
                func.count(PipelineRun.id).filter(PipelineRun.status == "success"),
                func.count(PipelineRun.id).filter(PipelineRun.status == "failed"),
                func.coalesce(func.avg(PipelineRun.duration_ms), 0),
            )
            .join(LectureArtifact, PipelineRun.artifact_id == LectureArtifact.id)
            .where(LectureArtifact.user_id == user_id)
        )
        p_result = await session.execute(pipeline_base)
        p_row = p_result.one()

        # Per-stage breakdown
        stage_result = await session.execute(
            select(
                PipelineRun.stage,
                func.count(PipelineRun.id),
                func.count(PipelineRun.id).filter(PipelineRun.status == "success"),
                func.count(PipelineRun.id).filter(PipelineRun.status == "failed"),
            )
            .join(LectureArtifact, PipelineRun.artifact_id == LectureArtifact.id)
            .where(LectureArtifact.user_id == user_id)
            .group_by(PipelineRun.stage)
        )
        stages = [
            {"stage": r[0], "total": r[1], "success": r[2], "failed": r[3]}
            for r in stage_result.all()
        ]

        # Last 5 failures
        failures_result = await session.execute(
            select(
                PipelineRun.stage,
                PipelineRun.error_message,
                PipelineRun.started_at,
            )
            .join(LectureArtifact, PipelineRun.artifact_id == LectureArtifact.id)
            .where(
                LectureArtifact.user_id == user_id,
                PipelineRun.status == "failed",
            )
            .order_by(PipelineRun.started_at.desc())
            .limit(5)
        )
        recent_failures = [
            {
                "stage": r[0],
                "error_message": r[1],
                "started_at": r[2].isoformat() if r[2] else None,
            }
            for r in failures_result.all()
        ]

        pipeline = {
            "total_runs": p_row[0],
            "success_count": p_row[1],
            "failed_count": p_row[2],
            "avg_duration_ms": round(float(p_row[3])),
            "stages": stages,
            "recent_failures": recent_failures,
        }
    except Exception:
        logger.warning("user_detail_pipeline_failed", user_id=user_id, exc_info=True)

    # Study (best-effort)
    study = None
    try:
        study_result = await session.execute(
            select(
                func.coalesce(func.sum(StudySession.cards_reviewed), 0),
                func.coalesce(func.sum(StudySession.quiz_questions_answered), 0),
                func.coalesce(func.sum(StudySession.quiz_correct), 0),
                func.coalesce(func.sum(StudySession.duration_seconds), 0),
                func.count(StudySession.id),
            ).where(StudySession.user_id == user_id)
        )
        s_row = study_result.one()
        quiz_answered = s_row[1]
        quiz_correct = s_row[2]
        duration_secs = s_row[3]

        study = {
            "total_sessions": s_row[4],
            "cards_reviewed": s_row[0],
            "quiz_questions_answered": quiz_answered,
            "quiz_correct": quiz_correct,
            "quiz_accuracy_pct": round(quiz_correct / quiz_answered * 100, 1)
            if quiz_answered > 0
            else 0.0,
            "total_study_hours": round(duration_secs / 3600, 1),
        }
    except Exception:
        logger.warning("user_detail_study_failed", user_id=user_id, exc_info=True)

    # Content (best-effort)
    content = None
    try:
        courses_count = (
            await session.execute(select(func.count(Course.id)).where(Course.user_id == user_id))
        ).scalar_one()

        artifacts_count = (
            await session.execute(
                select(func.count(LectureArtifact.id)).where(LectureArtifact.user_id == user_id)
            )
        ).scalar_one()

        exams_count = (
            await session.execute(select(func.count(Exam.id)).where(Exam.user_id == user_id))
        ).scalar_one()

        # Per-course breakdown
        course_breakdown_result = await session.execute(
            select(
                Course.code,
                Course.name,
                func.count(LectureArtifact.id),
            )
            .outerjoin(LectureArtifact, LectureArtifact.course_id == Course.id)
            .where(Course.user_id == user_id)
            .group_by(Course.id, Course.code, Course.name)
        )
        per_course = [
            {"code": r[0], "name": r[1], "artifact_count": r[2]}
            for r in course_breakdown_result.all()
        ]

        content = {
            "courses_count": courses_count,
            "artifacts_count": artifacts_count,
            "exams_count": exams_count,
            "per_course": per_course,
        }
    except Exception:
        logger.warning("user_detail_content_failed", user_id=user_id, exc_info=True)

    # Gamification (best-effort)
    gamification = None
    try:
        xp_result = await session.execute(select(UserXP).where(UserXP.user_id == user_id))
        xp = xp_result.scalars().first()

        achievements_count = (
            await session.execute(
                select(func.count(UserAchievement.id)).where(UserAchievement.user_id == user_id)
            )
        ).scalar_one()

        gamification = {
            "total_xp": xp.total_xp if xp else 0,
            "level": xp.level if xp else 1,
            "achievements_count": achievements_count,
        }
    except Exception:
        logger.warning("user_detail_gamification_failed", user_id=user_id, exc_info=True)

    # Chat (best-effort)
    chat = None
    try:
        chat_result = await session.execute(
            select(
                func.count(ChatSession.id),
                func.coalesce(func.sum(ChatSession.message_count), 0),
            ).where(ChatSession.user_id == user_id)
        )
        c_row = chat_result.one()

        # Total token count via join
        token_result = await session.execute(
            select(
                func.coalesce(func.sum(ChatMessage.token_count), 0),
            )
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.user_id == user_id)
        )
        total_tokens = token_result.scalar_one()

        chat = {
            "total_sessions": c_row[0],
            "total_messages": c_row[1],
            "total_tokens": total_tokens,
        }
    except Exception:
        logger.warning("user_detail_chat_failed", user_id=user_id, exc_info=True)

    return {
        "profile": profile,
        "subscription": subscription,
        "storage": storage,
        "usage": usage,
        "pipeline": pipeline,
        "study": study,
        "content": content,
        "gamification": gamification,
        "chat": chat,
    }


# ── User provisioning and lifecycle ───────────────────────────────


async def create_user(
    session: AsyncSession,
    email: str,
    username: str,
    role: str = "user",
    tier: str = "free",
) -> tuple[User, str]:
    """Create an account with no password and mint its setup link.

    The admin never chooses or sees a password: the account is created with
    `hashed_password = None` (the same shape as an OAuth-only account) and a
    single-use link lets the new user set their own. The link is returned so
    the caller can hand it over directly — beta instances often have no working
    SMTP yet, and an admin who cannot deliver the link cannot onboard anyone.

    Args:
        session: Database session.
        email: New user's email.
        username: New user's display name.
        role: "admin" or "user".
        tier: "free" or "pro".

    Returns:
        (user, raw_setup_token)

    Raises:
        UserExistsError: If the email or username is taken.
        ValueError: If role or tier is not recognized.
    """
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
    if tier not in VALID_TIERS:
        raise ValueError(f"tier must be one of {sorted(VALID_TIERS)}")

    # Normalized on the way in, so an admin-created account cannot become the
    # case-differing twin of one that already exists (issue #91).
    email = normalize_email(email)

    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise UserExistsError("email")

    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise UserExistsError("username")

    user = User(
        id=generate_id(),
        email=email,
        username=username,
        hashed_password=None,
        role=role,
        tier=tier,
        is_active=True,
        email_verified=False,
    )
    session.add(user)
    await session.flush()

    minted = await user_service.request_password_reset(
        session, email, expires_in_hours=user_service.ACCOUNT_SETUP_TOKEN_HOURS
    )
    if minted is None:  # pragma: no cover - the user was just flushed
        raise RuntimeError("Could not mint a setup link for the new account")

    logger.info("admin_created_user", user_id=user.id, role=role, tier=tier)
    return user, minted.raw_token


async def ensure_admin(
    session: AsyncSession,
    email: str,
    username: str | None = None,
) -> tuple[User, str]:
    """Guarantee one reachable admin account and mint its set-password link.

    Targets the self-hosted default admin row if it exists at all, regardless
    of its current role, so every course and artifact it already owns keeps
    its owner and no data migration is needed. Falls back to any other admin,
    and creates one only when the instance has none.

    This is the only path to a first admin credential: `require_role("admin")`
    needs a real JWT, and the default row is created with no password and an
    undeliverable address, so neither the admin API nor a self-service reset
    can produce one.

    Where it changes something — a promotion, a reactivation, a repointed
    address — it also revokes the account's outstanding sessions, on the same
    reasoning as `update_user`. A run that changes nothing revokes nothing.

    Args:
        session: Database session.
        email: Address the admin should be reachable at.
        username: Display name, used only when creating a new account.

    Returns:
        (user, raw_setup_token)

    The caller must commit. Neither the repointed row nor the returned token
    is durable until then.

    Raises:
        UserExistsError: If `email` already belongs to a different account.
            On the create path (no existing admin), also raised if
            `username` collides with an existing account.
    """
    # Layering: the service layer should not import the API layer at module
    # scope, so this stays a local import even though there is no cycle.
    from app.api.deps import DEFAULT_ADMIN_ID

    user = await session.get(User, DEFAULT_ADMIN_ID)
    if user is None:
        result = await session.execute(
            select(User)
            .where(User.role == "admin")
            .order_by(User.created_at.nulls_last(), User.id)
            .limit(1)
        )
        user = result.scalar_one_or_none()

    if user is None:
        return await create_user(session, email, username or "admin", role="admin", tier="pro")

    # Same normalized comparison as `update_user`, and for the same reason:
    # re-running ensure-admin with the address typed in a different case is a
    # no-op, not a repoint that would unlink the admin's own OAuth sign-in and
    # revoke the console session they are running the command from (issue #91).
    email = normalize_email(email)
    was_repointed = normalize_email(user.email) != email
    was_promoted = user.role != "admin"
    was_reactivated = not user.is_active

    if was_repointed:
        await _repoint_email(session, user, email)
    elif user.email != email:
        # Pre-migration row stored with different casing: canonicalise it
        # without treating it as a change.
        user.email = email

    # Demotion or deactivation is one of the lockouts this recovers from.
    user.role = "admin"
    user.is_active = True

    # Same rule as `update_user`: a promotion or a reactivation revokes the
    # sessions that predate it, and only when something actually changed. The
    # no-op case matters here — re-running ensure-admin purely to mint a fresh
    # link on a healthy admin account is a normal operator move, and it must
    # not sign that admin out of the console they are working in. `_repoint_email`
    # stamps the cutoff itself, so the repoint case is already covered.
    if was_promoted or was_reactivated:
        _revoke_sessions(user)

    user.updated_at = datetime.now(UTC)
    await session.flush()

    minted = await user_service.request_password_reset(
        session, user.email, expires_in_hours=user_service.ACCOUNT_SETUP_TOKEN_HOURS
    )
    if minted is None:  # pragma: no cover - the row was just flushed
        raise RuntimeError("Could not mint a setup link for the admin account")

    logger.info(
        "admin_ensured",
        user_id=user.id,
        repointed=was_repointed,
        promoted=was_promoted,
        reactivated=was_reactivated,
    )
    return user, minted.raw_token


async def count_active_admins(session: AsyncSession, excluding: str | None = None) -> int:
    """Count active admin accounts, optionally ignoring one.

    Args:
        session: Database session.
        excluding: User ID to leave out of the count.

    Returns:
        Number of active admins.
    """
    query = (
        select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))
    )
    if excluding:
        query = query.where(User.id != excluding)
    return (await session.execute(query)).scalar_one()


async def _guard_last_admin(
    session: AsyncSession,
    user: User,
    role: str | None = None,
    is_active: bool | None = None,
) -> None:
    """Refuse a change that would leave the instance with no active admin.

    Args:
        session: Database session.
        user: The user being changed.
        role: Requested new role, if any.
        is_active: Requested new active status, if any.

    Raises:
        LastAdminError: If the change removes the last active admin.
    """
    if user.role != "admin" or not user.is_active:
        return  # Not currently an active admin — nothing to protect.

    losing_role = role is not None and role != "admin"
    losing_access = is_active is False
    if not (losing_role or losing_access):
        return

    if await count_active_admins(session, excluding=user.id) == 0:
        raise LastAdminError("demote" if losing_role else "deactivate")


async def delete_user(session: AsyncSession, user_id: str, acting_admin_id: str) -> dict[str, int]:
    """Permanently delete a user and everything they own.

    Args:
        session: Database session.
        user_id: The account to delete.
        acting_admin_id: The admin performing the deletion.

    Returns:
        Rows deleted per table.

    Raises:
        ValueError: If the target does not exist, is the acting admin, or is
            the last active admin.
    """
    if user_id == acting_admin_id:
        # Deleting yourself from the admin panel leaves a half-dead session and
        # is almost always a misclick; /api/auth/account is the deliberate path.
        raise ValueError("You cannot delete your own account from the admin panel")

    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    if (
        user.role == "admin"
        and user.is_active
        and await count_active_admins(session, excluding=user_id) == 0
    ):
        raise LastAdminError("delete")

    counts = await account_service.delete_user_account(session, user_id)
    logger.info("admin_deleted_user", user_id=user_id, by=acting_admin_id)
    return counts


async def issue_password_reset(session: AsyncSession, user_id: str) -> tuple[User, str]:
    """Mint a password reset link for a user on their behalf.

    Args:
        session: Database session.
        user_id: The account to reset.

    Returns:
        (user, raw_token)

    Raises:
        ValueError: If the user does not exist.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    minted = await user_service.request_password_reset(
        session, user.email, expires_in_hours=user_service.ACCOUNT_SETUP_TOKEN_HOURS
    )
    if minted is None:  # pragma: no cover - user was just loaded
        raise ValueError("User not found")

    logger.info("admin_issued_password_reset", user_id=user_id)
    return user, minted.raw_token


async def issue_email_verification(session: AsyncSession, user_id: str) -> tuple[User, str]:
    """Mint a fresh email verification link for a user.

    Args:
        session: Database session.
        user_id: The account to verify.

    Returns:
        (user, raw_token)

    Raises:
        ValueError: If the user does not exist or is already verified.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    if user.email_verified:
        raise ValueError("This email is already verified")

    minted = await user_service.create_email_verification_link(session, user)
    logger.info("admin_issued_email_verification", user_id=user_id)
    return user, minted.raw_token
