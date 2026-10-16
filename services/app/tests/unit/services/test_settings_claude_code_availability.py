"""SEC-006 option F: the settings surface reports and enforces Claude Code availability.

The worker's refusal (`ensure_claude_cli_spawnable`) is authoritative; this only
keeps a user from choosing a backend that cannot run. Nothing here spawns the CLI
or calls `get_agent` (floor 3).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import settings_service

USER_ID = "user-001"
REASON = "the Claude Code backend is unavailable: test reason"
PROBE = "app.agents.claude_code.claude_cli_unavailable_reason"


def _row(stored: dict) -> MagicMock:
    row = MagicMock()
    row.settings_json = stored
    row.theme = "system"
    row.language = "en"
    row.content_language = False
    row.timezone = "UTC"
    row.leaderboard_opt_in = False
    row.dashboard_layout = None
    row.updated_at = datetime.now(UTC)
    return row


def _with_row(row: MagicMock):
    return patch.object(
        settings_service, "_get_or_create_user_settings", AsyncMock(return_value=row)
    )


@pytest.fixture
def session():
    s = AsyncMock()
    s.add = MagicMock()
    return s


class TestAvailabilityHelper:
    def test_available_when_probe_returns_none(self):
        with patch(PROBE, return_value=None):
            assert settings_service.claude_code_availability() == (True, None)

    def test_unavailable_carries_reason(self):
        with patch(PROBE, return_value=REASON):
            assert settings_service.claude_code_availability() == (False, REASON)


@pytest.mark.asyncio
class TestReadSurface:
    async def test_read_reports_unavailable_with_reason(self, session):
        with _with_row(_row({})), patch(PROBE, return_value=REASON):
            out = await settings_service.get_user_settings(session, USER_ID)
        assert out["claude_code_available"] is False
        assert out["claude_code_unavailable_reason"] == REASON

    async def test_read_reports_available(self, session):
        with _with_row(_row({})), patch(PROBE, return_value=None):
            out = await settings_service.get_user_settings(session, USER_ID)
        assert out["claude_code_available"] is True
        assert out["claude_code_unavailable_reason"] is None

    async def test_existing_claude_code_choice_is_shown_not_rewritten(self, session):
        row = _row({"agent_backend": "claude_code"})
        with _with_row(row), patch(PROBE, return_value=REASON):
            out = await settings_service.get_user_settings(session, USER_ID)
        assert out["agent_backend"] == "claude_code"
        assert out["claude_code_available"] is False
        assert row.settings_json == {"agent_backend": "claude_code"}


@pytest.mark.asyncio
class TestSaveRefusal:
    async def test_saving_claude_code_refused_when_unavailable(self, session):
        row = _row({})
        with (
            _with_row(row),
            patch(PROBE, return_value=REASON),
            pytest.raises(ValueError, match="Claude Code backend is unavailable"),
        ):
            await settings_service.update_user_settings(
                session, USER_ID, {"agent_backend": "claude_code"}
            )
        assert row.settings_json == {}
        session.commit.assert_not_awaited()

    async def test_saving_claude_code_allowed_when_available(self, session):
        row = _row({})
        with _with_row(row), patch(PROBE, return_value=None):
            await settings_service.update_user_settings(
                session, USER_ID, {"agent_backend": "claude_code"}
            )
        assert row.settings_json["agent_backend"] == "claude_code"

    async def test_other_backends_unaffected_when_unavailable(self, session):
        row = _row({})
        with _with_row(row), patch(PROBE, return_value=REASON):
            await settings_service.update_user_settings(
                session, USER_ID, {"agent_backend": "ollama"}
            )
        assert row.settings_json["agent_backend"] == "ollama"

    async def test_resubmitting_stored_claude_code_is_not_refused(self, session):
        """A form that echoes the saved value must not fail unrelated edits."""
        row = _row({"agent_backend": "claude_code"})
        with _with_row(row), patch(PROBE, return_value=REASON):
            await settings_service.update_user_settings(
                session, USER_ID, {"agent_backend": "claude_code", "flashcard_count_per_week": 7}
            )
        assert row.settings_json["agent_backend"] == "claude_code"
        assert row.settings_json["flashcard_count_per_week"] == 7
