"""The time zone setting over HTTP, and the zone reaching the day-based routes (R-023)."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.unit.api.test_settings import MOCK_SETTINGS


@pytest.mark.asyncio
class TestTimezoneSetting:
    async def test_get_always_carries_a_timezone(self, async_client):
        with patch(
            "app.api.settings.settings_service.get_user_settings",
            new_callable=AsyncMock,
            return_value=MOCK_SETTINGS,
        ):
            response = await async_client.get("/api/settings")
        assert response.status_code == 200
        assert response.json()["timezone"] == "UTC"

    async def test_put_valid_timezone_is_forwarded(self, async_client, default_test_user):
        with patch(
            "app.api.settings.settings_service.update_user_settings",
            new_callable=AsyncMock,
            return_value={**MOCK_SETTINGS, "timezone": "Europe/Paris"},
        ) as update:
            response = await async_client.put("/api/settings", json={"timezone": "Europe/Paris"})
        assert response.status_code == 200
        assert response.json()["timezone"] == "Europe/Paris"
        assert update.await_args.args[2] == {"timezone": "Europe/Paris"}

    async def test_put_invalid_timezone_is_422_from_the_validator(self, async_client):
        """Real service validation (not a mock) rejects the zone with 422."""
        from unittest.mock import MagicMock

        row = MagicMock(settings_json={}, timezone="UTC")
        with patch(
            "app.services.settings_service._get_or_create_user_settings",
            new_callable=AsyncMock,
            return_value=row,
        ):
            response = await async_client.put("/api/settings", json={"timezone": "Mars/Base"})
        assert response.status_code == 422
        assert "timezone" in response.json()["detail"]
        assert row.timezone == "UTC"


@pytest.mark.asyncio
class TestZoneIsThreaded:
    async def test_streak_route_passes_the_users_zone(self, async_client, default_test_user):
        with (
            patch(
                "app.api.deps.settings_service.get_user_timezone",
                new_callable=AsyncMock,
                return_value="Pacific/Kiritimati",
            ) as lookup,
            patch(
                "app.api.study.streak_service.get_streak",
                new_callable=AsyncMock,
                return_value={"current_streak": 0, "longest_streak": 0, "last_study_date": None},
            ) as streak,
        ):
            response = await async_client.get("/api/study/streak")
        assert response.status_code == 200
        assert lookup.await_args.args[1] == default_test_user.id
        assert streak.await_args.kwargs["tz"] == "Pacific/Kiritimati"
