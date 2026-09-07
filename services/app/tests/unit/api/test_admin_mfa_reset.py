"""The MFA lockout recovery path (issue #71).

Working backup codes fix the common case. They do not fix the case the issue is
actually about: a user who has lost the authenticator *and* the codes. Before
this endpoint, `disable_mfa` was the only way off MFA and it requires a current
TOTP code -- so recovery meant direct SQL.

**Why this and not "password reset clears MFA".** A reset that clears MFA turns
the second factor into mailbox possession: whoever can read the user's email
walks straight through it. That is the attacker MFA exists to stop, so recovery
has to be a decision made by someone who is not the requester. Hence
`require_role("admin")` and an out-of-band identity check.

The fixtures mirror `test_admin_user_management.py` so both files authenticate
the same way.
"""

import json
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.auth import hash_password
from app.core.security import generate_backup_codes, hash_backup_codes
from app.models.user import User

TEST_PASSWORD = "TestPass1!"

TEST_SECRET = "<test-placeholder>"


def _make_user(**overrides) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = overrides.get("id", "u-1")
    user.email = overrides.get("email", "tester@example.com")
    user.username = overrides.get("username", "tester")
    user.role = overrides.get("role", "user")
    user.tier = overrides.get("tier", "free")
    user.is_active = overrides.get("is_active", True)
    user.email_verified = overrides.get("email_verified", False)
    user.mfa_enabled = overrides.get("mfa_enabled", False)
    user.mfa_secret = overrides.get("mfa_secret")
    user.backup_codes = overrides.get("backup_codes")
    user.tokens_valid_from = overrides.get("tokens_valid_from")
    user.created_at = overrides.get("created_at", datetime(2026, 1, 1))
    user.last_login_at = None
    user.avatar_url = None
    user.hashed_password = hash_password(TEST_PASSWORD)
    user.has_password = True
    return user


def _locked_out_user() -> MagicMock:
    """MFA on, authenticator lost, codes lost -- the state with no way out."""
    return _make_user(
        id="locked-001",
        mfa_enabled=True,
        mfa_secret=TEST_SECRET,
        backup_codes=json.dumps(hash_backup_codes(generate_backup_codes())),
    )


@pytest.fixture
def _session_returning():
    """Point `mock_session` at a specific user for `get_user_by_id`."""

    def _apply(mock_session, user):
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

    return _apply


@pytest.fixture
async def admin_client(mock_session):
    """Client authenticated as an admin."""
    from app.api.deps import get_current_user
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    admin = _make_user(id="admin-001", email="admin@example.com", username="admin", role="admin")

    async def override_session():
        yield mock_session

    async def override_user():
        return admin

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir, patch("app.config.settings.data_dir", tmpdir):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def nonadmin_client(mock_session):
    """Client authenticated as an ordinary user."""
    from app.api.deps import get_current_user
    from app.core.database import get_session
    from app.core.rate_limit import limiter
    from app.main import app

    async def override_session():
        yield mock_session

    async def override_user():
        return _make_user(id="user-001", role="user")

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    limiter.reset()

    with tempfile.TemporaryDirectory() as tmpdir, patch("app.config.settings.data_dir", tmpdir):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    app.dependency_overrides.clear()


