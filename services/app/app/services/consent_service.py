"""AI-processing consent (SEC-08, GL#38).

Lecture content is sent to an AI provider, so a user must be told so and agree
before the first AI action. The record lives on ``users``
(``ai_processing_consent_at`` / ``ai_processing_consent_version``); NULL means
not consented. The disclosure wording is versioned by
``settings.ai_consent_version``: a recorded version below the current one means
the user is asked again.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import utc_now
from app.core.exceptions import AiConsentRequiredError
from app.models.user import User

logger = structlog.get_logger()


def current_version() -> int:
    """Return the disclosure version a user must have agreed to."""
    return settings.ai_consent_version


def consent_required(user: User) -> bool:
    """Whether this user must consent (again) before any AI processing.

    The single-user operator is treated as consented: there is no one else to
    disclose to and no sign-in at which to ask.

    Returns:
        True when no consent is recorded or the recorded version is outdated.
    """
    if settings.single_user_mode:
        return False
    return (
        user.ai_processing_consent_at is None
        or user.ai_processing_consent_version is None
        or user.ai_processing_consent_version < settings.ai_consent_version
    )


def require_consent(user: User) -> None:
    """Raise unless the user has a current consent.

    Raises:
        AiConsentRequiredError: Consent is missing or outdated.
    """
    if consent_required(user):
        raise AiConsentRequiredError()


async def record_consent(session: AsyncSession, user: User) -> None:
    """Record that the user consented now, to the current disclosure version."""
    user.ai_processing_consent_at = utc_now()
    user.ai_processing_consent_version = settings.ai_consent_version
    await session.commit()
    logger.info("ai_consent_recorded", user_id=user.id, version=settings.ai_consent_version)
