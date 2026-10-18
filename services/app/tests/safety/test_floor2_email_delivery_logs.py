"""Floor 2 (tokens and addresses out of logs): outgoing mail logs neither (GL#53, SEC-08).

M33 gate. GL#53 (``0be417c``) added ``Date``, ``Message-ID`` and a ``text/plain``
alternative derived from the HTML body. The plain part repeats every link in
the body as a visible URL, so a password-reset, verification or invite token
now appears twice in each message. The pins here run ``send_email`` through the
real logging configuration, on success and on SMTP failures whose exception
text names the recipient, and require that the handler stream carries neither
the recipient address nor the link token, nor the body itself.

The call-site sweep in ``test_floor2_no_email_in_logs`` proves no log call is
*handed* an address; these prove what actually reaches the stream when the
mail layer logs, including exception text it does not control.
"""

from __future__ import annotations

import io
import logging
from unittest.mock import AsyncMock, patch

import pytest
import structlog

RECIPIENT = "floor2-recipient@example.com"
TOKEN = "f2tok-6b1d0c4e9a7f43c2b8e5d1a0c9f8e7d6"


@pytest.fixture
def stream():
    """Configure the app's logging on a fresh root handler; restore afterwards."""
    from app.core.logging import configure_logging

    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    saved_config = structlog.get_config()
    out = io.StringIO()
    root.handlers = [logging.StreamHandler(out)]
    try:
        configure_logging("DEBUG")
        # basicConfig is a no-op once root has a handler, so set the level here:
        # DEBUG, so the TLS-mode line and every other debug line are checked too.
        root.setLevel(logging.DEBUG)
        yield out
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
        structlog.configure(**saved_config)


def _smtp_settings(s) -> None:
    s.smtp_host = "smtp.test.invalid"
    s.smtp_port = 587
    s.smtp_username = "user"
    s.smtp_password.get_secret_value.return_value = "pass"
    s.smtp_from_email = "noreply@mail.studyaio.test"
    s.smtp_from_name = "StudyAIO"
    s.smtp_use_tls = True
    s.app_base_url = "https://app.studyaio.test"


async def _send(kind: str, *, side_effect=None):
    from app.services import email_service

    url = f"https://app.studyaio.test/{kind}?token={TOKEN}"
    with (
        patch("app.services.email_service.settings") as s,
        patch("aiosmtplib.send", new_callable=AsyncMock, side_effect=side_effect) as send,
    ):
        _smtp_settings(s)
        if kind == "reset-password":
            ok = await email_service.send_password_reset(RECIPIENT, url)
        elif kind == "verify-email":
            ok = await email_service.send_email_verification(RECIPIENT, url)
        else:
            ok = await email_service.send_invite(RECIPIENT, url, "in 14 days", note="hi")
    return ok, send


def _smtp_refusal() -> Exception:
    import aiosmtplib

    return aiosmtplib.SMTPRecipientsRefused(
        [aiosmtplib.SMTPRecipientRefused(550, f"no such user {RECIPIENT}", RECIPIENT)]
    )


KINDS = ("reset-password", "verify-email", "register")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_floor2_sent_mail_logs_no_address_token_or_body(stream, kind):
    ok, send = await _send(kind)
    assert ok is True
    msg = send.await_args.args[0]
    # Not vacuous: the token is in both alternatives of the message that left.
    parts = [p.get_payload(decode=True).decode() for p in msg.get_payload()]
    assert [p.get_content_subtype() for p in msg.get_payload()] == ["plain", "html"]
    assert all(TOKEN in p for p in parts), "probe is vacuous: the token is not in the mail"
    out = stream.getvalue()
    assert "email_sent" in out, "probe is vacuous: nothing was logged: " + out
    assert RECIPIENT not in out and "@example.com" not in out, out
    assert TOKEN not in out, out
    assert "<html" not in out.lower() and "<a " not in out.lower(), "the body reached a log: " + out


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "error",
    [
        _smtp_refusal,
        lambda: RuntimeError(f"relay rejected {RECIPIENT} for <{RECIPIENT}>"),
    ],
    ids=["recipients-refused", "error-text-names-recipient"],
)
async def test_floor2_failed_mail_logs_no_address_or_token(stream, kind, error):
    ok, _send_mock = await _send(kind, side_effect=error())
    assert ok is False
    out = stream.getvalue()
    assert "email_send_failed" in out and "Traceback" in out, "probe is vacuous: " + out
    assert "@example.com" not in out, out
    assert TOKEN not in out, out
