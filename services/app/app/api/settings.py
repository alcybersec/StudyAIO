"""Settings API endpoints."""

import structlog
from fastapi import APIRouter, HTTPException

from app.api.schemas import SettingsResponse, SettingsUpdateRequest
from app.services import settings_service

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/settings",
    response_model=SettingsResponse,
    summary="Get current settings",
    description="Returns all configurable settings with their effective values (defaults merged with overrides).",
)
async def get_settings() -> SettingsResponse:
    """Get all current settings."""
    return SettingsResponse(**settings_service.get_all_settings())


@router.put(
    "/settings",
    response_model=SettingsResponse,
    summary="Update settings",
    description="Partially update application settings. Only provided fields are changed.",
)
async def update_settings(body: SettingsUpdateRequest) -> SettingsResponse:
    """Update one or more settings."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided to update")

    try:
        result = settings_service.update_settings(updates)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return SettingsResponse(**result)
