"""SEC-10 (GL#28): rate-limit counters are shared across processes via Redis."""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from limits.storage import MemoryStorage
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.exceptions import RateLimiterUnavailableError
from app.core.rate_limit import build_limiter, resolve_storage_uri


class _SharedStorage(MemoryStorage):
    """Stands in for one Redis server seen by several processes."""

    STORAGE_SCHEME = ["sharedtest"]
    _instance = None

    def __new__(cls, *a, **kw):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ready = False
        return cls._instance

    def __init__(self, *a, **kw):
        if not self._ready:
            super().__init__(*a, **kw)
            self._ready = True


class _DeadStorage(MemoryStorage):
    STORAGE_SCHEME = ["deadtest"]

    def incr(self, *a, **kw):
        raise ConnectionError("redis down")

    def get_moving_window(self, *a, **kw):
        raise ConnectionError("redis down")

    def acquire_entry(self, *a, **kw):
        raise ConnectionError("redis down")

    def check(self):
        return False


def _make_app(uri: str) -> FastAPI:
    """One 'process': its own limiter and app; only the storage URI is common."""
    lim = build_limiter(uri)
    app = FastAPI()
    app.state.limiter = lim
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.exception_handler(RateLimiterUnavailableError)
    async def _unavailable(request, exc):
        return JSONResponse(status_code=503, content={"detail": "x"})

    @app.get("/api/thing")
    @lim.limit("3/minute")
    async def thing(request: Request):
        return {"ok": True}

    @app.get("/api/auth/login")
    @lim.limit("3/minute")
    async def login(request: Request):
        return {"ok": True}

    return app


def _client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.asyncio
async def test_two_instances_share_the_budget():
    _SharedStorage._instance = None
    a, b = _make_app("sharedtest://"), _make_app("sharedtest://")
    async with _client(a) as ca, _client(b) as cb:
        codes = [(await c.get("/api/thing")).status_code for c in (ca, cb, ca, cb)]
    # 3/minute in total across both processes, not 3 each
    assert codes == [200, 200, 200, 429]


@pytest.mark.asyncio
async def test_separate_storage_is_the_per_process_baseline():
    a, b = _make_app("memory://"), _make_app("memory://")
    async with _client(a) as ca, _client(b) as cb:
        codes = [(await c.get("/api/thing")).status_code for c in (ca, cb, ca, cb)]
    assert codes == [200, 200, 200, 200]


@pytest.mark.asyncio
async def test_storage_outage_fails_closed_for_auth_endpoints():
    async with _client(_make_app("deadtest://")) as c:
        assert (await c.get("/api/auth/login")).status_code == 503


@pytest.mark.asyncio
async def test_storage_outage_fails_open_for_other_endpoints():
    async with _client(_make_app("deadtest://")) as c:
        assert (await c.get("/api/thing")).status_code == 200


def test_storage_uri_defaults_to_redis_url():
    assert resolve_storage_uri("", "redis://redis:6379/0") == "redis://redis:6379/0"
    assert resolve_storage_uri("memory://", "redis://x/0") == "memory://"
