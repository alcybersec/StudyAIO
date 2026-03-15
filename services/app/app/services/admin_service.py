"""Admin service — user management and system metrics."""

from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import LectureArtifact
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.course import Course
from app.models.exam import Exam
from app.models.pipeline_run import PipelineRun
from app.models.study_session import StudySession
from app.models.subscription import Subscription
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.models.user_xp import UserXP

logger = structlog.get_logger()


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


async def update_user(
    session: AsyncSession,
    user_id: str,
    role: str | None = None,
    tier: str | None = None,
    is_active: bool | None = None,
) -> dict | None:
    """Update user role, tier, or active status.

    Args:
        session: Database session.
        user_id: UUID of the user to update.
        role: New role (admin, user, demo).
        tier: New tier (free, pro).
        is_active: New active status.

    Returns:
        Updated user dict or None if not found.
    """
    user = await session.get(User, user_id)
    if not user:
        return None

    if role is not None:
        if role not in ("admin", "user", "demo"):
            raise ValueError(f"Invalid role: {role}")
        user.role = role
    if tier is not None:
        if tier not in ("free", "pro"):
            raise ValueError(f"Invalid tier: {tier}")
        user.tier = tier
    if is_active is not None:
        user.is_active = is_active

    user.updated_at = datetime.now(UTC)
    await session.commit()

    logger.info(
        "admin_user_updated",
        user_id=user_id,
        role=role,
        tier=tier,
        is_active=is_active,
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

    return {
        "total_users": total_users,
        "total_artifacts": total_artifacts,
        "total_courses": total_courses,
        "pipeline_runs_24h": pipeline_runs_24h,
        "total_storage_bytes": total_storage_bytes,
        "total_storage_mb": round(total_storage_bytes / (1024 * 1024), 2),
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
        result = await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        sub = result.scalars().first()
        if sub:
            subscription = {
                "plan": sub.plan,
                "status": sub.status,
                "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
                "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
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
            "quiz_accuracy_pct": round(quiz_correct / quiz_answered * 100, 1) if quiz_answered > 0 else 0.0,
            "total_study_hours": round(duration_secs / 3600, 1),
        }
    except Exception:
        logger.warning("user_detail_study_failed", user_id=user_id, exc_info=True)

    # Content (best-effort)
    content = None
    try:
        courses_count = (
            await session.execute(
                select(func.count(Course.id)).where(Course.user_id == user_id)
            )
        ).scalar_one()

        artifacts_count = (
            await session.execute(
                select(func.count(LectureArtifact.id)).where(LectureArtifact.user_id == user_id)
            )
        ).scalar_one()

        exams_count = (
            await session.execute(
                select(func.count(Exam.id)).where(Exam.user_id == user_id)
            )
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
        xp_result = await session.execute(
            select(UserXP).where(UserXP.user_id == user_id)
        )
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
