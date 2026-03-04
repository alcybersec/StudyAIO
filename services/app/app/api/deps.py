"""FastAPI authentication dependencies."""

from collections.abc import Callable

import structlog
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import ACCESS_TOKEN_COOKIE, decode_token
from app.core.database import get_session
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.utils import generate_id
from app.models.user import User
from app.services import user_service

logger = structlog.get_logger()

# Default admin user for self-hosted mode (matches migration backfill)
DEFAULT_ADMIN_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_ADMIN_EMAIL = "admin@studyaio.local"
DEFAULT_ADMIN_USERNAME = "admin"

# In-memory cache for the default user (avoids DB hit per request in self-hosted)
_default_user_cache: User | None = None


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Extract and validate the access token from cookies, return the User.

    Raises:
        AuthenticationError: If no token, invalid token, or user not found.
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise AuthenticationError("Not authenticated")

    payload = decode_token(token)

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload")

    user = await user_service.get_user_by_id(session, user_id)
    if not user:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("Account is deactivated")

    return user


async def get_optional_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Same as get_current_user but returns None instead of raising."""
    try:
        return await get_current_user(request, session)
    except AuthenticationError:
        return None


async def _get_or_create_default_user(session: AsyncSession) -> User:
    """Fetch or create the default admin user for self-hosted mode.

    Returns:
        The default admin User instance.
    """
    global _default_user_cache
    if _default_user_cache is not None:
        # Merge cached user into current session to avoid DetachedInstanceError
        return await session.merge(_default_user_cache, load=False)

    result = await session.execute(
        select(User).where(User.id == DEFAULT_ADMIN_ID)
    )
    user = result.scalar_one_or_none()

    if not user:
        # First admin user — find any existing admin, or create one
        result = await session.execute(
            select(User).where(User.role == "admin").limit(1)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                id=DEFAULT_ADMIN_ID,
                email=DEFAULT_ADMIN_EMAIL,
                username=DEFAULT_ADMIN_USERNAME,
                role="admin",
                tier="pro",
                is_active=True,
                email_verified=True,
            )
            session.add(user)
            await session.flush()
            logger.info("default_admin_created", user_id=user.id)

    _default_user_cache = user
    return user


async def get_current_user_or_default(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get the current authenticated user, or the default admin in self-hosted mode.

    In self-hosted mode (settings.self_hosted=True), returns the default admin
    user without requiring authentication. In SaaS mode, delegates to
    get_current_user which requires a valid JWT cookie.

    Returns:
        A User instance (always real, never None).
    """
    if settings.self_hosted:
        # Try JWT auth first (user may have logged in even in self-hosted)
        try:
            return await get_current_user(request, session)
        except AuthenticationError:
            return await _get_or_create_default_user(session)
    else:
        return await get_current_user(request, session)


def require_role(*allowed_roles: str) -> Callable:
    """Dependency factory that checks if the current user has one of the allowed roles.

    Args:
        *allowed_roles: Roles that are permitted (e.g., "admin", "user").

    Returns:
        A FastAPI dependency function.
    """

    async def _check_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise AuthorizationError(
                f"Role '{user.role}' is not authorized. Required: {', '.join(allowed_roles)}"
            )
        return user

    return _check_role


def require_plan(*allowed_tiers: str) -> Callable:
    """Dependency factory that checks tier, with self_hosted bypass.

    Args:
        *allowed_tiers: Tiers that are permitted (e.g., "pro").

    Returns:
        A FastAPI dependency function.
    """

    async def _check_plan(user: User = Depends(get_current_user)) -> User:
        # Self-hosted mode bypasses tier checks
        if settings.self_hosted:
            return user
        if user.tier not in allowed_tiers:
            raise AuthorizationError(
                f"Tier '{user.tier}' is not authorized. Required: {', '.join(allowed_tiers)}"
            )
        return user

    return _check_plan
