"""Settings API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.api.schemas import SettingsResponse, SettingsUpdateRequest
from app.core.database import get_session
from app.models.user import User
from app.services import settings_service

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/settings",
    response_model=SettingsResponse,
    summary="Get current settings",
    description="Returns all configurable settings with their effective values (defaults merged with per-user overrides).",
)
async def get_settings(
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    """Get all current settings for the authenticated user."""
    all_settings = await settings_service.get_user_settings(session, user.id)
    return SettingsResponse(**all_settings)


@router.put(
    "/settings",
    response_model=SettingsResponse,
    summary="Update settings",
    description="Partially update application settings. Only provided fields are changed.",
)
async def update_settings(
    body: SettingsUpdateRequest,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    """Update one or more settings for the authenticated user."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided to update")

    try:
        result = await settings_service.update_user_settings(session, user.id, updates)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return SettingsResponse(**result)
