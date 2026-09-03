"""Unit-test fixtures.

`.claude/rules/tests.md` requires `tests/unit/` to be fast and free of external
dependencies. Several endpoints reach Redis on the side — the dashboard cache,
SSE event publishing, OAuth state — so without this file those "unit" tests
quietly need a live server.

The failure mode was not a clean error, either: `redis://redis:6379/0` is a
Docker Compose hostname, so outside Compose the client blocks on connect and the
test **hangs forever** instead of failing. CI hid it by providing Redis as a
service container.

`fake_redis` (autouse) swaps in an in-memory stand-in everywhere `Redis` is
imported, so the real cache/oauth/event code still executes — and is still
covered — without a socket.
"""

import fnmatch
import time

import pytest

# Modules that do `from redis.asyncio import Redis` and construct their own
# client. Each binds `Redis` into its own namespace, so each must be patched.
REDIS_IMPORTING_MODULES = (
    "app.core.cache",
    "app.core.oauth",
    "app.core.redis",
    "app.api.uploads",
    "app.services.event_service",
)


class FakeRedis:
    """Minimal in-memory stand-in for `redis.asyncio.Redis`.

    Implements only what the app actually calls: get/setex/delete/scan/ping,
    publish, pubsub and aclose. Anything else should raise loudly rather than
    silently pass, so a new Redis call site is noticed here rather than
    discovered as a hang on someone's laptop.
    """

    # Shared across instances: the app builds a new client per call, but a
    # value written by one must be readable by the next, like a real server.
    _store: dict[str, tuple[str, float | None]] = {}
    published: list[tuple[str, str]] = []

    def __init__(self, *args, **kwargs) -> None:
        self.closed = False

    @classmethod
    def from_url(cls, *args, **kwargs) -> "FakeRedis":
        return cls()

    @classmethod
    def reset(cls) -> None:
        cls._store = {}
        cls.published = []

    def _live(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self._live(key)

    async def set(self, key: str, value: str) -> bool:
        self._store[key] = (value, None)
        return True

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        self._store[key] = (value, time.monotonic() + ttl)
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if self._store.pop(key, None) is not None:
                removed += 1
        return removed

    async def scan(self, cursor: int = 0, match: str = "*", count: int = 100):
        keys = [k for k in list(self._store) if fnmatch.fnmatch(k, match)]
        return 0, keys

    async def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1

    def pubsub(self) -> "FakePubSub":
        return FakePubSub()

    async def aclose(self) -> None:
        self.closed = True

    async def close(self) -> None:
        self.closed = True


class FakePubSub:
    """Stand-in for a Redis pub/sub subscription that yields nothing."""

    async def subscribe(self, *channels: str) -> None:
        return None

    async def unsubscribe(self, *channels: str) -> None:
        return None

    async def get_message(self, *args, **kwargs) -> None:
        return None

    async def aclose(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Replace Redis with an in-memory fake in every module that imports it.

    Autouse: a unit test must never open a socket, and opting in per test is
    exactly the kind of thing that gets forgotten.
    """
    FakeRedis.reset()

    for module_path in REDIS_IMPORTING_MODULES:
        module = pytest.importorskip(module_path)
        if hasattr(module, "Redis"):
            monkeypatch.setattr(module, "Redis", FakeRedis)
        # app.core.redis builds a module-level client at import time.
        if hasattr(module, "redis_client"):
            monkeypatch.setattr(module, "redis_client", FakeRedis())

    yield FakeRedis

    FakeRedis.reset()
