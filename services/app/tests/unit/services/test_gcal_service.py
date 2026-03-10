"""Tests for Google Calendar sync service."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import CalendarSyncError
from app.services import gcal_service


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
    execute_result.scalar_one_or_none.return_value = None
    execute_result.scalar.return_value = 0
    session.execute = AsyncMock(return_value=execute_result)
    return session


@pytest.fixture
def mock_cal_sync():
    """A mock CalendarSync record."""
    sync = MagicMock()
    sync.id = "sync-001"
    sync.user_id = "user-001"
    sync.google_calendar_id = "abc@group.calendar.google.com"
    sync.sync_direction = "push"
    sync.access_token = "ya29.test-token"
    sync.refresh_token = "1//test-refresh"
    sync.last_synced_at = None
    sync.sync_token = None
    return sync


class TestComputeEventHash:
    """Tests for _compute_event_hash."""

    def test_same_input_same_hash(self):
        """Identical inputs produce identical hashes."""
        h1 = gcal_service._compute_event_hash("Test", "2026-03-10", "desc")
        h2 = gcal_service._compute_event_hash("Test", "2026-03-10", "desc")
        assert h1 == h2

    def test_different_input_different_hash(self):
        """Different inputs produce different hashes."""
        h1 = gcal_service._compute_event_hash("Test A", "2026-03-10", None)
        h2 = gcal_service._compute_event_hash("Test B", "2026-03-10", None)
        assert h1 != h2

    def test_none_description_handled(self):
        """None description doesn't cause errors."""
        h = gcal_service._compute_event_hash("Test", "2026-03-10", None)
        assert len(h) == 64  # SHA-256 hex digest


class TestConnectGoogleCalendar:
    """Tests for connect_google_calendar."""

    @pytest.mark.asyncio
    async def test_connect_creates_calendar_sync_record(self, mock_session):
        """Successfully creates a CalendarSync record."""
        mock_creds = MagicMock()
        mock_creds.token = "ya29.access"
        mock_creds.refresh_token = "1//refresh"

        mock_flow_instance = MagicMock()
        mock_flow_instance.credentials = mock_creds

        mock_flow_cls = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow_instance

        mock_service = MagicMock()
        mock_service.calendars.return_value.insert.return_value.execute.return_value = {
            "id": "new-cal@group.calendar.google.com"
        }

        mock_flow_mod = MagicMock()
        mock_flow_mod.Flow = mock_flow_cls

        mock_discovery_mod = MagicMock()
        mock_discovery_mod.build.return_value = mock_service

        with patch.dict(
            "sys.modules",
            {
                "google_auth_oauthlib.flow": mock_flow_mod,
                "google_auth_oauthlib": MagicMock(flow=mock_flow_mod),
                "google.auth.transport.requests": MagicMock(),
                "google.auth.transport": MagicMock(),
                "google.auth": MagicMock(),
                "google": MagicMock(),
                "googleapiclient.discovery": mock_discovery_mod,
                "googleapiclient": MagicMock(discovery=mock_discovery_mod),
            },
        ):
            result = await gcal_service.connect_google_calendar(
                mock_session, "user-001", "test-auth-code"
            )

        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_connect_invalid_auth_code_raises(self, mock_session):
        """Raises CalendarSyncError on invalid auth code."""
        mock_flow_instance = MagicMock()
        mock_flow_instance.fetch_token.side_effect = Exception("Invalid code")

        mock_flow_cls = MagicMock()
        mock_flow_cls.from_client_config.return_value = mock_flow_instance

        mock_flow_mod = MagicMock()
        mock_flow_mod.Flow = mock_flow_cls

        with (
            patch.dict(
                "sys.modules",
                {
                    "google_auth_oauthlib.flow": mock_flow_mod,
                    "google_auth_oauthlib": MagicMock(flow=mock_flow_mod),
                    "google.auth.transport.requests": MagicMock(),
                    "google.auth.transport": MagicMock(),
                    "google.auth": MagicMock(),
                    "google": MagicMock(),
                },
            ),
            pytest.raises(CalendarSyncError, match="Failed to exchange"),
        ):
            await gcal_service.connect_google_calendar(mock_session, "user-001", "bad-code")


