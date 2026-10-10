"""Day-2 study nudge: selection and content (PROD-03, GL#15).

Selection only; the hourly local-08:00 gate and the per-user Redis claim live
in ``app/pipeline/notification_tasks.py`` (ADR 0006). The 24-48h signup window
is exactly one day wide, so each user crosses their local 08:xx slot once
inside it and is nudged at most once.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import Select, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.artifact import LectureArtifact
from app.models.flashcard_review import FlashcardReview
from app.models.notification_preference import NotificationPreference
from app.models.study_session import StudySession
from app.models.user import User
from app.services import notification_service

logger = structlog.get_logger()

NUDGE_EVENT = "study_nudge"
NUDGE_MIN_AGE = timedelta(hours=24)
NUDGE_MAX_AGE = timedelta(hours=48)


@dataclass(frozen=True)
class NudgeCandidate:
    """A user due a day-2 nudge."""

    user_id: str
    has_uploads: bool


@dataclass(frozen=True)
class NudgeContent:
    """Message body and in-app target for a nudge."""

    title: str
    body: str
    href: str


def candidates_stmt(now: datetime) -> Select:
    """Build the owner-scoped selection of users who signed up 24-48h ago.

    Every sub-query is correlated to ``users.id``, so one user's activity never
    suppresses (or triggers) another's nudge. Users who opted out of
    ``study_nudge`` on every channel, inactive users, and anyone who has already
    reviewed a card or logged a study session are excluded.
    """
    opted_in = exists().where(
        NotificationPreference.user_id == User.id,
        NotificationPreference.event_type == NUDGE_EVENT,
        NotificationPreference.enabled.is_(True),
    )
    studied = exists().where(StudySession.user_id == User.id)
    reviewed = exists().where(FlashcardReview.user_id == User.id)
    has_uploads = exists().where(LectureArtifact.user_id == User.id)
    return select(User.id, has_uploads).where(
        User.is_active.is_(True),
        User.created_at <= now - NUDGE_MIN_AGE,
        User.created_at > now - NUDGE_MAX_AGE,
        opted_in,
        ~studied,
        ~reviewed,
    )


async def find_nudge_candidates(
    session: AsyncSession, now: datetime | None = None
) -> list[NudgeCandidate]:
    """Return users eligible for the day-2 nudge right now.

    The caller resolves each user's zone via the scoped
    ``settings_service.get_user_timezone`` (R-023; this module never reads the
    zone column), filters on local 08:xx and claims a per-user send slot.
    """
    rows = await session.execute(candidates_stmt(now or datetime.now(UTC)))
    return [NudgeCandidate(r[0], bool(r[1])) for r in rows.all()]


def nudge_content(has_uploads: bool) -> NudgeContent:
    """Pick the nudge copy: upload first, or start on the cards that exist."""
    if has_uploads:
        return NudgeContent(
            title="Your flashcards are ready",
            body="Your lecture is processed and your flashcards are waiting. "
            "Five minutes now is enough to start remembering it.",
            href="/study",
        )
    return NudgeContent(
        title="Upload your first lecture",
        body="Upload a lecture PDF, DOCX or PPTX and StudyAIO will turn it into "
        "a summary, flashcards and a quiz.",
        href="/upload",
    )


async def send_study_nudge(
    session: AsyncSession, user_id: str, has_uploads: bool
) -> dict[str, bool]:
    """Deliver the nudge to the in-app inbox and the user's enabled channels."""
    content = nudge_content(has_uploads)
    await notification_service.notify_inbox(
        session, user_id, kind="nudge", title=content.title, body=content.body, href=content.href
    )
    cta_url = f"{settings.app_base_url.rstrip('/')}{content.href}"
    return await notification_service.notify(
        session, user_id, NUDGE_EVENT, body=content.body, cta_url=cta_url
    )
