"""FastAPI dependencies for quota enforcement."""

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_or_default
from app.config import settings
from app.core.database import get_session
from app.models.user import User


def check_upload_quota() -> Callable:
    """FastAPI dependency that checks upload quota before allowing an upload."""

    async def _check(
        user: User = Depends(get_current_user_or_default),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        if not settings.self_hosted:
            from app.services import quota_service

            await quota_service.check_upload_quota(session, user.id, user.tier)
        return user

    return _check


def check_ai_quota() -> Callable:
    """FastAPI dependency that checks AI call quota."""

    async def _check(
        user: User = Depends(get_current_user_or_default),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        if not settings.self_hosted:
            from app.services import quota_service

            await quota_service.check_ai_quota(session, user.id, user.tier)
        return user

    return _check


def check_course_quota() -> Callable:
    """FastAPI dependency that checks course creation quota."""

    async def _check(
        user: User = Depends(get_current_user_or_default),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        if not settings.self_hosted:
            from app.services import quota_service

            await quota_service.check_course_quota(session, user.id, user.tier)
        return user

    return _check
