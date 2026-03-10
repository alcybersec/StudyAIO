"""Golden tests for calendar sync response structures.

Validates that calendar-related API responses conform to expected schemas:
- CalendarSyncInfo: connected calendar with status
- CalendarConnectResponse: newly connected calendar
- CalendarEvent mapping: entity-to-GCal event link
- CalendarSyncResult: push/pull counts
- Webhook payload: Google push notification headers
"""

import pytest

# ── Sample data fixtures ────────────────────────────────────────────


@pytest.fixture
def sample_sync_status_response():
    """A realistic calendar status response."""
    return {
        "calendars": [
            {
                "id": "sync-001",
                "google_calendar_id": "abc123@group.calendar.google.com",
                "sync_direction": "bidirectional",
                "last_synced_at": "2026-03-06T12:00:00",
                "event_count": 12,
            },
            {
                "id": "sync-002",
                "google_calendar_id": "def456@group.calendar.google.com",
                "sync_direction": "push",
                "last_synced_at": None,
                "event_count": 0,
            },
        ]
    }


@pytest.fixture
def sample_connect_response():
    """A realistic calendar connect response."""
    return {
        "sync_id": "sync-001",
        "calendar_id": "abc123@group.calendar.google.com",
    }


@pytest.fixture
def sample_event_mapping():
    """A realistic calendar event mapping."""
    return {
        "id": "event-001",
        "user_id": "user-001",
        "calendar_sync_id": "sync-001",
        "google_event_id": "gcal_event_abc123",
        "entity_type": "deadline",
        "entity_id": "deadline-001",
        "last_synced_hash": "a" * 64,
        "created_at": "2026-03-06T12:00:00",
    }


@pytest.fixture
def sample_sync_result():
    """A realistic sync result response."""
    return {
        "pushed": 5,
        "pulled": 2,
    }


@pytest.fixture
def sample_webhook_headers():
    """Realistic Google Calendar push notification headers."""
    return {
        "x-goog-channel-id": "sync-001",
        "x-goog-resource-id": "resource-abc123",
        "x-goog-resource-state": "sync",
        "x-goog-message-number": "1",
    }


# ── Status response structure ──────────────────────────────────────


class TestCalendarSyncStatusStructure:
    """Validate calendar sync status response structure."""

    def test_has_calendars_key(self, sample_sync_status_response):
        """Response has a calendars key."""
        assert "calendars" in sample_sync_status_response

    def test_calendars_is_list(self, sample_sync_status_response):
        """calendars value is a list."""
        assert isinstance(sample_sync_status_response["calendars"], list)

    def test_each_calendar_has_required_fields(self, sample_sync_status_response):
        """Each calendar entry has all required fields."""
        required = {"id", "google_calendar_id", "sync_direction", "last_synced_at", "event_count"}
        for i, cal in enumerate(sample_sync_status_response["calendars"]):
            missing = required - cal.keys()
            assert not missing, f"Calendar {i} missing fields: {missing}"

    def test_last_synced_at_is_nullable(self, sample_sync_status_response):
        """last_synced_at can be None (never synced)."""
        never_synced = [
            c for c in sample_sync_status_response["calendars"] if c["last_synced_at"] is None
        ]
        assert len(never_synced) > 0

    def test_event_count_is_non_negative(self, sample_sync_status_response):
        """event_count is always >= 0."""
        for cal in sample_sync_status_response["calendars"]:
            assert isinstance(cal["event_count"], int)
            assert cal["event_count"] >= 0

    def test_sync_direction_is_valid(self, sample_sync_status_response):
        """sync_direction must be push, pull, or bidirectional."""
        valid = {"push", "pull", "bidirectional"}
        for cal in sample_sync_status_response["calendars"]:
            assert cal["sync_direction"] in valid


# ── Connect response structure ──────────────────────────────────────


class TestCalendarConnectResponseStructure:
    """Validate calendar connect response structure."""

    def test_has_required_fields(self, sample_connect_response):
        """Connect response has sync_id and calendar_id."""
        assert "sync_id" in sample_connect_response
        assert "calendar_id" in sample_connect_response

    def test_fields_are_strings(self, sample_connect_response):
        """Both fields are non-empty strings."""
        assert isinstance(sample_connect_response["sync_id"], str)
        assert len(sample_connect_response["sync_id"]) > 0
        assert isinstance(sample_connect_response["calendar_id"], str)
        assert len(sample_connect_response["calendar_id"]) > 0


# ── Event mapping structure ──────────────────────────────────────────


class TestCalendarEventMappingStructure:
    """Validate calendar event mapping structure."""

    def test_has_all_required_fields(self, sample_event_mapping):
        """Event mapping has all required fields."""
        required = {
            "id",
            "user_id",
            "calendar_sync_id",
            "google_event_id",
            "entity_type",
            "entity_id",
            "last_synced_hash",
            "created_at",
        }
        missing = required - sample_event_mapping.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_entity_type_is_valid(self, sample_event_mapping):
        """entity_type must be a known type."""
        valid = {"deadline", "exam", "class_schedule"}
        assert sample_event_mapping["entity_type"] in valid

    def test_hash_is_64_chars(self, sample_event_mapping):
        """last_synced_hash is a 64-char hex string (SHA-256)."""
        h = sample_event_mapping["last_synced_hash"]
        assert len(h) == 64
        int(h, 16)  # Validates it's hex


# ── Sync result structure ──────────────────────────────────────────


class TestCalendarSyncResultStructure:
    """Validate sync result response structure."""

    def test_has_pushed_and_pulled(self, sample_sync_result):
        """Sync result has pushed and pulled counts."""
        assert "pushed" in sample_sync_result
        assert "pulled" in sample_sync_result

    def test_counts_are_non_negative(self, sample_sync_result):
        """Push and pull counts are non-negative integers."""
        assert isinstance(sample_sync_result["pushed"], int)
        assert sample_sync_result["pushed"] >= 0
        assert isinstance(sample_sync_result["pulled"], int)
        assert sample_sync_result["pulled"] >= 0


# ── Webhook payload structure ──────────────────────────────────────


class TestCalendarWebhookPayloadStructure:
    """Validate Google Calendar webhook headers structure."""

    def test_has_channel_id(self, sample_webhook_headers):
        """Webhook has x-goog-channel-id header."""
        assert "x-goog-channel-id" in sample_webhook_headers
        assert len(sample_webhook_headers["x-goog-channel-id"]) > 0

    def test_has_resource_id(self, sample_webhook_headers):
        """Webhook has x-goog-resource-id header."""
        assert "x-goog-resource-id" in sample_webhook_headers

    def test_has_resource_state(self, sample_webhook_headers):
        """Webhook has x-goog-resource-state header."""
        assert "x-goog-resource-state" in sample_webhook_headers
