"""MFA backup codes at the login endpoint (issue #71).

Before this, backup codes were generated, shown to the user and stored in
plaintext, and nothing anywhere verified one -- `LoginRequest` had no field to
submit one. So the tests that matter are endpoint tests: `consume_backup_code`
passing its own unit tests proves nothing if login never calls it, which is
precisely the failure shape this project has hit before (see
`test_login_throttle_wiring.py`).

What is asserted here:

* a backup code is accepted in place of a TOTP code, and spent;
* a spent code is refused on replay;
* a wrong backup code is indistinguishable from a wrong TOTP code, and counts
  toward the per-account throttle;
* neither field is a way past the password.

No literal codes appear below. Every one is generated at runtime by
`generate_backup_codes`, so nothing in this file looks like a real credential to
a secret scanner -- and the tests exercise the real format rather than a guess
at it.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import generate_backup_codes, hash_backup_codes
from tests.unit.api.test_auth import _make_db_user

TEST_SECRET = "<test-placeholder>"


@pytest.fixture
def throttle():
    """Patch the throttle as the login endpoint sees it."""
    with (
        patch("app.api.auth.login_throttle.apply_delay", new_callable=AsyncMock) as delay,
        patch("app.api.auth.login_throttle.record_failure", new_callable=AsyncMock) as record,
        patch("app.api.auth.login_throttle.clear", new_callable=AsyncMock) as clear,
    ):
        delay.return_value = 0.0
        yield MagicMock(apply_delay=delay, record_failure=record, clear=clear)


def _enrolled_user(count: int = 3):
    """An MFA-enabled user holding `count` hashed backup codes."""
    codes = generate_backup_codes(count=count)
    user = _make_db_user(
        mfa_enabled=True,
        mfa_secret=TEST_SECRET,
        backup_codes=json.dumps(hash_backup_codes(codes)),
    )
    return user, codes


async def _login(async_client, user, **body):
    """POST /login with `authenticate_user` returning `user`."""
    with patch(
        "app.api.auth.user_service.authenticate_user",
        new_callable=AsyncMock,
        return_value=user,
    ):
        return await async_client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "TestPass1!", **body},
        )


class TestBackupCodeAccepted:
    """A backup code stands in for the authenticator."""

    @pytest.mark.asyncio
    async def test_a_backup_code_logs_in(self, async_client, mock_session, throttle):
        user, codes = _enrolled_user()

        response = await _login(async_client, user, backup_code=codes[0])

        assert response.status_code == 200
        assert "access_token" in response.cookies

    @pytest.mark.asyncio
    async def test_no_totp_code_is_needed(self, async_client, mock_session, throttle):
        """`verify_totp` must not be consulted -- the device is gone."""
        user, codes = _enrolled_user()

        with patch("app.api.auth.verify_totp") as verify:
            response = await _login(async_client, user, backup_code=codes[0])

        assert response.status_code == 200
        verify.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_code_typed_off_paper_is_accepted(self, async_client, mock_session, throttle):
        """Lowercase, no dashes -- how a code actually gets typed back."""
        user, codes = _enrolled_user()

        response = await _login(async_client, user, backup_code=codes[0].replace("-", "").lower())

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_the_remaining_count_is_reported(self, async_client, mock_session, throttle):
        """So that "I have two left" is knowable without asking an admin."""
        user, codes = _enrolled_user(count=3)

        response = await _login(async_client, user, backup_code=codes[0])

        assert response.json()["backup_codes_remaining"] == 2

    @pytest.mark.asyncio
    async def test_the_last_code_reports_zero_remaining(self, async_client, mock_session, throttle):
        """0 must survive the response, not be flattened into "not reported"."""
        user, codes = _enrolled_user(count=1)

        response = await _login(async_client, user, backup_code=codes[0])

        assert response.status_code == 200
        assert response.json()["backup_codes_remaining"] == 0

    @pytest.mark.asyncio
    async def test_a_normal_login_reports_no_count(self, async_client, mock_session, throttle):
        """The count is not account state clients should be polling."""
        response = await _login(async_client, _make_db_user())

        assert response.status_code == 200
        assert response.json()["backup_codes_remaining"] is None

    @pytest.mark.asyncio
    async def test_a_successful_backup_code_login_clears_the_throttle(
        self, async_client, mock_session, throttle
    ):
        user, codes = _enrolled_user()

        await _login(async_client, user, backup_code=codes[0])

        throttle.clear.assert_awaited_once()
        throttle.record_failure.assert_not_awaited()


class TestBackupCodeConsumed:
    """Single-use, like a magic link."""

    @pytest.mark.asyncio
    async def test_the_code_is_removed_from_the_account(self, async_client, mock_session, throttle):
        user, codes = _enrolled_user(count=3)

        await _login(async_client, user, backup_code=codes[0])

        assert len(json.loads(user.backup_codes)) == 2

    @pytest.mark.asyncio
    async def test_the_consumption_is_committed(self, async_client, mock_session, throttle):
        """An uncommitted spend leaves the code live for the next attacker."""
        user, codes = _enrolled_user()

        await _login(async_client, user, backup_code=codes[0])

        mock_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_replaying_a_used_code_is_refused(self, async_client, mock_session, throttle):
        user, codes = _enrolled_user()

        first = await _login(async_client, user, backup_code=codes[0])
        second = await _login(async_client, user, backup_code=codes[0])

        assert first.status_code == 200
        assert second.status_code == 403

    @pytest.mark.asyncio
    async def test_the_unused_codes_survive(self, async_client, mock_session, throttle):
        user, codes = _enrolled_user(count=3)

        await _login(async_client, user, backup_code=codes[0])
        second = await _login(async_client, user, backup_code=codes[2])

        assert second.status_code == 200
        assert second.json()["backup_codes_remaining"] == 1


class TestNoNewBypassOrOracle:
    """A wrong backup code must tell the caller nothing a wrong TOTP would not."""

    @pytest.mark.asyncio
    async def test_a_wrong_backup_code_is_rejected(self, async_client, mock_session, throttle):
        user, _ = _enrolled_user()
        stranger = generate_backup_codes(count=1)[0]

        response = await _login(async_client, user, backup_code=stranger)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_a_wrong_backup_code_looks_like_a_wrong_totp_code(
        self, async_client, mock_session, throttle
    ):
        """Status and body must match, or the field becomes an oracle."""
        user, _ = _enrolled_user()
        stranger = generate_backup_codes(count=1)[0]

        wrong_backup = await _login(async_client, user, backup_code=stranger)

        user_two, _ = _enrolled_user()
        with patch("app.api.auth.verify_totp", return_value=False):
            wrong_totp = await _login(async_client, user_two, totp_code="000000")

        assert wrong_backup.status_code == wrong_totp.status_code
        assert wrong_backup.json() == wrong_totp.json()

    @pytest.mark.asyncio
    async def test_an_account_with_no_codes_looks_the_same(
        self, async_client, mock_session, throttle
    ):
        """ "You have none left" is not something a guesser gets to learn."""
        enrolled, _ = _enrolled_user()
        exhausted = _make_db_user(
            mfa_enabled=True, mfa_secret=TEST_SECRET, backup_codes=json.dumps([])
        )
        never = _make_db_user(mfa_enabled=True, mfa_secret=TEST_SECRET, backup_codes=None)
        stranger = generate_backup_codes(count=1)[0]

        responses = [
            await _login(async_client, u, backup_code=stranger)
            for u in (enrolled, exhausted, never)
        ]

        assert {r.status_code for r in responses} == {403}
        assert len({json.dumps(r.json()) for r in responses}) == 1

    @pytest.mark.asyncio
    async def test_a_wrong_backup_code_counts_toward_the_throttle(
        self, async_client, mock_session, throttle
    ):
        """Otherwise the new field is an unthrottled guessing channel."""
        user, _ = _enrolled_user()
        stranger = generate_backup_codes(count=1)[0]

        response = await _login(async_client, user, backup_code=stranger)

        assert response.status_code == 403
        throttle.record_failure.assert_awaited_once()
        assert throttle.record_failure.await_args.args[0] == "test@example.com"
        throttle.clear.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_wrong_backup_code_consumes_nothing(self, async_client, mock_session, throttle):
        """A guesser must not be able to burn a stranger's codes."""
        user, _ = _enrolled_user(count=3)
        before = user.backup_codes
        stranger = generate_backup_codes(count=1)[0]

        await _login(async_client, user, backup_code=stranger)

        assert user.backup_codes == before

    @pytest.mark.asyncio
    async def test_a_backup_code_does_not_replace_the_password(
        self, async_client, mock_session, throttle
    ):
        """The second factor is second. `authenticate_user` runs first and 401s."""
        user, codes = _enrolled_user()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

        response = await async_client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPass1!",
                "backup_code": codes[0],
            },
        )

        assert response.status_code == 401
        # And the code is still there to be used with the right password.
        assert len(json.loads(user.backup_codes)) == 3

    @pytest.mark.asyncio
    async def test_a_wrong_totp_is_not_rescued_by_a_valid_backup_code(
        self, async_client, mock_session, throttle
    ):
        """Submitting both must not let a failed TOTP fall through to recovery."""
        user, codes = _enrolled_user()

        with patch("app.api.auth.verify_totp", return_value=False):
            response = await _login(async_client, user, totp_code="000000", backup_code=codes[0])

        assert response.status_code == 403
        assert len(json.loads(user.backup_codes)) == 3

    @pytest.mark.asyncio
    async def test_submitting_neither_factor_still_asks_for_one(
        self, async_client, mock_session, throttle
    ):
        user, _ = _enrolled_user()

        response = await _login(async_client, user)

        assert response.status_code == 403
        throttle.record_failure.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_backup_code_is_ignored_when_mfa_is_off(
        self, async_client, mock_session, throttle
    ):
        """It must not become a second, weaker way in for accounts without MFA."""
        user = _make_db_user(mfa_enabled=False, backup_codes=None)

        response = await _login(async_client, user, backup_code="AAAA-AAAA-AAAA-AAAA")

        assert response.status_code == 200
        assert response.json()["backup_codes_remaining"] is None


