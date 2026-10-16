"""Contract test for `core.login-throttle-metrics v1` (docs/CONTRACTS.md, M34-S3-BACKEND-012).

Pins:

1. ``login_throttle.LOGIN_THROTTLE_UNAVAILABLE`` is the entry's counter: same
   name, same single ``action`` label.
2. With a store that raises, each of ``apply_delay``, ``record_failure`` and
   ``clear`` advances it once under its own ``action`` and still fails open
   (no exception, no delay).
3. The limiter's fail-closed branch on an ``/api/auth/`` path advances
   ``action="limit"`` and still raises ``RateLimiterUnavailableError``; its
   fail-open branch elsewhere does not count.
4. The series is on the default registry, so ``/metrics`` exports it.

Red until ``backend`` adds the counter (M34-S3-BACKEND-012).
"""

import ast

import pytest
from prometheus_client import REGISTRY, generate_latest

from tests.contracts._weakspot_docs import contract_section, python_block

HEADING = "### core.login-throttle-metrics v1"
METRIC = "studyaio_login_throttle_unavailable_total"
EMAIL = "someone@example.test"


class _DownStore:
    """A Redis client whose every call fails like an unreachable server."""

    def __getattr__(self, name):
        async def _fail(*args, **kwargs):
            raise ConnectionError("store unreachable")

        return _fail


@pytest.fixture(scope="module")
def counter():
    from app.core import login_throttle

    found = getattr(login_throttle, "LOGIN_THROTTLE_UNAVAILABLE", None)
    assert found is not None, "login_throttle.LOGIN_THROTTLE_UNAVAILABLE does not exist yet"
    return found


def _value(action: str) -> float:
    return REGISTRY.get_sample_value(METRIC, {"action": action}) or 0.0


def test_definition_matches_the_entry(counter):
    block = python_block(contract_section(HEADING), HEADING)
    call = block.body[0].value
    assert isinstance(call, ast.Call)
    name, _help, labels = (ast.literal_eval(a) for a in call.args)
    assert name == METRIC
    assert counter._type == "counter"
    assert f"{counter._name}_total" == name
    assert tuple(counter._labelnames) == tuple(labels) == ("action",)


@pytest.fixture
def down_store(monkeypatch):
    from app.core import redis as redis_mod

    monkeypatch.setattr(redis_mod, "redis_client", _DownStore())


@pytest.mark.parametrize(
    ("action", "call"),
    [
        ("read", lambda lt: lt.apply_delay(EMAIL)),
        ("record", lambda lt: lt.record_failure(EMAIL)),
        ("clear", lambda lt: lt.clear(EMAIL)),
    ],
)
async def test_each_throttle_operation_counts_and_fails_open(counter, down_store, action, call):
    from app.core import login_throttle

    before = _value(action)
    result = await call(login_throttle)
    assert result in (None, 0, 0.0), f"{action}: did not fail open ({result!r})"
    assert _value(action) == before + 1, f"{action}: counter did not advance by one"


def _limiter_call(monkeypatch, path: str):
    from slowapi import Limiter

    from app.core.rate_limit import build_limiter

    def _store_down(self, request, endpoint_func, in_middleware=True):
        raise ConnectionError("store unreachable")

    monkeypatch.setattr(Limiter, "_check_request_limit", _store_down)
    limiter = build_limiter("memory://")

    class _Request(dict):
        state = type("State", (), {})()

    return lambda: limiter._check_request_limit(_Request(path=path), None)


def test_fail_closed_limiter_counts_as_limit(counter, monkeypatch):
    from app.core.exceptions import RateLimiterUnavailableError

    before = _value("limit")
    with pytest.raises(RateLimiterUnavailableError):
        _limiter_call(monkeypatch, "/api/auth/login")()
    assert _value("limit") == before + 1


def test_fail_open_limiter_is_not_counted(counter, monkeypatch):
    before = {a: _value(a) for a in ("read", "record", "clear", "limit")}
    assert _limiter_call(monkeypatch, "/api/courses")() is None
    assert {a: _value(a) for a in before} == before


def test_exported_on_the_default_registry(counter):
    counter.labels(action="read")
    assert METRIC.encode() in generate_latest(REGISTRY)
