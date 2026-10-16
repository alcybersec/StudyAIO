"""Telegram setWebhook registration passes the secret token (SEC-015)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app import cli
from app.config import settings
from app.services import telegram_service


def _client(status=200, payload=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload if payload is not None else {"ok": True}
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.fixture
def configured():
    with (
        patch.object(settings, "telegram_bot_token", SecretStr("123:tok")),
        patch.object(settings, "telegram_webhook_secret", SecretStr("sec_ret-1")),
        patch.object(settings, "telegram_webhook_url", "https://h.example/hook"),
    ):
        yield


class TestRegisterWebhook:
    @pytest.mark.asyncio
    async def test_passes_secret_token_and_url(self, configured) -> None:
        client = _client()
        with patch("app.services.telegram_service.httpx.AsyncClient", return_value=client):
            ok = await telegram_service.register_webhook()
        assert ok is True
        args, kwargs = client.post.call_args
        assert args[0].endswith("/bot123:tok/setWebhook")
        assert kwargs["json"]["secret_token"] == "sec_ret-1"
        assert kwargs["json"]["url"] == "https://h.example/hook"

    @pytest.mark.asyncio
    async def test_refuses_without_secret(self, configured) -> None:
        client = _client()
        with (
            patch.object(settings, "telegram_webhook_secret", SecretStr("")),
            patch("app.services.telegram_service.httpx.AsyncClient", return_value=client),
        ):
            with pytest.raises(ValueError):
                await telegram_service.register_webhook()
        client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_telegram_rejection_returns_false(self, configured) -> None:
        client = _client(400, {"ok": False})
        with patch("app.services.telegram_service.httpx.AsyncClient", return_value=client):
            assert await telegram_service.register_webhook() is False


class TestCliCommand:
    def test_cli_registers_and_never_prints_secret(self, configured, capsys) -> None:
        with patch.object(cli.telegram_service, "register_webhook", AsyncMock(return_value=True)):
            code = cli.main(["register-telegram-webhook"])
        out = capsys.readouterr()
        assert code == 0
        assert "sec_ret-1" not in out.out + out.err
        assert "123:tok" not in out.out + out.err
