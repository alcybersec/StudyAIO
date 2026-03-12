"""Settings API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.api.schemas import SettingsResponse, SettingsUpdateRequest, TestAIResponse
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


@router.post(
    "/settings/test-ai",
    response_model=TestAIResponse,
    summary="Test AI connection",
    description="Tests the AI connection using the current user's saved settings. Sends a minimal prompt to verify credentials work.",
)
async def test_ai_connection(
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> TestAIResponse:
    """Test AI connection with the user's current settings."""
    from app.agents.factory import get_agent
    from app.services.settings_service import get_user_agent_config

    user_agent_config = await get_user_agent_config(session, user.id)
    agent = get_agent(user_settings=user_agent_config)

    # Determine the backend name for the response
    if user_agent_config:
        backend = user_agent_config.get(
            "agent_backend",
            settings_service.get_effective_setting("agent_backend"),
        )
    else:
        backend = settings_service.get_effective_setting("agent_backend")

    try:
        result = await agent.classify_lecture(
            text_preview="This is a test prompt. Respond with a valid JSON classification.",
            filename="test.pdf",
            known_courses=["TEST101"],
        )
        return TestAIResponse(
            status="ok",
            backend=backend,
            message=f"Connection successful (confidence: {result.confidence})",
        )
    except Exception as e:
        logger.warning("test_ai_failed", error=str(e), backend=backend)
        raise HTTPException(
            status_code=502,
            detail=f"AI connection failed ({backend}): {e}",
        ) from e
