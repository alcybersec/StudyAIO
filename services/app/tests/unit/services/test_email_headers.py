"""Deliverability headers and the text/plain alternative on outgoing mail (GL#53)."""

from collections.abc import Awaitable, Callable
from email.message import Message
from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import (
    send_email,
    send_email_verification,
    send_invite,
    send_password_reset,
)


async def _capture(send: Callable[[], Awaitable[bool]]) -> Message:
    """Run a send coroutine with SMTP mocked; return the message given to aiosmtplib."""
    with (
        patch("app.services.email_service.settings") as s,
        patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send,
    ):
        s.smtp_host = "smtp.test.com"
        s.smtp_port = 587
        s.smtp_username = "user"
        s.smtp_password.get_secret_value.return_value = "pass"
        s.smtp_from_email = "noreply@mail.studyaio.test"
        s.smtp_from_name = "StudyAIO"
        s.smtp_use_tls = True
        s.app_base_url = "https://app.studyaio.test"
        assert await send() is True
    return mock_send.await_args.args[0]


def _parts(msg: Message) -> list[Message]:
    return list(msg.get_payload())


def _plain(msg: Message) -> str:
    return _parts(msg)[0].get_payload(decode=True).decode()


class TestEmailHeaders:
    @pytest.mark.asyncio
    async def test_message_id_uses_sender_domain(self) -> None:
        msg = await _capture(lambda: send_email("a@b.test", "Hi", "<p>Hi</p>"))
        mid = msg["Message-ID"]
        assert mid.startswith("<")
        assert mid.endswith("@mail.studyaio.test>")

    @pytest.mark.asyncio
    async def test_message_ids_are_unique(self) -> None:
        a = await _capture(lambda: send_email("a@b.test", "Hi", "<p>Hi</p>"))
        b = await _capture(lambda: send_email("a@b.test", "Hi", "<p>Hi</p>"))
        assert a["Message-ID"] != b["Message-ID"]

    @pytest.mark.asyncio
    async def test_date_header_is_utc_rfc2822(self) -> None:
        msg = await _capture(lambda: send_email("a@b.test", "Hi", "<p>Hi</p>"))
        assert msg["Date"].endswith("-0000")

    @pytest.mark.asyncio
    async def test_sender_recipient_subject_unchanged(self) -> None:
        msg = await _capture(lambda: send_email("a@b.test", "Hi", "<p>Hi</p>"))
        assert msg["From"] == "StudyAIO <noreply@mail.studyaio.test>"
        assert msg["To"] == "a@b.test"
        assert msg["Subject"] == "Hi"

    @pytest.mark.asyncio
    async def test_plain_part_precedes_html_part(self) -> None:
        msg = await _capture(lambda: send_email("a@b.test", "Hi", "<p>Hello</p>"))
        assert msg.get_content_type() == "multipart/alternative"
        assert [p.get_content_type() for p in _parts(msg)] == ["text/plain", "text/html"]

    @pytest.mark.asyncio
    async def test_plain_part_drops_style_and_keeps_link_urls(self) -> None:
        html = (
            "<html><head><title>T</title><style>.x{color:red}</style></head>"
            '<body><p>Hello <b>there</b></p><a href="https://x.test/go?t=1">Go</a>'
            "</body></html>"
        )
        msg = await _capture(lambda: send_email("a@b.test", "Hi", html))
        plain = _plain(msg)
        assert "color:red" not in plain
        assert "Hello there" in plain
        assert "https://x.test/go?t=1" in plain
        assert "<" not in plain


class TestAuthEmailsPlainText:
    @pytest.mark.asyncio
    async def test_verification_plain_has_link_and_sentence(self) -> None:
        url = "https://app.studyaio.test/verify-email?token=abc123"
        msg = await _capture(lambda: send_email_verification("a@b.test", url))
        assert [p.get_content_type() for p in _parts(msg)] == ["text/plain", "text/html"]
        plain = _plain(msg)
        assert url in plain
        assert "Confirm this email address to finish setting up your account." in plain

    @pytest.mark.asyncio
    async def test_password_reset_plain_has_link_and_sentence(self) -> None:
        url = "https://app.studyaio.test/reset-password?token=xyz"
        msg = await _capture(lambda: send_password_reset("a@b.test", url))
        plain = _plain(msg)
        assert url in plain
        assert "Reset your password" in plain

    @pytest.mark.asyncio
    async def test_invite_plain_has_link_and_sentence(self) -> None:
        url = "https://app.studyaio.test/register?invite=tok"
        msg = await _capture(lambda: send_invite("a@b.test", url, "in 14 days"))
        plain = _plain(msg)
        assert url in plain
        assert "in 14 days" in plain
