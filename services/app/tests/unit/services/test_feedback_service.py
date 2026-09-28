"""Tests for the feedback service.

Sentry records what crashed and the beta funnel records that a tester stopped
after their first upload. Neither records *why* — that has to come from the
person, and until this existed there was nowhere for them to say it.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.feedback import Feedback
from app.services import feedback_service


class TestSubmitFeedback:
    async def test_stores_what_was_written(self, mock_session):
        entry = await feedback_service.submit_feedback(
            mock_session, "user-1", kind="bug", message="Summary tab renders empty"
        )

        assert entry.user_id == "user-1"
        assert entry.kind == "bug"
        assert entry.message == "Summary tab renders empty"
        mock_session.add.assert_called_once()

    async def test_keeps_the_route_and_build(self, mock_session):
        """Without these, "it looked empty" is unactionable.

        With them it is a page and a commit, which is the difference between a
        report you can reproduce and one you can only sympathise with.
        """
        entry = await feedback_service.submit_feedback(
            mock_session,
            "user-1",
            kind="bug",
            message="blank",
            route="/courses/CSIT302/weeks/3",
            app_version="8d8841b",
        )

        assert entry.route == "/courses/CSIT302/weeks/3"
        assert entry.app_version == "8d8841b"

    async def test_trims_surrounding_whitespace(self, mock_session):
        entry = await feedback_service.submit_feedback(
            mock_session, "user-1", kind="idea", message="  dark mode for the PDF viewer \n"
        )

        assert entry.message == "dark mode for the PDF viewer"

    async def test_a_whitespace_only_message_is_rejected(self, mock_session):
        """An empty report is a mis-click, not feedback."""
        with pytest.raises(ValueError, match="empty"):
            await feedback_service.submit_feedback(
                mock_session, "user-1", kind="bug", message="   \n  "
            )

    async def test_an_unknown_kind_is_rejected(self, mock_session):
        with pytest.raises(ValueError, match="kind"):
            await feedback_service.submit_feedback(
                mock_session, "user-1", kind="complaint", message="x"
            )

    async def test_an_overlong_message_is_rejected(self, mock_session):
        with pytest.raises(ValueError, match="exceeds"):
            await feedback_service.submit_feedback(
                mock_session,
                "user-1",
                kind="bug",
                message="x" * (feedback_service.MAX_MESSAGE_LENGTH + 1),
            )

    async def test_a_long_user_agent_is_truncated_not_rejected(self, mock_session):
        """The browser chose that string; losing the report over it is absurd."""
        entry = await feedback_service.submit_feedback(
            mock_session, "user-1", kind="bug", message="x", user_agent="M" * 900
        )

        assert len(entry.user_agent) == 500

    async def test_the_message_is_not_written_to_the_structured_log(self, mock_session):
        """It is the user's words; the log is not where they belong."""
        with patch.object(feedback_service.logger, "info") as log:
            await feedback_service.submit_feedback(
                mock_session, "user-1", kind="bug", message="my email is alex@example.com"
            )

        assert "alex@example.com" not in str(log.call_args)
        assert log.call_args.kwargs["length"] == len("my email is alex@example.com")


class TestNotifyAdmins:
    """Feedback nobody reads is worse than none, because it looks like a channel."""

    def _entry(self, message="it broke", kind="bug", route="/upload"):
        return SimpleNamespace(id="f-1", message=message, kind=kind, route=route)

    def _session_with_links(self, chat_ids):
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            SimpleNamespace(chat_id=c) for c in chat_ids
        ]
        session.execute = AsyncMock(return_value=result)
        return session

    async def test_pings_every_linked_admin(self):
        session = self._session_with_links([11, 22])
        send = AsyncMock(return_value=True)

        with patch("app.services.telegram_service.send_telegram_message", send):
            sent = await feedback_service.notify_admins(session, self._entry(), "a@b.com")

        assert sent == 2

    async def test_no_linked_admin_is_not_an_error(self):
        session = self._session_with_links([])
        assert await feedback_service.notify_admins(session, self._entry(), "a@b.com") == 0

    async def test_a_telegram_outage_never_raises(self):
        """The feedback is already stored and acknowledged by this point."""
        session = self._session_with_links([11])

        with patch(
            "app.services.telegram_service.send_telegram_message",
            AsyncMock(side_effect=RuntimeError("telegram down")),
        ):
            assert await feedback_service.notify_admins(session, self._entry(), "a@b.com") == 0

    async def test_a_failed_send_is_not_counted(self):
        session = self._session_with_links([11, 22])
        send = AsyncMock(side_effect=[True, False])

        with patch("app.services.telegram_service.send_telegram_message", send):
            sent = await feedback_service.notify_admins(session, self._entry(), "a@b.com")

        assert sent == 1

    async def test_the_excerpt_is_truncated_with_an_ellipsis(self):
        session = self._session_with_links([11])
        send = AsyncMock(return_value=True)
        long_message = "y" * (feedback_service.PING_EXCERPT + 50)

        with patch("app.services.telegram_service.send_telegram_message", send):
            await feedback_service.notify_admins(session, self._entry(long_message), "a@b.com")

        text = send.await_args.args[1]
        assert "…" in text
        # The whole report must not be in the ping — it is a "go and read it"
        # nudge, not a delivery mechanism. Comparing total lengths would be
        # wrong: the header and footer make the message longer than the body.
        assert long_message not in text
        assert text.count("y") == feedback_service.PING_EXCERPT

    async def test_user_content_is_html_escaped(self):
        """The ping is sent as HTML, so an unescaped report could break it —
        or worse, smuggle markup into a message the admin reads."""
        session = self._session_with_links([11])
        send = AsyncMock(return_value=True)

        with patch("app.services.telegram_service.send_telegram_message", send):
            await feedback_service.notify_admins(
                session, self._entry("<b>bold</b> & <script>x</script>"), "a@b.com"
            )

        text = send.await_args.args[1]
        assert "<script>" not in text
        assert "&lt;script&gt;" in text


class TestSetStatus:
    async def test_moves_it_through_triage(self, mock_session):
        entry = Feedback(id="f-1", user_id="u-1", kind="bug", message="x", status="new")
        mock_session.get = AsyncMock(return_value=entry)

        updated = await feedback_service.set_status(mock_session, "f-1", "triaged")

        assert updated.status == "triaged"

    async def test_an_unknown_status_is_rejected(self, mock_session):
        with pytest.raises(ValueError, match="status"):
            await feedback_service.set_status(mock_session, "f-1", "wontfix")

    async def test_a_missing_item_returns_none(self, mock_session):
        mock_session.get = AsyncMock(return_value=None)

        assert await feedback_service.set_status(mock_session, "nope", "closed") is None


class TestCountByStatus:
    async def test_statuses_with_no_rows_are_present_as_zero(self, mock_session):
        """The admin badge needs a number, not a missing key."""
        result = MagicMock()
        result.all.return_value = [("new", 3)]
        mock_session.execute = AsyncMock(return_value=result)

        counts = await feedback_service.count_by_status(mock_session)

        assert counts == {"new": 3, "triaged": 0, "closed": 0}