class TestRecoveryWorks:
    """The endpoint actually unlocks the account."""

    @pytest.mark.asyncio
    async def test_it_clears_the_enrollment(self, admin_client, mock_session, _session_returning):
        locked = _locked_out_user()
        _session_returning(mock_session, locked)

        response = await admin_client.post("/api/admin/users/locked-001/mfa-reset")

        assert response.status_code == 200
        assert response.json()["mfa_was_enabled"] is True
        assert locked.mfa_enabled is False
        assert locked.mfa_secret is None
        assert locked.backup_codes is None

    @pytest.mark.asyncio
    async def test_it_revokes_the_accounts_sessions(
        self, admin_client, mock_session, _session_returning
    ):
        """The security level just dropped; a token minted before it must die."""
        locked = _locked_out_user()
        _session_returning(mock_session, locked)

        await admin_client.post("/api/admin/users/locked-001/mfa-reset")

        assert locked.tokens_valid_from is not None

    @pytest.mark.asyncio
    async def test_it_commits(self, admin_client, mock_session, _session_returning):
        _session_returning(mock_session, _locked_out_user())

        await admin_client.post("/api/admin/users/locked-001/mfa-reset")

        mock_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_the_user_can_then_log_in_with_password_alone(
        self, admin_client, mock_session, _session_returning
    ):
        """The end-to-end promise: after the reset, the lockout is over.

        Asserted through the real login endpoint rather than by re-reading the
        flag, because the flag is not the thing the user is stuck behind -- the
        403 from `login` is.
        """
        locked = _locked_out_user()
        _session_returning(mock_session, locked)

        with (
            patch("app.api.auth.login_throttle.apply_delay", new_callable=AsyncMock) as delay,
            patch("app.api.auth.login_throttle.record_failure", new_callable=AsyncMock),
            patch("app.api.auth.login_throttle.clear", new_callable=AsyncMock),
        ):
            delay.return_value = 0.0
            body = {"email": locked.email, "password": TEST_PASSWORD}

            before = await admin_client.post("/api/auth/login", json=body)
            assert before.status_code == 403  # locked out: MFA code required

            reset = await admin_client.post("/api/admin/users/locked-001/mfa-reset")
            assert reset.status_code == 200

            after = await admin_client.post("/api/auth/login", json=body)

        assert after.status_code == 200

    @pytest.mark.asyncio
    async def test_an_account_without_mfa_is_a_no_op(
        self, admin_client, mock_session, _session_returning
    ):
        """Reported honestly, and without signing the user out for nothing."""
        plain = _make_user(id="plain-001", mfa_enabled=False)
        _session_returning(mock_session, plain)

        response = await admin_client.post("/api/admin/users/plain-001/mfa-reset")

        assert response.status_code == 200
        assert response.json()["mfa_was_enabled"] is False
        assert plain.tokens_valid_from is None

    @pytest.mark.asyncio
    async def test_an_unknown_user_is_404(self, admin_client, mock_session, _session_returning):
        _session_returning(mock_session, None)

        response = await admin_client.post("/api/admin/users/nope/mfa-reset")

        assert response.status_code == 404


class TestOnlyAdminsCanRecover:
    """The escape hatch must not be reachable by the account holder."""

    @pytest.mark.asyncio
    async def test_a_regular_user_is_refused(
        self, nonadmin_client, mock_session, _session_returning
    ):
        locked = _locked_out_user()
        _session_returning(mock_session, locked)

        response = await nonadmin_client.post("/api/admin/users/locked-001/mfa-reset")

        assert response.status_code == 403
        assert locked.mfa_enabled is True

    @pytest.mark.asyncio
    async def test_a_user_cannot_clear_their_own_mfa(
        self, nonadmin_client, mock_session, _session_returning
    ):
        """Self-service would make MFA optional at the victim's own request."""
        locked = _locked_out_user()
        locked.id = "user-001"
        _session_returning(mock_session, locked)

        response = await nonadmin_client.post("/api/admin/users/user-001/mfa-reset")

        assert response.status_code == 403
        assert locked.mfa_enabled is True


class TestPasswordResetStillLeavesMFAOn:
    """The rejected alternative, asserted so it cannot creep back in.

    If a future change makes `reset_password_with_token` clear `mfa_enabled`,
    every MFA-protected account in the instance becomes bypassable by whoever
    controls the mailbox. That is a deliberate non-feature.
    """

    @pytest.mark.asyncio
    async def test_a_password_reset_does_not_disable_mfa(self):
        from datetime import UTC, datetime, timedelta

        from app.core.auth import hash_magic_link_token
        from app.models.magic_link import MagicLink
        from app.services import user_service

        user = _locked_out_user()
        link = MagicMock(spec=MagicLink)
        link.id = "link-001"
        link.user_id = user.id
        link.token_hash = hash_magic_link_token("<test-placeholder>")
        link.link_type = "password_reset"
        link.expires_at = datetime.now(UTC) + timedelta(hours=1)
        link.used_at = None

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [link, user]
        session.execute.return_value = result

        await user_service.reset_password_with_token(session, "<test-placeholder>", "NewSecure1!")

        assert user.mfa_enabled is True
        assert user.mfa_secret == TEST_SECRET
