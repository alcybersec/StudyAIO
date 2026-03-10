"""Tests for email notification service."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import (
    render_template,
    send_cards_due,
    send_email,
    send_pipeline_complete,
    send_templated_email,
    send_weekly_digest,
)


class TestEmailService:
    """Tests for email_service functions."""

    def test_render_template_pipeline_complete(self) -> None:
        """render_template renders pipeline_complete with variables."""
        html = render_template(
            "pipeline_complete.html",
            filename="lecture1.pdf",
            course_code="CSIT302",
            week=3,
            flashcard_count=15,
            quiz_count=8,
        )
        assert "lecture1.pdf" in html
        assert "CSIT302" in html
        assert "15 flashcards" in html
        assert "8 quiz questions" in html

    @pytest.mark.asyncio
    async def test_send_email_no_smtp_returns_false(self) -> None:
        """send_email returns False when SMTP is not configured."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.smtp_host = ""
            mock_settings.smtp_from_email = ""
            result = await send_email("test@example.com", "Test", "<p>Hi</p>")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_success(self) -> None:
        """send_email returns True when SMTP send succeeds."""
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("app.services.email_service._smtp_configured", return_value=True),
            patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send,
        ):
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_username = "user"
            mock_settings.smtp_password.get_secret_value.return_value = "pass"
            mock_settings.smtp_from_email = "from@test.com"
            mock_settings.smtp_from_name = "Test"
            mock_settings.smtp_use_tls = True

            result = await send_email("to@test.com", "Subject", "<p>Body</p>")
            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_failure_returns_false(self) -> None:
        """send_email returns False on SMTP failure (best-effort)."""
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("app.services.email_service._smtp_configured", return_value=True),
            patch(
                "aiosmtplib.send", new_callable=AsyncMock, side_effect=ConnectionError("SMTP down")
            ),
        ):
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_username = "user"
            mock_settings.smtp_password.get_secret_value.return_value = "pass"
            mock_settings.smtp_from_email = "from@test.com"
            mock_settings.smtp_from_name = "Test"
            mock_settings.smtp_use_tls = True

            result = await send_email("to@test.com", "Subject", "<p>Body</p>")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_templated_email(self) -> None:
        """send_templated_email renders template and calls send_email."""
        with patch("app.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            result = await send_templated_email(
                "to@test.com", "Test Subject", "cards_due.html", due_count=5
            )
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "5" in call_args[0][2]  # html_body contains the count

    @pytest.mark.asyncio
    async def test_typed_senders(self) -> None:
        """Typed sender functions call send_templated_email correctly."""
        with patch(
            "app.services.email_service.send_templated_email", new_callable=AsyncMock
        ) as mock:
            mock.return_value = True

            await send_pipeline_complete("to@test.com", "lec.pdf", "CS101", 1, 10, 5)
            assert mock.call_count == 1

            await send_cards_due("to@test.com", 7)
            assert mock.call_count == 2

            await send_weekly_digest("to@test.com", 50, 10, 5, 7, 3)
            assert mock.call_count == 3