class TestDisconnectCalendar:
    """Tests for disconnect_calendar."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_record(self, mock_session, mock_cal_sync):
        """Disconnecting deletes the CalendarSync record."""
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = mock_cal_sync
        mock_session.execute.return_value = execute_result

        with patch("httpx.AsyncClient") as MockClient:
            mock_http = AsyncMock()
            MockClient.return_value = mock_http
            mock_http.post = AsyncMock()

            result = await gcal_service.disconnect_calendar(mock_session, "user-001", "sync-001")

        assert result is True
        mock_session.delete.assert_awaited_once_with(mock_cal_sync)

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_returns_false(self, mock_session):
        """Returns False when sync record not found."""
        result = await gcal_service.disconnect_calendar(mock_session, "user-001", "nonexistent")
        assert result is False


class TestGetSyncStatus:
    """Tests for get_sync_status."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_syncs(self, mock_session):
        """Returns empty list when no calendars connected."""
        result = await gcal_service.get_sync_status(mock_session, "user-001")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_calendar_info(self, mock_session, mock_cal_sync):
        """Returns status info for connected calendars."""
        # First call returns the CalendarSync list
        sync_result = MagicMock()
        sync_result.scalars.return_value.all.return_value = [mock_cal_sync]

        # Second call returns event count
        count_result = MagicMock()
        count_result.scalar.return_value = 5

        mock_session.execute = AsyncMock(side_effect=[sync_result, count_result])

        result = await gcal_service.get_sync_status(mock_session, "user-001")
        assert len(result) == 1
        assert result[0]["id"] == "sync-001"
        assert result[0]["event_count"] == 5


class TestPushEvents:
    """Tests for push_events."""

    @pytest.mark.asyncio
    async def test_push_creates_google_events(self, mock_session, mock_cal_sync):
        """Push creates new events in Google Calendar."""
        # Setup: CalendarSync found, no existing events, one deadline
        sync_result = MagicMock()
        sync_result.scalar_one_or_none.return_value = mock_cal_sync

        events_result = MagicMock()
        events_result.scalars.return_value.all.return_value = []

        mock_deadline = MagicMock()
        mock_deadline.id = "deadline-001"
        mock_deadline.title = "Assignment 1"
        mock_deadline.due_date = date(2026, 4, 1)
        mock_deadline.deadline_type = "assignment"
        mock_deadline.description = "Submit essay"

        deadlines_result = MagicMock()
        deadlines_result.scalars.return_value.all.return_value = [mock_deadline]

        exams_result = MagicMock()
        exams_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[sync_result, events_result, deadlines_result, exams_result]
        )

        mock_service = MagicMock()
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "gcal-event-001"
        }
        mock_creds = MagicMock()
        mock_creds.expired = False

        with patch.object(
            gcal_service, "_build_gcal_service", return_value=(mock_service, mock_creds)
        ):
            changes = await gcal_service.push_events(mock_session, "user-001", "sync-001")

        assert changes == 1
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_skips_unchanged_events(self, mock_session, mock_cal_sync):
        """Push skips events that haven't changed (same hash)."""
        sync_result = MagicMock()
        sync_result.scalar_one_or_none.return_value = mock_cal_sync

        mock_deadline = MagicMock()
        mock_deadline.id = "deadline-001"
        mock_deadline.title = "Assignment 1"
        mock_deadline.due_date = date(2026, 4, 1)
        mock_deadline.deadline_type = "assignment"
        mock_deadline.description = "Submit essay"

        existing_hash = gcal_service._compute_event_hash(
            "Assignment 1", "2026-04-01", "Submit essay"
        )
        existing_event = MagicMock()
        existing_event.entity_type = "deadline"
        existing_event.entity_id = "deadline-001"
        existing_event.last_synced_hash = existing_hash

        events_result = MagicMock()
        events_result.scalars.return_value.all.return_value = [existing_event]

        deadlines_result = MagicMock()
        deadlines_result.scalars.return_value.all.return_value = [mock_deadline]

        exams_result = MagicMock()
        exams_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[sync_result, events_result, deadlines_result, exams_result]
        )

        mock_creds = MagicMock()
        mock_creds.expired = False

        with patch.object(
            gcal_service, "_build_gcal_service", return_value=(MagicMock(), mock_creds)
        ):
            changes = await gcal_service.push_events(mock_session, "user-001", "sync-001")

        assert changes == 0

    @pytest.mark.asyncio
    async def test_push_updates_changed_events(self, mock_session, mock_cal_sync):
        """Push updates events whose hash has changed."""
        sync_result = MagicMock()
        sync_result.scalar_one_or_none.return_value = mock_cal_sync

        mock_deadline = MagicMock()
        mock_deadline.id = "deadline-001"
        mock_deadline.title = "Assignment 1 (Updated)"
        mock_deadline.due_date = date(2026, 4, 1)
        mock_deadline.deadline_type = "assignment"
        mock_deadline.description = "Submit essay"

        existing_event = MagicMock()
        existing_event.entity_type = "deadline"
        existing_event.entity_id = "deadline-001"
        existing_event.google_event_id = "gcal-event-001"
        existing_event.last_synced_hash = "old-hash-value"

        events_result = MagicMock()
        events_result.scalars.return_value.all.return_value = [existing_event]

        deadlines_result = MagicMock()
        deadlines_result.scalars.return_value.all.return_value = [mock_deadline]

        exams_result = MagicMock()
        exams_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[sync_result, events_result, deadlines_result, exams_result]
        )

        mock_service = MagicMock()
        mock_creds = MagicMock()
        mock_creds.expired = False

        with patch.object(
            gcal_service, "_build_gcal_service", return_value=(mock_service, mock_creds)
        ):
            changes = await gcal_service.push_events(mock_session, "user-001", "sync-001")

        assert changes == 1
        mock_service.events.return_value.update.assert_called_once()


