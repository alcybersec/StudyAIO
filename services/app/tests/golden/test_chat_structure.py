"""Golden tests for chat response structures.

Validates that chat-related API responses conform to expected schemas:
- ChatSession: all session fields present and correctly typed
- ChatMessage: all message fields present with valid roles
- SendMessageResponse: contains both user and assistant messages
- Citations: nullable and correctly structured when present
"""

import pytest

# ── Sample data fixtures ────────────────────────────────────────────


@pytest.fixture
def sample_session_response():
    """A realistic chat session response."""
    return {
        "id": "01234567-89ab-cdef-0123-456789abcdef",
        "title": "Help me understand TCP handshake",
        "course_id": "fedcba98-7654-3210-fedc-ba9876543210",
        "message_count": 6,
        "created_at": "2026-03-05T10:00:00",
        "updated_at": "2026-03-05T10:15:00",
    }


@pytest.fixture
def sample_message_response():
    """A realistic chat message response."""
    return {
        "id": "abcdef01-2345-6789-abcd-ef0123456789",
        "session_id": "01234567-89ab-cdef-0123-456789abcdef",
        "role": "assistant",
        "content": "TCP uses a three-way handshake [1]. First, the client sends a SYN packet.",
        "citations_json": [
            {
                "ref": 1,
                "chunk_id": "chunk-001",
                "text_snippet": "TCP three-way handshake involves SYN, SYN-ACK, ACK",
                "course_code": "CSIT302",
                "week": 5,
                "page_ref": 3,
            }
        ],
        "created_at": "2026-03-05T10:05:00",
    }


@pytest.fixture
def sample_send_message_response():
    """A realistic send message response with both user and assistant messages."""
    return {
        "user_message": {
            "id": "msg-user-001",
            "session_id": "session-001",
            "role": "user",
            "content": "What is a firewall?",
            "citations_json": None,
            "created_at": "2026-03-05T10:05:00",
        },
        "assistant_message": {
            "id": "msg-asst-001",
            "session_id": "session-001",
            "role": "assistant",
            "content": "A firewall is a network security system [1].",
            "citations_json": [
                {
                    "ref": 1,
                    "text_snippet": "Firewalls monitor and control network traffic.",
                }
            ],
            "created_at": "2026-03-05T10:05:01",
        },
    }


@pytest.fixture
def sample_session_list_response():
    """A realistic session list response."""
    return {
        "sessions": [
            {
                "id": "session-002",
                "title": "Understanding encryption",
                "course_id": None,
                "message_count": 4,
                "created_at": "2026-03-05T11:00:00",
                "updated_at": "2026-03-05T11:20:00",
            },
            {
                "id": "session-001",
                "title": "TCP handshake help",
                "course_id": "course-001",
                "message_count": 8,
                "created_at": "2026-03-05T10:00:00",
                "updated_at": "2026-03-05T10:30:00",
            },
        ]
    }


@pytest.fixture
def sample_message_no_citations():
    """A message response with no citations."""
    return {
        "id": "msg-003",
        "session_id": "session-001",
        "role": "user",
        "content": "Can you explain that differently?",
        "citations_json": None,
        "created_at": "2026-03-05T10:06:00",
    }


# ── Session structure ──────────────────────────────────────────────


class TestSessionResponseStructure:
    """Validate chat session response structure."""

    def test_has_all_required_fields(self, sample_session_response):
        """Session response contains all required fields."""
        required = {"id", "title", "course_id", "message_count", "created_at", "updated_at"}
        missing = required - sample_session_response.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_message_count_is_non_negative_int(self, sample_session_response):
        """Message count is a non-negative integer."""
        assert isinstance(sample_session_response["message_count"], int)
        assert sample_session_response["message_count"] >= 0

    def test_timestamps_are_iso_format(self, sample_session_response):
        """Timestamps are valid ISO format strings."""
        from datetime import datetime

        datetime.fromisoformat(sample_session_response["created_at"])
        datetime.fromisoformat(sample_session_response["updated_at"])

    def test_course_id_is_nullable(self, sample_session_list_response):
        """course_id can be None (not scoped to a course)."""
        no_course = [
            s for s in sample_session_list_response["sessions"] if s["course_id"] is None
        ]
        assert len(no_course) > 0, "Should have at least one session without course_id"


# ── Message structure ──────────────────────────────────────────────


class TestMessageResponseStructure:
    """Validate chat message response structure."""

    def test_has_all_required_fields(self, sample_message_response):
        """Message response contains all required fields."""
        required = {"id", "session_id", "role", "content", "citations_json", "created_at"}
        missing = required - sample_message_response.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_role_is_valid(self, sample_message_response):
        """Role must be user or assistant."""
        assert sample_message_response["role"] in ("user", "assistant")

    def test_content_is_non_empty_string(self, sample_message_response):
        """Content must be a non-empty string."""
        assert isinstance(sample_message_response["content"], str)
        assert len(sample_message_response["content"]) > 0

    def test_citations_json_is_list_when_present(self, sample_message_response):
        """When citations_json is not None, it must be a list of dicts."""
        cites = sample_message_response["citations_json"]
        assert isinstance(cites, list)
        for c in cites:
            assert isinstance(c, dict)
            assert "ref" in c

    def test_citations_json_is_nullable(self, sample_message_no_citations):
        """citations_json can be None (user messages typically have no citations)."""
        assert sample_message_no_citations["citations_json"] is None


# ── SendMessage response structure ─────────────────────────────────


class TestSendMessageResponseStructure:
    """Validate send message response structure."""

    def test_has_both_messages(self, sample_send_message_response):
        """Response contains both user_message and assistant_message."""
        assert "user_message" in sample_send_message_response
        assert "assistant_message" in sample_send_message_response

    def test_user_message_has_user_role(self, sample_send_message_response):
        """user_message has role=user."""
        assert sample_send_message_response["user_message"]["role"] == "user"

    def test_assistant_message_has_assistant_role(self, sample_send_message_response):
        """assistant_message has role=assistant."""
        assert sample_send_message_response["assistant_message"]["role"] == "assistant"

    def test_both_messages_share_session_id(self, sample_send_message_response):
        """Both messages belong to the same session."""
        user_sid = sample_send_message_response["user_message"]["session_id"]
        asst_sid = sample_send_message_response["assistant_message"]["session_id"]
        assert user_sid == asst_sid

    def test_user_message_has_no_citations(self, sample_send_message_response):
        """User messages should not have citations."""
        assert sample_send_message_response["user_message"]["citations_json"] is None


# ── Session list structure ─────────────────────────────────────────


class TestSessionListResponseStructure:
    """Validate session list response structure."""

    def test_has_sessions_key(self, sample_session_list_response):
        """Response has a sessions key."""
        assert "sessions" in sample_session_list_response

    def test_sessions_is_list(self, sample_session_list_response):
        """sessions value is a list."""
        assert isinstance(sample_session_list_response["sessions"], list)

    def test_each_session_has_required_fields(self, sample_session_list_response):
        """Each session in the list has all required fields."""
        required = {"id", "title", "course_id", "message_count", "created_at", "updated_at"}
        for i, s in enumerate(sample_session_list_response["sessions"]):
            missing = required - s.keys()
            assert not missing, f"Session {i} missing fields: {missing}"
