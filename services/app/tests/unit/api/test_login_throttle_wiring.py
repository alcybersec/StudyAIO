"""The per-account throttle must actually be reached from the login endpoint.

The throttle's own unit tests all pass with the calls deleted from the
endpoint, which is the failure shape this project has hit before: correct code
that nothing invokes. These assert the wiring, and the two behavioural
properties that only exist at the endpoint — a failure is recorded, a success
clears the record, and a nonexistent account is treated identically to a real
one.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.api.test_auth import _make_db_user


@pytest.fixture
def throttle():
    """Patch the throttle as the endpoint sees it."""
    with (
        patch("app.api.auth.login_throttle.apply_delay", new_callable=AsyncMock) as delay,
        patch("app.api.auth.login_throttle.record_failure", new_callable=AsyncMock) as record,
        patch("app.api.auth.login_throttle.clear", new_callable=AsyncMock) as clear,
    ):
        delay.return_value = 0.0
        yield MagicMock(apply_delay=delay, record_failure=record, clear=clear)


@pytest.mark.asyncio
async def test_the_delay_is_applied_before_authenticating(async_client, mock_session, throttle):
    """Before, not after — the delay must not depend on the account existing."""
    with patch(
        "app.api.auth.user_service.authenticate_user",
        new_callable=AsyncMock,
        return_value=_make_db_user(),
    ):
        await async_client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "TestPass1!"},
        )

    throttle.apply_delay.assert_awaited_once()
    assert throttle.apply_delay.await_args.args[0] == "test@example.com"


@pytest.mark.asyncio
async def test_a_successful_login_clears_the_record(async_client, mock_session, throttle):
    with patch(
        "app.api.auth.user_service.authenticate_user",
        new_callable=AsyncMock,
        return_value=_make_db_user(),
    ):
        response = await async_client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "TestPass1!"},
        )

    assert response.status_code == 200
    throttle.clear.assert_awaited_once()
    throttle.record_failure.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_wrong_password_is_recorded(async_client, mock_session, throttle):
    result = MagicMock()
    result.scalar_one_or_none.return_value = _make_db_user()
    mock_session.execute.return_value = result

    response = await async_client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "WrongPass1!"},
    )

    assert response.status_code == 401
    throttle.record_failure.assert_awaited_once()
    throttle.clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_unknown_account_is_treated_identically(async_client, mock_session, throttle):
    """Otherwise the throttle itself becomes an account-enumeration oracle."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result

    response = await async_client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "AnyPass1!"},
    )

    assert response.status_code == 401
    throttle.apply_delay.assert_awaited_once()
    throttle.record_failure.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_wrong_mfa_code_counts_as_a_failure(async_client, mock_session, throttle):
    """An attacker holding the password must not get unlimited codes to guess."""
    user = _make_db_user(mfa_enabled=True, mfa_secret="<test-placeholder>")

    with (
        patch(
            "app.api.auth.user_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=user,
        ),
        patch("app.api.auth.verify_totp", return_value=False),
    ):
        response = await async_client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "TestPass1!", "totp_code": "000000"},
        )

    assert response.status_code == 403
    throttle.record_failure.assert_awaited_once()
    throttle.clear.assert_not_awaited()
