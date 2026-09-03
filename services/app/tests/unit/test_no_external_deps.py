"""Guards that keep `tests/unit/` free of external dependencies.

`.claude/rules/tests.md` requires unit tests to be fast and fully mocked. The
rule was silently violated for a while: several endpoints touch Redis on the
side, and because `redis://redis:6379/0` is a Compose hostname, running
`pytest tests/unit` outside Compose **hung forever** rather than failing. CI
hid it by providing Redis as a service container.

`tests/unit/conftest.py` fakes Redis for every module that imports it. The list
there is hand-maintained, so this file checks it against the actual source.
"""

import ast
import re
from pathlib import Path

import pytest

from tests.unit.conftest import REDIS_IMPORTING_MODULES, FakeRedis

APP_ROOT = Path(__file__).parents[2] / "app"


def _modules_importing_redis() -> set[str]:
    """Every app module that imports the Redis client class.

    Parses the AST rather than grepping, so a mention in a comment or docstring
    does not count.
    """
    found: set[str] = set()
    for path in APP_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - would fail the build elsewhere
            continue
        for node in ast.walk(tree):
            imports_redis = (
                isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("redis")
                and any(alias.name == "Redis" for alias in node.names)
            )
            if imports_redis:
                rel = path.relative_to(APP_ROOT.parent).with_suffix("")
                found.add(".".join(rel.parts))
    return found


class TestRedisIsAlwaysFaked:
    """Every module holding a Redis client must be covered by the fake."""

    def test_conftest_covers_every_module_that_imports_redis(self):
        actual = _modules_importing_redis()
        listed = set(REDIS_IMPORTING_MODULES)
        missing = actual - listed
        assert missing == set(), (
            "These modules construct a Redis client but are not faked in "
            f"tests/unit/conftest.py: {sorted(missing)}. Add them to "
            "REDIS_IMPORTING_MODULES, or their unit tests will hang for anyone "
            "without a local Redis instead of failing with a useful message."
        )

    def test_the_list_has_no_dead_entries(self):
        stale = set(REDIS_IMPORTING_MODULES) - _modules_importing_redis()
        assert stale == set(), (
            f"REDIS_IMPORTING_MODULES lists modules that no longer import Redis: {sorted(stale)}"
        )

    @pytest.mark.asyncio
    async def test_cache_helpers_run_against_the_fake(self):
        """The real cache code still executes — it just has no socket."""
        from app.core.cache import cache_delete, cache_get, cache_set

        await cache_set("cache:probe", {"hello": "world"}, ttl=60)
        assert await cache_get("cache:probe") == {"hello": "world"}

        await cache_delete("cache:probe")
        assert await cache_get("cache:probe") is None

    @pytest.mark.asyncio
    async def test_redis_connectivity_check_uses_the_fake(self):
        from app.core.cache import check_redis_connectivity

        assert await check_redis_connectivity() is True

    def test_the_fake_is_installed_in_the_cache_module(self):
        from app.core import cache

        assert cache.Redis is FakeRedis


class TestRedisFailsFastInProduction:
    """A hang is not an acceptable failure mode for a best-effort cache."""

    def test_socket_timeouts_are_configured(self):
        from app.config import settings

        assert settings.redis_socket_timeout > 0

    @pytest.mark.parametrize(
        "module_path",
        ["app/core/cache.py", "app/core/oauth.py", "app/core/redis.py"],
    )
    def test_every_client_sets_a_connect_timeout(self, module_path):
        """Without a connect timeout an unreachable Redis blocks forever.

        The cache helpers all promise "best-effort, never raises" — a promise
        they cannot keep if the connect never returns to reach the except.
        """
        source = (APP_ROOT.parent / module_path).read_text(encoding="utf-8")
        constructions = source.count("Redis.from_url(")
        timeouts = len(re.findall(r"socket_connect_timeout=", source))
        assert timeouts == constructions, (
            f"{module_path} builds {constructions} Redis client(s) but sets "
            f"{timeouts} connect timeout(s)"
        )
