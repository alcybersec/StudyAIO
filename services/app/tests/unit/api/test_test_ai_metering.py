"""M32 gate N-1: POST /api/settings/test-ai is metered when it spends the instance's key."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import GlobalCeilingError, QuotaExceededError

URL = "/api/settings/test-ai"
CHECK_AI = "app.services.quota_service.check_ai_quota"
RECORD = "app.api.settings.billing_service.record_ai_call"
CONFIG = "app.services.settings_service.get_user_agent_config"
GET_AGENT = "app.agents.factory.get_agent"
OWN = {"agent_backend": "openai", "openai_api_key": "sk-own"}


def _agent(fail: bool = False) -> MagicMock:
    agent = MagicMock()
    result = MagicMock(confidence=0.9)
    agent.classify_lecture = AsyncMock(
        side_effect=RuntimeError("boom") if fail else None, return_value=result
    )
    return agent


@pytest.mark.asyncio
class TestInstanceProvider:
    async def test_quota_is_checked_for_the_caller_then_usage_recorded(
        self, async_client, default_test_user
    ):
        agent = _agent()
        with (
            patch(CONFIG, new_callable=AsyncMock, return_value=None),
            patch(GET_AGENT, return_value=agent),
            patch(CHECK_AI, new_callable=AsyncMock) as check,
            patch(RECORD, new_callable=AsyncMock) as record,
        ):
            response = await async_client.post(URL)

        assert response.status_code == 200
        assert check.await_count == 1
        assert check.await_args.args[1] == default_test_user.id  # load-bearing
        assert record.await_count == 1
        assert record.await_args.args[1] == default_test_user.id  # load-bearing

    @pytest.mark.parametrize(
        "error",
        [QuotaExceededError("ai_calls", 20, "day"), GlobalCeilingError("AI call", 100, 60)],
    )
    async def test_refused_before_the_agent_is_built_or_called(self, async_client, error):
        agent = _agent()
        with (
            patch(CONFIG, new_callable=AsyncMock, return_value=None),
            patch(GET_AGENT, return_value=agent) as get_agent,
            patch(CHECK_AI, AsyncMock(side_effect=error)),
            patch(RECORD, new_callable=AsyncMock) as record,
        ):
            response = await async_client.post(URL)

        assert response.status_code in (402, 429)
        get_agent.assert_not_called()
        agent.classify_lecture.assert_not_awaited()
        record.assert_not_awaited()

    async def test_failed_call_is_still_metered(self, async_client):
        with (
            patch(CONFIG, new_callable=AsyncMock, return_value=None),
            patch(GET_AGENT, return_value=_agent(fail=True)),
            patch(CHECK_AI, new_callable=AsyncMock),
            patch(RECORD, new_callable=AsyncMock) as record,
        ):
            response = await async_client.post(URL)

        assert response.status_code == 502
        assert record.await_count == 1


@pytest.mark.asyncio
class TestOwnCredentials:
    async def test_not_metered_against_the_instance(self, async_client):
        with (
            patch(CONFIG, new_callable=AsyncMock, return_value=OWN),
            patch(GET_AGENT, return_value=_agent()),
            patch(CHECK_AI, new_callable=AsyncMock) as check,
            patch(RECORD, new_callable=AsyncMock) as record,
        ):
            response = await async_client.post(URL)

        assert response.status_code == 200
        check.assert_not_awaited()
        record.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("config", [None, OWN], ids=["instance", "own"])
async def test_rate_limited_to_five_per_minute(async_client, config):
    with (
        patch(CONFIG, new_callable=AsyncMock, return_value=config),
        patch(GET_AGENT, return_value=_agent()),
        patch(CHECK_AI, new_callable=AsyncMock),
        patch(RECORD, new_callable=AsyncMock),
    ):
        statuses = [(await async_client.post(URL)).status_code for _ in range(6)]

    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429
