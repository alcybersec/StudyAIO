"""Admin service — user management and system metrics."""

from datetime import datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import LectureArtifact
from app.models.course import Course
from app.models.pipeline_run import PipelineRun
from app.models.user import User

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

    user.updated_at = datetime.utcnow()
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
    cutoff = datetime.utcnow() - timedelta(hours=24)
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
