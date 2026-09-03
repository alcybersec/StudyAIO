"""Admin API endpoints — user management and system metrics."""

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.cache import DASHBOARD_TTL_SECONDS, cache_get, cache_set
from app.core.database import get_session
from app.models.invite_code import InviteCode
from app.models.user import User
from app.services import admin_service, invite_service

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


# ── User Detail Schemas ──────────────────────────────────────────


class UserProfileSection(BaseModel):
    """User profile data (always present)."""

    id: str
    email: str
    username: str | None
    role: str
    tier: str
    is_active: bool
    email_verified: bool
    mfa_enabled: bool
    avatar_url: str | None
    last_login_at: str | None
    created_at: str | None


class SubscriptionSection(BaseModel):
    """User subscription info."""

    plan: str
    status: str
    current_period_start: str | None
    current_period_end: str | None
    cancel_at_period_end: bool


class StorageSection(BaseModel):
    """User storage usage."""

    total_bytes: int
    total_mb: float
    total_files: int
    status_breakdown: dict[str, int]


class UsagePeriod(BaseModel):
    """Usage metrics for a time period."""

    ai_calls: int
    tokens_input: int
    tokens_output: int
    uploads: int


class UsageSection(BaseModel):
    """User API/AI usage."""

    today: UsagePeriod
    last_30_days: UsagePeriod


class PipelineStageBreakdown(BaseModel):
    """Pipeline stats for a single stage."""

    stage: str
    total: int
    success: int
    failed: int


class PipelineFailure(BaseModel):
    """Recent pipeline failure."""

    stage: str
    error_message: str | None
    started_at: str | None


class PipelineSection(BaseModel):
    """User pipeline health."""

    total_runs: int
    success_count: int
    failed_count: int
    avg_duration_ms: int
    stages: list[PipelineStageBreakdown]
    recent_failures: list[PipelineFailure]


class StudySection(BaseModel):
    """User study activity."""

    total_sessions: int
    cards_reviewed: int
    quiz_questions_answered: int
    quiz_correct: int
    quiz_accuracy_pct: float
    total_study_hours: float


class CourseBreakdown(BaseModel):
    """Per-course content breakdown."""

    code: str
    name: str | None
    artifact_count: int


class ContentSection(BaseModel):
    """User content overview."""

    courses_count: int
    artifacts_count: int
    exams_count: int
    per_course: list[CourseBreakdown]


class GamificationSection(BaseModel):
    """User gamification stats."""

    total_xp: int
    level: int
    achievements_count: int


class ChatSection(BaseModel):
    """User chat usage."""

    total_sessions: int
    total_messages: int
    total_tokens: int


class UserDetailResponse(BaseModel):
    """Comprehensive user detail for admin view."""

    profile: UserProfileSection
    subscription: SubscriptionSection | None = None
    storage: StorageSection | None = None
    usage: UsageSection | None = None
    pipeline: PipelineSection | None = None
    study: StudySection | None = None
    content: ContentSection | None = None
    gamification: GamificationSection | None = None
    chat: ChatSection | None = None


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


@router.get(
    "/admin/users/{user_id}/details",
    response_model=UserDetailResponse,
    summary="User details",
    description="Get comprehensive details for a single user. Admin only.",
)
async def get_user_details(
    user_id: str,
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> UserDetailResponse:
    """Get comprehensive user details (admin only)."""
    cache_key = f"cache:admin:user_detail:{user_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return UserDetailResponse(**cached)

    result = await admin_service.get_user_details(session, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")

    response = UserDetailResponse(**result)
    await cache_set(cache_key, response.model_dump(mode="json"), ttl=DASHBOARD_TTL_SECONDS)
    return response


# ── Invite codes ──────────────────────────────────────────────────


class InviteCreateRequest(BaseModel):
    """Request to mint an invite code."""

    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_in_days: int | None = Field(default=30, ge=1, le=365)
    note: str | None = Field(default=None, max_length=200)


class InviteResponse(BaseModel):
    """An invite code and its redemption state."""

    id: str
    code: str
    note: str | None
    max_uses: int
    used_count: int
    uses_remaining: int
    is_redeemable: bool
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class InviteListResponse(BaseModel):
    """A list of invite codes."""

    invites: list[InviteResponse]
    total: int


def _invite_to_response(invite: InviteCode) -> InviteResponse:
    """Serialize an invite, including its derived redemption state."""
    return InviteResponse(
        id=invite.id,
        code=invite.code,
        note=invite.note,
        max_uses=invite.max_uses,
        used_count=invite.used_count,
        uses_remaining=invite.uses_remaining,
        is_redeemable=invite.is_redeemable(),
        expires_at=invite.expires_at,
        revoked_at=invite.revoked_at,
        created_at=invite.created_at,
    )


@router.post(
    "/admin/invites",
    response_model=InviteResponse,
    status_code=201,
    summary="Create an invite code",
    description="Mint a registration invite code. Admin only.",
)
async def create_invite(
    body: InviteCreateRequest,
    admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> InviteResponse:
    """Mint a new invite code (admin only)."""
    invite = await invite_service.create_invite(
        session,
        created_by=admin.id,
        max_uses=body.max_uses,
        expires_in_days=body.expires_in_days,
        note=body.note,
    )
    await session.commit()
    return _invite_to_response(invite)


@router.get(
    "/admin/invites",
    response_model=InviteListResponse,
    summary="List invite codes",
    description="List all invite codes and their usage. Admin only.",
)
async def list_invites(
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> InviteListResponse:
    """List every invite code with its redemption state (admin only)."""
    invites = await invite_service.list_invites(session)
    return InviteListResponse(
        invites=[_invite_to_response(i) for i in invites],
        total=len(invites),
    )


@router.delete(
    "/admin/invites/{invite_id}",
    response_model=InviteResponse,
    summary="Revoke an invite code",
    description="Revoke an invite code so it can no longer be redeemed. Admin only.",
)
async def revoke_invite(
    invite_id: str,
    _admin: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> InviteResponse:
    """Revoke an invite code (admin only).

    Revoking does not delete the row — the audit trail of who registered with
    which code is worth more than the tidiness.
    """
    invite = await invite_service.revoke_invite(session, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite code not found")
    await session.commit()
    return _invite_to_response(invite)
