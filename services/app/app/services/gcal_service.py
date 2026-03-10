"""Google Calendar bidirectional sync service."""

import hashlib
from datetime import datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import CalendarSyncError
from app.core.utils import generate_id
from app.models.calendar_event import CalendarEvent
from app.models.calendar_sync import CalendarSync
from app.models.deadline import Deadline
from app.models.exam import Exam

logger = structlog.get_logger()


def _compute_event_hash(title: str, date_str: str, description: str | None) -> str:
    """Compute a SHA-256 hash for change detection.

    Args:
        title: Event title.
        date_str: Date as ISO string.
        description: Optional description.

    Returns:
        Hex digest of SHA-256 hash.
    """
    content = f"{title}|{date_str}|{description or ''}"
    return hashlib.sha256(content.encode()).hexdigest()


def _build_gcal_service(calendar_sync: CalendarSync):
    """Construct a Google Calendar API service from stored credentials.

    Args:
        calendar_sync: CalendarSync record with access/refresh tokens.

    Returns:
        Google Calendar API service object.

    Raises:
        CalendarSyncError: If Google API client cannot be built.
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as e:
        raise CalendarSyncError(
            "Google API client libraries not installed. "
            "Install google-api-python-client and google-auth-oauthlib."
        ) from e

    creds = Credentials(
        token=calendar_sync.access_token,
        refresh_token=calendar_sync.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret.get_secret_value(),
        scopes=settings.google_calendar_scopes.split(","),
    )

    try:
        service = build("calendar", "v3", credentials=creds)
    except Exception as e:
        raise CalendarSyncError(f"Failed to build Google Calendar service: {e}") from e

    return service, creds


async def connect_google_calendar(
    session: AsyncSession,
    user_id: str,
    auth_code: str,
) -> CalendarSync:
    """Exchange an OAuth auth code for tokens and create a CalendarSync record.

    Creates a "StudyAIO" calendar in Google Calendar if it doesn't exist.

    Args:
        session: Database session.
        user_id: The user's ID.
        auth_code: OAuth authorization code from Google consent flow.

    Returns:
        The created CalendarSync record.

    Raises:
        CalendarSyncError: If token exchange or calendar creation fails.
    """
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError as e:
        raise CalendarSyncError("Google auth libraries not installed") from e

    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret.get_secret_value(),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=settings.google_calendar_scopes.split(","),
            redirect_uri="postmessage",
        )
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
    except Exception as e:
        raise CalendarSyncError(f"Failed to exchange auth code: {e}") from e

    # Create a StudyAIO calendar in Google Calendar
    try:
        from googleapiclient.discovery import build

        service = build("calendar", "v3", credentials=creds)
        calendar_body = {
            "summary": "StudyAIO",
            "description": "Study deadlines and exams synced from StudyAIO",
            "timeZone": "UTC",
        }
        created_calendar = service.calendars().insert(body=calendar_body).execute()
        google_calendar_id = created_calendar["id"]
    except Exception as e:
        raise CalendarSyncError(f"Failed to create StudyAIO calendar: {e}") from e

    cal_sync = CalendarSync(
        id=generate_id(),
        user_id=user_id,
        google_calendar_id=google_calendar_id,
        sync_direction="push",
        access_token=creds.token,
        refresh_token=creds.refresh_token,
    )
    session.add(cal_sync)
    await session.flush()

    logger.info(
        "google_calendar_connected",
        user_id=user_id,
        sync_id=cal_sync.id,
        calendar_id=google_calendar_id,
    )
    return cal_sync


async def disconnect_calendar(
    session: AsyncSession,
    user_id: str,
    sync_id: str,
) -> bool:
    """Disconnect a Google Calendar integration.

    Revokes the token and deletes the CalendarSync record (cascade deletes events).

    Args:
        session: Database session.
        user_id: The user's ID.
        sync_id: CalendarSync record ID.

    Returns:
        True if a record was deleted.
    """
    result = await session.execute(
        select(CalendarSync).where(
            CalendarSync.id == sync_id,
            CalendarSync.user_id == user_id,
        )
    )
    cal_sync = result.scalar_one_or_none()
    if not cal_sync:
        return False

    # Best-effort token revocation
    try:
        import httpx

        await httpx.AsyncClient().post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": cal_sync.access_token},
        )
    except Exception:
        logger.warning("google_token_revoke_failed", sync_id=sync_id)

    await session.delete(cal_sync)
    await session.flush()
    logger.info("google_calendar_disconnected", user_id=user_id, sync_id=sync_id)
    return True


async def get_sync_status(
    session: AsyncSession,
    user_id: str,
) -> list[dict]:
    """List connected calendars with status info.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        List of calendar sync info dicts.
    """
    result = await session.execute(select(CalendarSync).where(CalendarSync.user_id == user_id))
    syncs = list(result.scalars().all())

    statuses = []
    for s in syncs:
        # Count linked events
        count_result = await session.execute(
            select(func.count()).where(CalendarEvent.calendar_sync_id == s.id)
        )
        event_count = count_result.scalar() or 0

        statuses.append(
            {
                "id": s.id,
                "google_calendar_id": s.google_calendar_id,
                "sync_direction": s.sync_direction,
                "last_synced_at": s.last_synced_at.isoformat() if s.last_synced_at else None,
                "event_count": event_count,
            }
        )

    return statuses


async def push_events(
    session: AsyncSession,
    user_id: str,
    sync_id: str,
) -> int:
    """Push StudyAIO deadlines and exams to Google Calendar.

    Creates new events, updates changed ones (by hash comparison), skips unchanged.

    Args:
        session: Database session.
        user_id: The user's ID.
        sync_id: CalendarSync record ID.

    Returns:
        Number of events created or updated.

    Raises:
        CalendarSyncError: If Google API calls fail.
    """
    result = await session.execute(
        select(CalendarSync).where(
            CalendarSync.id == sync_id,
            CalendarSync.user_id == user_id,
        )
    )
    cal_sync = result.scalar_one_or_none()
    if not cal_sync:
        raise CalendarSyncError(f"CalendarSync {sync_id} not found")

    service, creds = _build_gcal_service(cal_sync)

    # Refresh token if needed
    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request

            creds.refresh(Request())
            cal_sync.access_token = creds.token
            await session.flush()
        except Exception as e:
            raise CalendarSyncError(f"Token refresh failed: {e}") from e

    # Get existing event mappings
    result = await session.execute(
        select(CalendarEvent).where(CalendarEvent.calendar_sync_id == sync_id)
    )
    existing_events = {f"{e.entity_type}:{e.entity_id}": e for e in result.scalars().all()}

    changes = 0

    # Push deadlines
    result = await session.execute(
        select(Deadline).join(Deadline.course).where(Deadline.course.has(user_id=user_id))
    )
    deadlines = list(result.scalars().all())

    for deadline in deadlines:
        event_hash = _compute_event_hash(
            deadline.title, str(deadline.due_date), deadline.description
        )
        key = f"deadline:{deadline.id}"
        gcal_event_body = {
            "summary": f"[{deadline.deadline_type.upper()}] {deadline.title}",
            "description": deadline.description or "",
            "start": {"date": str(deadline.due_date)},
            "end": {"date": str(deadline.due_date)},
        }

        existing = existing_events.get(key)
        if existing:
            if existing.last_synced_hash == event_hash:
                continue  # No changes
            try:
                service.events().update(
                    calendarId=cal_sync.google_calendar_id,
                    eventId=existing.google_event_id,
                    body=gcal_event_body,
                ).execute()
                existing.last_synced_hash = event_hash
                changes += 1
            except Exception as e:
                logger.warning("gcal_push_update_failed", deadline_id=deadline.id, error=str(e))
        else:
            try:
                created = (
                    service.events()
                    .insert(
                        calendarId=cal_sync.google_calendar_id,
                        body=gcal_event_body,
                    )
                    .execute()
                )
                cal_event = CalendarEvent(
                    id=generate_id(),
                    user_id=user_id,
                    calendar_sync_id=sync_id,
                    google_event_id=created["id"],
                    entity_type="deadline",
                    entity_id=deadline.id,
                    last_synced_hash=event_hash,
                )
                session.add(cal_event)
                changes += 1
            except Exception as e:
                logger.warning("gcal_push_create_failed", deadline_id=deadline.id, error=str(e))

    # Push exams
    result = await session.execute(
        select(Exam).where(
            Exam.user_id == user_id,
            Exam.status == "active",
        )
    )
    exams = list(result.scalars().all())

    for exam in exams:
        exam_date_str = exam.exam_date.isoformat()
        event_hash = _compute_event_hash(exam.title, exam_date_str, None)
        key = f"exam:{exam.id}"
        gcal_event_body = {
            "summary": f"[EXAM] {exam.title}",
            "description": f"Target mastery: {exam.target_mastery_pct}%",
            "start": {"dateTime": exam_date_str, "timeZone": "UTC"},
            "end": {"dateTime": exam_date_str, "timeZone": "UTC"},
        }

        existing = existing_events.get(key)
        if existing:
            if existing.last_synced_hash == event_hash:
                continue
            try:
                service.events().update(
                    calendarId=cal_sync.google_calendar_id,
                    eventId=existing.google_event_id,
                    body=gcal_event_body,
                ).execute()
                existing.last_synced_hash = event_hash
                changes += 1
            except Exception as e:
                logger.warning("gcal_push_exam_update_failed", exam_id=exam.id, error=str(e))
        else:
            try:
                created = (
                    service.events()
                    .insert(
                        calendarId=cal_sync.google_calendar_id,
                        body=gcal_event_body,
                    )
                    .execute()
                )
                cal_event = CalendarEvent(
                    id=generate_id(),
                    user_id=user_id,
                    calendar_sync_id=sync_id,
                    google_event_id=created["id"],
                    entity_type="exam",
                    entity_id=exam.id,
                    last_synced_hash=event_hash,
                )
                session.add(cal_event)
                changes += 1
            except Exception as e:
                logger.warning("gcal_push_exam_create_failed", exam_id=exam.id, error=str(e))

    cal_sync.last_synced_at = datetime.utcnow()
    await session.flush()

    logger.info("gcal_push_complete", user_id=user_id, sync_id=sync_id, changes=changes)
    return changes


async def pull_events(
    session: AsyncSession,
    user_id: str,
    sync_id: str,
) -> int:
    """Pull events from Google Calendar using incremental sync.

    Uses syncToken for efficient incremental sync when available.

    Args:
        session: Database session.
        user_id: The user's ID.
        sync_id: CalendarSync record ID.

    Returns:
        Number of events imported.

    Raises:
        CalendarSyncError: If Google API calls fail.
    """
    result = await session.execute(
        select(CalendarSync).where(
            CalendarSync.id == sync_id,
            CalendarSync.user_id == user_id,
        )
    )
    cal_sync = result.scalar_one_or_none()
    if not cal_sync:
        raise CalendarSyncError(f"CalendarSync {sync_id} not found")

    service, creds = _build_gcal_service(cal_sync)

    # Refresh token if needed
    if creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request

            creds.refresh(Request())
            cal_sync.access_token = creds.token
            await session.flush()
        except Exception as e:
            raise CalendarSyncError(f"Token refresh failed: {e}") from e

    try:
        kwargs = {"calendarId": cal_sync.google_calendar_id}
        if cal_sync.sync_token:
            kwargs["syncToken"] = cal_sync.sync_token
        else:
            kwargs["timeMin"] = datetime.utcnow().isoformat() + "Z"

        events_result = service.events().list(**kwargs).execute()
    except Exception as e:
        # If sync token is invalid, do a full sync
        if cal_sync.sync_token:
            cal_sync.sync_token = None
            await session.flush()
            logger.warning("gcal_sync_token_expired", sync_id=sync_id)
        raise CalendarSyncError(f"Failed to list events: {e}") from e

    new_sync_token = events_result.get("nextSyncToken")
    if new_sync_token:
        cal_sync.sync_token = new_sync_token

    imported = 0
    items = events_result.get("items", [])

    for item in items:
        google_event_id = item.get("id", "")
        if not google_event_id:
            continue

        # Check if we already track this event
        result = await session.execute(
            select(CalendarEvent).where(
                CalendarEvent.calendar_sync_id == sync_id,
                CalendarEvent.google_event_id == google_event_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            continue  # Already tracked

        summary = item.get("summary", "")
        event_hash = _compute_event_hash(
            summary,
            item.get("start", {}).get("date", item.get("start", {}).get("dateTime", "")),
            item.get("description"),
        )

        cal_event = CalendarEvent(
            id=generate_id(),
            user_id=user_id,
            calendar_sync_id=sync_id,
            google_event_id=google_event_id,
            entity_type="class_schedule",
            entity_id=generate_id(),  # No local entity yet
            last_synced_hash=event_hash,
        )
        session.add(cal_event)
        imported += 1

    cal_sync.last_synced_at = datetime.utcnow()
    await session.flush()

    logger.info("gcal_pull_complete", user_id=user_id, sync_id=sync_id, imported=imported)
    return imported


async def sync_calendar(
    session: AsyncSession,
    user_id: str,
    sync_id: str,
) -> dict:
    """Orchestrate push + pull based on sync_direction.

    Args:
        session: Database session.
        user_id: The user's ID.
        sync_id: CalendarSync record ID.

    Returns:
        Dict with pushed and pulled counts.
    """
    result = await session.execute(
        select(CalendarSync).where(
            CalendarSync.id == sync_id,
            CalendarSync.user_id == user_id,
        )
    )
    cal_sync = result.scalar_one_or_none()
    if not cal_sync:
        raise CalendarSyncError(f"CalendarSync {sync_id} not found")

    pushed = 0
    pulled = 0

    if cal_sync.sync_direction in ("push", "bidirectional"):
        try:
            pushed = await push_events(session, user_id, sync_id)
        except CalendarSyncError:
            logger.warning("gcal_sync_push_failed", sync_id=sync_id, exc_info=True)

    if cal_sync.sync_direction in ("pull", "bidirectional"):
        try:
            pulled = await pull_events(session, user_id, sync_id)
        except CalendarSyncError:
            logger.warning("gcal_sync_pull_failed", sync_id=sync_id, exc_info=True)

    return {"pushed": pushed, "pulled": pulled}


async def handle_gcal_webhook(
    session: AsyncSession,
    channel_id: str,
    resource_id: str,
) -> None:
    """Process a Google Calendar push notification.

    Triggers a pull sync for the calendar associated with the channel.

    Args:
        session: Database session.
        channel_id: The notification channel ID (maps to sync_id).
        resource_id: The Google resource ID.
    """
    result = await session.execute(select(CalendarSync).where(CalendarSync.id == channel_id))
    cal_sync = result.scalar_one_or_none()
    if not cal_sync:
        logger.warning("gcal_webhook_unknown_channel", channel_id=channel_id)
        return

    try:
        await pull_events(session, cal_sync.user_id, cal_sync.id)
    except CalendarSyncError:
        logger.warning("gcal_webhook_pull_failed", sync_id=cal_sync.id, exc_info=True)
