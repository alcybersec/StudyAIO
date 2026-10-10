"""At-rest encryption of per-user credentials (SEC-06, GL#20, R-033)."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.config import settings
from app.core import secret_box
from app.services import settings_service

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()
CREDS = json.dumps(
    {"claudeAiOauth": {"accessToken": "tok-access-123", "refreshToken": "tok-ref-456"}}
)


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(KEY_A))
    return KEY_A


class TestSecretBox:
    def test_round_trip(self, key):
        token = secret_box.encrypt("sk-ant-secret-value")
        assert token.startswith(secret_box.PREFIX)
        assert "sk-ant-secret-value" not in token
        assert secret_box.decrypt(token) == "sk-ant-secret-value"

    def test_nonce_makes_ciphertexts_differ(self, key):
        assert secret_box.encrypt("same-value") != secret_box.encrypt("same-value")

    def test_tamper_detected(self, key):
        token = secret_box.encrypt("sk-ant-secret-value")
        flipped = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")
        with pytest.raises(secret_box.SecretDecryptError):
            secret_box.decrypt(flipped)

    def test_wrong_key_fails(self, key, monkeypatch):
        token = secret_box.encrypt("sk-ant-secret-value")
        monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(KEY_B))
        with pytest.raises(secret_box.SecretDecryptError):
            secret_box.decrypt(token)

    def test_rotation_old_key_still_decrypts_new_key_encrypts(self, key, monkeypatch):
        old = secret_box.encrypt("sk-ant-secret-value")
        monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(f"{KEY_B},{KEY_A}"))
        assert secret_box.decrypt(old) == "sk-ant-secret-value"
        assert secret_box.needs_rotation(old)
        fresh = secret_box.encrypt("sk-ant-secret-value")
        assert not secret_box.needs_rotation(fresh)
        monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(KEY_B))
        assert secret_box.decrypt(fresh) == "sk-ant-secret-value"

    def test_legacy_plaintext_passes_through_decrypt(self, key):
        assert secret_box.decrypt("sk-legacy-plain") == "sk-legacy-plain"
        assert secret_box.is_encrypted("sk-legacy-plain") is False

    def test_no_key_stores_plaintext_when_self_hosted(self, monkeypatch):
        monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(""))
        monkeypatch.setattr(settings, "self_hosted", True)
        assert secret_box.encrypt("abc-plain") == "abc-plain"

    def test_no_key_refuses_to_write_when_not_self_hosted(self, monkeypatch):
        monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(""))
        monkeypatch.setattr(settings, "self_hosted", False)
        with pytest.raises(secret_box.SecretBoxError):
            secret_box.encrypt("abc-plain")

    def test_encrypted_value_without_key_is_unreadable(self, key, monkeypatch):
        token = secret_box.encrypt("abc-plain")
        monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(""))
        with pytest.raises(secret_box.SecretDecryptError):
            secret_box.decrypt(token)

    def test_startup_check_fails_fast_in_saas_without_key(self, monkeypatch):
        monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(""))
        monkeypatch.setattr(settings, "self_hosted", False)
        with pytest.raises(RuntimeError, match="SETTINGS_ENCRYPTION_KEY"):
            secret_box.check_startup()

    def test_startup_check_passes_self_hosted_without_key(self, monkeypatch):
        monkeypatch.setattr(settings, "settings_encryption_key", SecretStr(""))
        monkeypatch.setattr(settings, "self_hosted", True)
        secret_box.check_startup()

    def test_startup_check_rejects_malformed_key(self, monkeypatch):
        monkeypatch.setattr(settings, "settings_encryption_key", SecretStr("not-a-fernet-key"))
        with pytest.raises(RuntimeError, match="SETTINGS_ENCRYPTION_KEY"):
            secret_box.check_startup()


def _row(overrides):
    return SimpleNamespace(
        user_id="u1",
        settings_json=dict(overrides),
        theme="system",
        language="en",
        content_language=False,
        timezone="UTC",
        leaderboard_opt_in=False,
        dashboard_layout=None,
        updated_at=None,
    )


def _session(row):
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


class TestSettingsServiceEncryption:
    @pytest.mark.asyncio
    async def test_put_stores_ciphertext_for_every_secret(self, key):
        row = _row({})
        await settings_service.update_user_settings(
            _session(row),
            "u1",
            {
                "agent_backend": "anthropic_api",
                "anthropic_api_key": "sk-ant-PLAINTEXT-1",
                "openai_api_key": "sk-openai-PLAINTEXT-2",
                "zai_api_key": "zai-PLAINTEXT-3",
                "claude_cli_credentials": CREDS,
            },
        )
        stored = row.settings_json
        blob = json.dumps(stored)
        for plain in ("PLAINTEXT-1", "PLAINTEXT-2", "PLAINTEXT-3", "tok-access-123", "tok-ref-456"):
            assert plain not in blob
        for k in settings_service.SECRET_KEYS:
            assert stored[k].startswith(secret_box.PREFIX)
        assert stored["agent_backend"] == "anthropic_api"

    @pytest.mark.asyncio
    async def test_put_response_never_contains_plaintext(self, key):
        row = _row({})
        out = await settings_service.update_user_settings(
            _session(row), "u1", {"anthropic_api_key": "sk-ant-PLAINTEXT-1"}
        )
        assert "PLAINTEXT" not in json.dumps(out, default=str)
        assert out["anthropic_api_key_configured"] is True

    @pytest.mark.asyncio
    async def test_get_never_contains_plaintext_or_ciphertext(self, key):
        token = secret_box.encrypt("sk-ant-PLAINTEXT-1")
        out = await settings_service.get_user_settings(
            _session(_row({"anthropic_api_key": token})), "u1"
        )
        dumped = json.dumps(out, default=str)
        assert "PLAINTEXT" not in dumped and secret_box.PREFIX not in dumped
        assert out["anthropic_api_key_configured"] is True

    @pytest.mark.asyncio
    async def test_agent_config_decrypts(self, key):
        row = _row(
            {
                "agent_backend": "claude_code",
                "claude_cli_credentials": secret_box.encrypt(CREDS),
            }
        )
        cfg = await settings_service.get_user_agent_config(_session(row), "u1")
        assert cfg["claude_cli_credentials"] == CREDS

    @pytest.mark.asyncio
    async def test_legacy_plaintext_is_read_then_reencrypted(self, key):
        row = _row({"agent_backend": "anthropic_api", "anthropic_api_key": "sk-ant-legacy-1"})
        session = _session(row)
        cfg = await settings_service.get_user_agent_config(session, "u1")
        assert cfg["anthropic_api_key"] == "sk-ant-legacy-1"
        assert row.settings_json["anthropic_api_key"].startswith(secret_box.PREFIX)
        assert "sk-ant-legacy-1" not in json.dumps(row.settings_json)
        cfg2 = await settings_service.get_user_agent_config(session, "u1")
        assert cfg2["anthropic_api_key"] == "sk-ant-legacy-1"

    @pytest.mark.asyncio
    async def test_tampered_value_yields_empty_credential_not_garbage(self, key):
        token = secret_box.encrypt("sk-ant-PLAINTEXT-1")
        bad = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")
        row = _row({"agent_backend": "anthropic_api", "anthropic_api_key": bad})
        cfg = await settings_service.get_user_agent_config(_session(row), "u1")
        assert cfg["anthropic_api_key"] == ""

    @pytest.mark.asyncio
    async def test_redaction_scrubs_decrypted_values(self, key):
        row = _row({"anthropic_api_key": secret_box.encrypt("sk-ant-PLAINTEXT-1")})
        out = await settings_service.redact_user_secrets(
            _session(row), "u1", "boom sk-ant-PLAINTEXT-1 boom"
        )
        assert "PLAINTEXT" not in out
