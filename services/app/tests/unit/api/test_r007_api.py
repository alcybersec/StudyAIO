"""R-007 API wiring: leaderboard sees the caller; settings carry the opt-in flag."""

from unittest.mock import AsyncMock, patch

import pytest

from app.api.schemas import SettingsResponse, SettingsUpdateRequest


@pytest.mark.asyncio
async def test_leaderboard_endpoint_passes_caller(async_client, default_test_user):
    with patch(
        "app.api.gamification.xp_service.get_leaderboard",
        new_callable=AsyncMock,
        return_value=[],
    ) as lb:
        resp = await async_client.get("/api/gamification/leaderboard")
    assert resp.status_code == 200
    assert lb.await_args.kwargs.get("user_id") == default_test_user.id  # load-bearing


def test_settings_response_defaults_flag_false():
    fields = SettingsResponse.model_fields
    assert "leaderboard_opt_in" in fields
    assert fields["leaderboard_opt_in"].default is False


def test_settings_update_accepts_flag_and_marks_it_set():
    body = SettingsUpdateRequest(leaderboard_opt_in=True)
    assert body.model_dump(exclude_unset=True) == {"leaderboard_opt_in": True}
