"""The per-account login throttle must really run under the unit-suite Redis fake.

`FakeRedis` once lacked `incr`/`expire`, so `record_failure` raised
`AttributeError`, logged `login_throttle_unavailable` and failed open. Every
unit test then exercised a login path with the throttle silently off. These
tests use the autouse fake (not an `AsyncMock`) so that gap cannot reopen.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.core import login_throttle


class TestFakeRedisCounters:
    @pytest.mark.asyncio
    async def test_incr_counts_from_one_and_is_shared_across_clients(self, fake_redis):
        assert await fake_redis().incr("k") == 1
        assert await fake_redis().incr("k") == 2
        assert await fake_redis().get("k") == "2"

    @pytest.mark.asyncio
    async def test_expire_sets_a_ttl_and_the_key_lapses(self, fake_redis):
        client = fake_redis()
        await client.incr("k")
        assert await client.expire("k", 60) is True
        assert 0 < await client.ttl("k") <= 60
        later = time.monotonic() + 61
        with patch("time.monotonic", return_value=later):
            assert await client.get("k") is None
            assert await client.incr("k") == 1  # a lapsed counter restarts

    @pytest.mark.asyncio
    async def test_expire_and_ttl_on_missing_keys(self, fake_redis):
        client = fake_redis()
        assert await client.expire("nope", 5) is False
        assert await client.ttl("nope") == -2
        await client.set("forever", "x")
        assert await client.ttl("forever") == -1


class TestThrottleEngagesUnderTheFake:
    @pytest.mark.asyncio
    async def test_failures_are_counted_not_swallowed(self, fake_redis):
        with patch.object(login_throttle.logger, "warning") as warn:
            counts = [await login_throttle.record_failure("v@example.com") for _ in range(3)]
        assert counts == [1, 2, 3]
        assert not [c for c in warn.call_args_list if c.args[:1] == ("login_throttle_unavailable",)]

    @pytest.mark.asyncio
    async def test_the_delay_engages_after_the_free_attempts(self, fake_redis):
        for _ in range(settings.login_throttle_free_attempts):
            await login_throttle.record_failure("v@example.com")
        with patch("app.core.login_throttle.asyncio.sleep", new_callable=AsyncMock) as sleep:
            assert await login_throttle.apply_delay("v@example.com") == 0.0
            await login_throttle.record_failure("v@example.com")
            slept = await login_throttle.apply_delay("v@example.com")
        assert slept == settings.login_throttle_base_delay
        sleep.assert_awaited_once_with(settings.login_throttle_base_delay)

    @pytest.mark.asyncio
    async def test_clear_resets_the_account(self, fake_redis):
        for _ in range(settings.login_throttle_free_attempts + 2):
            await login_throttle.record_failure("v@example.com")
        await login_throttle.clear("v@example.com")
        with patch("app.core.login_throttle.asyncio.sleep", new_callable=AsyncMock) as sleep:
            assert await login_throttle.apply_delay("v@example.com") == 0.0
        sleep.assert_not_awaited()
