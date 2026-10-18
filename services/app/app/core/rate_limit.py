"""Shared rate limiter instance for the application (SEC-10, GL#28).

Counters live in Redis, not in process memory, so N uvicorn workers enforce one
budget instead of N. Slowapi's in-memory default made "10/minute" mean
"10/minute per worker".

Outage policy, when the store is unreachable:

* ``/api/auth/*`` **fails closed**: the request gets a 503. Login, registration
  and password reset are the brute-force surface; an attacker who can knock Redis
  over must not thereby switch the throttle off.
* everything else **fails open** (logged): a cache outage should not take the
  whole product down. Cost-bearing routes keep their separate AI-call ceilings.

Counting uses a moving window (see ``RATE_LIMIT_STRATEGY``), not a fixed one.

Redis calls are synchronous (``limits``) with short socket timeouts, so an outage
costs at most ``redis_socket_timeout`` per request rather than a hang.
"""

import structlog
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import settings
from app.core.exceptions import RateLimiterUnavailableError
from app.core.login_throttle import LOGIN_THROTTLE_UNAVAILABLE

logger = structlog.get_logger()

#: Counting strategy for every limit. A fixed window opens at the first hit and
#: forgets everything when it closes, so an attacker can spend the budget at the
#: end of one window and again at the start of the next (up to 2x the limit in a
#: moment) and a slow client can straddle the reset by accident. A moving window
#: counts the hits of the last N seconds, so "5/minute" is true at every instant.
#: Supported by both the ``memory://`` and Redis stores. Applied to all limits,
#: not just auth: the cost is one stored timestamp per allowed hit, which is
#: negligible at these budgets, and one rule is easier to hold than two.
RATE_LIMIT_STRATEGY = "moving-window"

#: Paths whose limits protect credentials and therefore fail closed.
FAIL_CLOSED_PREFIXES = ("/api/auth/",)


def resolve_storage_uri(configured: str, redis_url: str) -> str:
    """Pick the limiter storage URI: explicit setting, else the Redis URL."""
    return configured or redis_url


class _OutagePolicyLimiter(Limiter):
    """Limiter that fails closed on auth routes and open elsewhere."""

    def _check_request_limit(self, request: Request, endpoint_func, in_middleware: bool = True):
        try:
            return super()._check_request_limit(request, endpoint_func, in_middleware)
        except RateLimitExceeded:
            raise
        except Exception as exc:
            path = request["path"] or ""
            if path.startswith(FAIL_CLOSED_PREFIXES):
                LOGIN_THROTTLE_UNAVAILABLE.labels(action="limit").inc()
                logger.error("rate_limit_store_down_failing_closed", path=path, error=repr(exc))
                raise RateLimiterUnavailableError("rate limit store unavailable") from exc
            logger.warning("rate_limit_store_down_failing_open", path=path, error=repr(exc))
            request.state.view_rate_limit = None  # decorator reads it for headers
            return None


def build_limiter(storage_uri: str, timeout: float | None = None) -> Limiter:
    """Build a limiter on ``storage_uri`` (``redis://...`` in production)."""
    options: dict[str, float] = {}
    if storage_uri.startswith(("redis://", "rediss://")):
        t = settings.redis_socket_timeout if timeout is None else timeout
        options = {"socket_timeout": t, "socket_connect_timeout": t}
    return _OutagePolicyLimiter(
        key_func=get_remote_address,
        storage_uri=storage_uri,
        storage_options=options,
        key_prefix="studyaio-rl",
        strategy=RATE_LIMIT_STRATEGY,
    )


limiter = build_limiter(resolve_storage_uri(settings.rate_limit_storage_uri, settings.redis_url))
