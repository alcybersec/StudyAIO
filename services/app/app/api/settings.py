"""Settings API endpoints.

Credentials are write-only here. `SettingsResponse` carries
`<key>_configured` booleans and no values, for every caller including admins:
the instance credential is configured through the environment, so there is
nothing legitimate to read back, and returning one is what issue #30 was.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default, require_ai_consent
from app.api.schemas import SettingsResponse, SettingsUpdateRequest, TestAIResponse
from app.core.cache import cache_delete, dashboard_cache_key
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.user import User
from app.services import billing_service, quota_service, settings_service

logger = structlog.get_logger()

router = APIRouter()


@router.get(
    "/settings",
    response_model=SettingsResponse,
    summary="Get current settings",
    description=(
        "Returns all readable settings (defaults merged with per-user overrides). "
        "Credentials are never returned — each is reported as a "
        "`<key>_configured` boolean."
    ),
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
    description=(
        "Partially update application settings. Only provided fields are changed. "
        "An empty or omitted credential leaves the stored one unchanged; name it "
        "in `clear_secrets` to remove it."
    ),
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
        logger.error("settings_update_failed", error=str(e), updates=list(updates.keys()))
        raise HTTPException(status_code=422, detail=str(e)) from e

    if "timezone" in updates:
        # The cached dashboard embeds the old zone's "today"; drop it.
        await cache_delete(dashboard_cache_key(str(user.id)))

    return SettingsResponse(**result)


@router.post(
    "/settings/test-ai",
    dependencies=[Depends(require_ai_consent)],
    response_model=TestAIResponse,
    summary="Test AI connection",
    description="Tests the AI connection using the current user's saved settings. Sends a minimal prompt to verify credentials work.",
)
@limiter.limit("5/minute")
async def test_ai_connection(
    request: Request,
    user: User = Depends(get_current_user_or_default),
    session: AsyncSession = Depends(get_session),
) -> TestAIResponse:
    """Test AI connection with the user's current settings."""
    from app.agents.factory import get_agent
    from app.services.settings_service import get_user_agent_config

    user_agent_config = await get_user_agent_config(session, user.id)
    # None means "StudyAIO provided" — the instance backend, which is not named
    # in the response: which provider the operator pays for is their business.
    backend = (
        user_agent_config.get("agent_backend")
        if user_agent_config
        else settings_service.STUDYAIO_BACKEND
    )
    # SEC-006 option F: answer from the availability check, never by spawning.
    if backend == "claude_code":
        available, reason = settings_service.claude_code_availability()
        if not available:
            raise HTTPException(status_code=422, detail=reason)

    # A probe on the operator's key is real spend: it counts against the
    # caller's quota and the global ceilings, and is recorded. A user testing
    # their own credentials spends their own money, so only the rate limit
    # applies.
    metered = user_agent_config is None
    if metered:
        await quota_service.check_ai_quota(session, user.id, user.tier)

    agent = get_agent(user_settings=user_agent_config)

    try:
        result = await agent.classify_lecture(
            text_preview="This is a test prompt. Respond with a valid JSON classification.",
            filename="test.pdf",
            known_courses=["TEST101"],
        )
        if metered:
            await billing_service.record_ai_call(session, user.id, agent=agent)
            await session.commit()
        return TestAIResponse(
            status="ok",
            backend=backend,
            message=f"Connection successful (confidence: {result.confidence})",
        )
    except Exception as e:
        if metered:
            await billing_service.record_ai_call(session, user.id, agent=agent)
            await session.commit()
        safe_error = await settings_service.redacted_error(session, user.id, e)
        logger.warning("test_ai_failed", error=safe_error, backend=backend)
        raise HTTPException(
            status_code=502,
            detail=f"AI connection failed ({backend}): {safe_error}",
        ) from e
