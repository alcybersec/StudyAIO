"""AI-processing consent rules (M33-S1-BACKEND-017, GL#38, audit SEC-08)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User
from app.services import consent_service


def _user(at: datetime | None, version: int | None) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = "u1"
    user.ai_processing_consent_at = at
    user.ai_processing_consent_version = version
    return user


class TestConsentRequired:
    def test_never_consented_requires_consent(self):
        assert consent_service.consent_required(_user(None, None)) is True

    def test_current_version_is_consented(self):
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 2
            assert consent_service.consent_required(_user(datetime.now(UTC), 2)) is False

    def test_older_version_requires_reconsent(self):
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 2
            assert consent_service.consent_required(_user(datetime.now(UTC), 1)) is True

    def test_newer_version_is_not_required(self):
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 1
            assert consent_service.consent_required(_user(datetime.now(UTC), 3)) is False

    def test_timestamp_without_version_requires_consent(self):
        assert consent_service.consent_required(_user(datetime.now(UTC), None)) is True

    def test_single_user_mode_operator_is_treated_as_consented(self):
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = True
            s.ai_consent_version = 1
            assert consent_service.consent_required(_user(None, None)) is False


@pytest.mark.asyncio
class TestRecordConsent:
    async def test_records_now_and_current_version(self):
        user = _user(None, None)
        session = AsyncMock()
        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 4
            await consent_service.record_consent(session, user)
        assert user.ai_processing_consent_version == 4
        assert user.ai_processing_consent_at is not None
        assert user.ai_processing_consent_at.tzinfo is not None
        session.commit.assert_awaited_once()

    async def test_require_raises_when_missing(self):
        from app.core.exceptions import AiConsentRequiredError

        with patch("app.services.consent_service.settings") as s:
            s.single_user_mode = False
            s.ai_consent_version = 1
            with pytest.raises(AiConsentRequiredError):
                consent_service.require_consent(_user(None, None))