class TestPullEvents:
    """Tests for pull_events."""

    @pytest.mark.asyncio
    async def test_pull_imports_new_events(self, mock_session, mock_cal_sync):
        """Pull imports events not already tracked."""
        sync_result = MagicMock()
        sync_result.scalar_one_or_none.return_value = mock_cal_sync

        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {"id": "gcal-new-001", "summary": "Class", "start": {"date": "2026-03-15"}},
            ],
            "nextSyncToken": "sync-token-123",
        }
        mock_creds = MagicMock()
        mock_creds.expired = False

        # First: find CalendarSync, second: check if event exists
        not_found_result = MagicMock()
        not_found_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(side_effect=[sync_result, not_found_result])

        with patch.object(
            gcal_service, "_build_gcal_service", return_value=(mock_service, mock_creds)
        ):
            imported = await gcal_service.pull_events(mock_session, "user-001", "sync-001")

        assert imported == 1
        assert mock_cal_sync.sync_token == "sync-token-123"

    @pytest.mark.asyncio
    async def test_pull_incremental_uses_sync_token(self, mock_session, mock_cal_sync):
        """Pull uses existing syncToken for incremental sync."""
        mock_cal_sync.sync_token = "existing-sync-token"

        sync_result = MagicMock()
        sync_result.scalar_one_or_none.return_value = mock_cal_sync

        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [],
            "nextSyncToken": "new-sync-token",
        }
        mock_creds = MagicMock()
        mock_creds.expired = False

        mock_session.execute = AsyncMock(return_value=sync_result)

        with patch.object(
            gcal_service, "_build_gcal_service", return_value=(mock_service, mock_creds)
        ):
            await gcal_service.pull_events(mock_session, "user-001", "sync-001")

        # Verify syncToken was passed to events().list()
        call_kwargs = mock_service.events.return_value.list.call_args
        assert call_kwargs.kwargs.get("syncToken") == "existing-sync-token"


class TestSyncCalendar:
    """Tests for sync_calendar."""

    @pytest.mark.asyncio
    async def test_sync_bidirectional(self, mock_session, mock_cal_sync):
        """Bidirectional sync calls both push and pull."""
        mock_cal_sync.sync_direction = "bidirectional"

        sync_result = MagicMock()
        sync_result.scalar_one_or_none.return_value = mock_cal_sync
        mock_session.execute = AsyncMock(return_value=sync_result)

        with (
            patch.object(gcal_service, "push_events", new_callable=AsyncMock, return_value=3),
            patch.object(gcal_service, "pull_events", new_callable=AsyncMock, return_value=2),
        ):
            result = await gcal_service.sync_calendar(mock_session, "user-001", "sync-001")

        assert result == {"pushed": 3, "pulled": 2}
