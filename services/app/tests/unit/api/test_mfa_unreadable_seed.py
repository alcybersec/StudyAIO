"""Unreadable TOTP seed (``mfa_secret`` reads ``None``): backup codes still work (M34-S2-SEC-005)."""

import json
from unittest.mock import AsyncMock, patch

import pytest


def _user(make_user):
    return make_user(
        id="user-mfa-002",
        email="seedless@example.com",
        mfa_enabled=True,
        mfa_secret=None,
        backup_codes=json.dumps(["digest-a"]),
    )


@pytest.fixture
def throttle():
    with (
        patch("app.api.auth.login_throttle.apply_delay", new_callable=AsyncMock),
        patch("app.api.auth.login_throttle.record_failure", new_callable=AsyncMock) as record,
        patch("app.api.auth.login_throttle.clear", new_callable=AsyncMock),
    ):
        yield record


async def test_backup_code_signs_in_when_the_seed_is_unreadable(async_client, make_user, throttle):
    user = _user(make_user)
    with (
        patch(
            "app.api.auth.user_service.authenticate_user",
            new_callable=AsyncMock,
            return_value=user,
        ),
        patch(
            "app.api.auth.user_service.consume_backup_code",
            new_callable=AsyncMock,
            return_value=0,
        ) as consume,
    ):
        response = await async_client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "TestPass1!", "backup_code": "abcd-efgh"},
        )

    assert response.status_code == 200, response.text
    consume.assert_awaited_once()
    assert consume.await_args.args[1] is user  # load-bearing: the account's own backup codes
    throttle.assert_not_awaited()


async def test_missing_code_is_still_required_not_a_bypass(async_client, make_user, throttle):
    user = _user(make_user)
    with patch(
        "app.api.auth.user_service.authenticate_user", new_callable=AsyncMock, return_value=user
    ):
        response = await async_client.post(
            "/api/auth/login", json={"email": user.email, "password": "TestPass1!"}
        )
    assert response.status_code == 403
    assert "access_token" not in response.cookies
    throttle.assert_awaited_once_with(user.email)
