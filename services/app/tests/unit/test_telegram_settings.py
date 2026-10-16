"""Telegram webhook-secret validation at startup (SEC-015 follow-up)."""

import pytest
from pydantic import ValidationError

from app.config import Settings

GOOD = "a" * 31 + "-" + "B_9" * 3


class TestWebhookSecretValidation:
    def test_unset_is_allowed(self) -> None:
        assert Settings(telegram_webhook_secret="").telegram_webhook_secret.get_secret_value() == ""

    def test_valid_secret_is_accepted(self) -> None:
        s = Settings(telegram_webhook_secret=GOOD)
        assert s.telegram_webhook_secret.get_secret_value() == GOOD

    def test_max_length_256_accepted(self) -> None:
        Settings(telegram_webhook_secret="x" * 256)

    @pytest.mark.parametrize(
        "bad",
        ["short-secret", "a" * 31, "a" * 257, "a" * 31 + "!", "a" * 31 + " ", "é" * 32],
    )
    def test_invalid_secret_refused_without_echoing_value(self, bad: str) -> None:
        with pytest.raises(ValidationError) as exc:
            Settings(telegram_webhook_secret=bad)
        text = str(exc.value)
        assert "TELEGRAM_WEBHOOK_SECRET" in text
        assert bad not in text
        assert "input_value" not in text
