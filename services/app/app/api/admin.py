"""Admin API endpoints — user management and system metrics."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_session
from app.models.user import User
from app.services import admin_service

logger = structlog.get_logger()

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────


class UserResponse(BaseModel):
    """Admin view of a user."""

    id: str
    email: str
    username: str | None
    role: str
    tier: str
    is_active: bool
    created_at: str | None
    last_login_at: str | None


class UserListResponse(BaseModel):
    """Paginated user list."""

    users: list[UserResponse]
    total: int
    offset: int
    limit: int


class UserUpdateRequest(BaseModel):
    """Request to update a user's role, tier, or active status."""

    role: str | None = None
    tier: str | None = None
    is_active: bool | None = None


class SystemMetricsResponse(BaseModel):
    """Aggregate system metrics."""

    total_users: int
    total_artifacts: int
    total_courses: int
    pipeline_runs_24h: int
    total_storage_bytes: int
    total_storage_mb: float


# ── Endpoints ─────────────────────────────────────────────────────


@router.get(
    "/admin/users",
    response_model=UserListResponse,
    summary="List users",
    description="List all users with optional filters. Admin only.",
)
async def list_users(
    role: str | None = Query(None, description="Filter by role (admin, user, demo)"),
    tier: str | None = Query(None, description="Filter by tier (free, pro)"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> UserListResponse:
    """List users with optional filters (admin only)."""
    users, total = await admin_service.list_users(
        session, role=role, tier=tier, is_active=is_active, offset=offset, limit=limit
    )
    return UserListResponse(users=users, total=total, offset=offset, limit=limit)


@router.patch(
    "/admin/users/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    description="Update a user's role, tier, or active status. Admin only.",
)
async def update_user(
    user_id: str,
    body: UserUpdateRequest,
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Update user role, tier, or active status (admin only)."""
    if body.role is None and body.tier is None and body.is_active is None:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    try:
        result = await admin_service.update_user(
            session, user_id, role=body.role, tier=body.tier, is_active=body.is_active
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    if result is None:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(**result)


@router.get(
    "/admin/metrics",
    response_model=SystemMetricsResponse,
    summary="System metrics",
    description="Aggregate system metrics for the admin dashboard.",
)
async def get_system_metrics(
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> SystemMetricsResponse:
    """Get aggregate system metrics (admin only)."""
    metrics = await admin_service.get_system_metrics(session)
    return SystemMetricsResponse(**metrics)