class TestStorageIsNotReadable:
    """Nothing usable is left in the column for a database reader to find."""

    @pytest.mark.asyncio
    async def test_the_stored_column_never_contains_a_code(self):
        from app.services import user_service

        user = _make_db_user()
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        session.execute.return_value = result

        with patch("app.services.user_service.verify_totp", return_value=True):
            codes = await user_service.enable_mfa(session, user.id, "123456", TEST_SECRET)

        for code in codes:
            assert code not in user.backup_codes
            assert code.replace("-", "") not in user.backup_codes

    @pytest.mark.asyncio
    async def test_a_reader_of_the_column_cannot_log_in_with_it(
        self, async_client, mock_session, throttle
    ):
        """The realistic attack: someone has the dump and submits what it holds."""
        user, _ = _enrolled_user(count=3)
        leaked = json.loads(user.backup_codes)

        for digest in leaked:
            response = await _login(async_client, user, backup_code=digest)
            assert response.status_code == 403

        assert len(json.loads(user.backup_codes)) == 3


class TestReEnrollmentIsRefused:
    """`/mfa/verify` must not silently replace a live enrollment.

    Adjacent finding in the same issue: a hijacked session could enroll a secret
    of its own, which survives the victim's next password change. Requiring the
    current password on this endpoint is the fuller fix and needs a UI field, so
    it is deferred; refusing re-enrollment is the part that costs nothing.
    """

    @pytest.mark.asyncio
    async def test_enrolling_over_live_mfa_is_a_400_not_a_500(self, mock_session):
        import tempfile

        import httpx

        from app.api.deps import get_current_user
        from app.core.database import get_session
        from app.core.rate_limit import limiter
        from app.main import app

        user, _ = _enrolled_user()
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

        async def override_session():
            yield mock_session

        async def override_user():
            return user

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user] = override_user
        limiter.reset()
        try:
            with (
                tempfile.TemporaryDirectory() as tmpdir,
                patch("app.config.settings.data_dir", tmpdir),
                patch("app.services.user_service.verify_totp", return_value=True),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/api/auth/mfa/verify",
                        json={"totp_code": "123456", "secret": TEST_SECRET},
                    )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 400
        assert user.mfa_secret == TEST_SECRET
