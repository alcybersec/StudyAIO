"""Tests for per-account login throttling (issue #37).

Rate limiting keys on the source address, which a distributed attacker simply
spreads across. These slow down guessing against the *account*.

The two properties that matter beyond "it counts": a throttled account must not
be distinguishable from a nonexistent one, and Redis being unavailable must not
make login impossible.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.core import login_throttle


@pytest.fixture
def fake_redis():
    redis = AsyncMock()
    with patch("app.core.redis.redis_client", redis):
        yield redis


class TestDelayCurve:
    def test_the_first_attempts_are_free(self):
        """People mistype passwords; the first few must cost nothing."""
        for failures in range(settings.login_throttle_free_attempts + 1):
            assert login_throttle.delay_for(failures) == 0.0

    def test_the_delay_grows(self):
        free = settings.login_throttle_free_attempts
        first = login_throttle.delay_for(free + 1)
        second = login_throttle.delay_for(free + 2)
        assert 0 < first < second

    def test_the_delay_is_capped(self):
        """Uncapped backoff would let an attacker tie up connections rather than
        merely be slowed by them."""
        assert login_throttle.delay_for(10_000) == settings.login_throttle_max_delay


class TestKeying:
    def test_the_address_is_not_stored_in_the_clear(self):
        key = login_throttle._key("victim@example.com")
        assert "victim@example.com" not in key
        assert key.startswith("login_fail:")

    def test_case_and_whitespace_do_not_create_separate_buckets(self):
        """Otherwise an attacker resets the counter by changing capitalisation."""
        assert login_throttle._key("  Victim@Example.COM ") == login_throttle._key(
            "victim@example.com"
        )


class TestCounting:
    @pytest.mark.asyncio
    async def test_a_failure_increments_and_sets_the_window(self, fake_redis):
        fake_redis.incr.return_value = 3

        failures = await login_throttle.record_failure("a@example.com")

        assert failures == 3
        fake_redis.expire.assert_awaited_once()
        assert fake_redis.expire.await_args.args[1] == settings.login_throttle_window_seconds

    @pytest.mark.asyncio
    async def test_success_clears_the_counter(self, fake_redis):
        await login_throttle.clear("a@example.com")
        fake_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delay_is_applied_from_the_stored_count(self, fake_redis):
        fake_redis.get.return_value = str(settings.login_throttle_free_attempts + 1)

        with patch("asyncio.sleep", AsyncMock()) as sleep:
            slept = await login_throttle.apply_delay("a@example.com")

        assert slept == settings.login_throttle_base_delay
        sleep.assert_awaited_once_with(settings.login_throttle_base_delay)

    @pytest.mark.asyncio
    async def test_no_history_means_no_delay(self, fake_redis):
        fake_redis.get.return_value = None

        with patch("asyncio.sleep", AsyncMock()) as sleep:
            assert await login_throttle.apply_delay("a@example.com") == 0.0

        sleep.assert_not_awaited()


class TestFailsOpen:
    """An auth path that refuses everyone when a cache is down is a worse outcome."""

    @pytest.mark.asyncio
    async def test_a_read_failure_does_not_delay(self, fake_redis):
        fake_redis.get.side_effect = ConnectionError("redis down")
        assert await login_throttle.apply_delay("a@example.com") == 0.0

    @pytest.mark.asyncio
    async def test_a_write_failure_does_not_raise(self, fake_redis):
        fake_redis.incr.side_effect = ConnectionError("redis down")
        assert await login_throttle.record_failure("a@example.com") == 0

    @pytest.mark.asyncio
    async def test_a_clear_failure_does_not_raise(self, fake_redis):
        fake_redis.delete.side_effect = ConnectionError("redis down")
        await login_throttle.clear("a@example.com")
