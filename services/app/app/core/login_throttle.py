"""Per-account throttling for failed logins.

Rate limiting keys on the source address, which is the wrong axis for
credential stuffing: an attacker spread across N addresses gets the full
per-address allowance against a single account, N times over, and nothing
counts the failures that account is accumulating. See issue #37.

This counts failures per *account* and slows the caller down as they mount.

**Why a delay and not a lock.** Locking an account on failed attempts is itself
a denial-of-service primitive: anyone who knows a tester's email can lock them
out on purpose, and the victim cannot self-recover. A bounded delay costs an
attacker their throughput — which is the entire value of guessing — while
leaving a legitimate user a working, if briefly slower, login.

**Why it cannot be used to enumerate accounts.** The delay is derived from the
email key alone and applied *before* the password is checked, so an address
with no account behaves exactly like one with an account. It also has to stay
that way: the response after the delay is the same 401 either way, and nothing
tells the caller they are being throttled.

**Redis being down does not break login.** The throttle fails open, loudly. An
auth path that refuses everyone when a cache is unavailable is a worse outcome
than one that is briefly easier to brute-force.
"""

import asyncio
import hashlib
import hmac

import structlog

from app.config import settings
from app.core.utils import normalize_email

logger = structlog.get_logger()

#: Redis key prefix for per-account failure counters.
_KEY_PREFIX = "login_fail:"


def _key(email: str) -> str:
    """Redis key for an email, HMAC'd so the store holds no address list.

    Email addresses are guessable, so this is not secrecy — it means a dump of
    the cache is not a ready-made list of who has accounts and who is under
    attack.

    Args:
        email: The address as supplied by the caller.

    Returns:
        The Redis key.
    """
    # Shares `normalize_email` with the account path so the counter follows the
    # account, not the casing: two spellings of one address must not each get
    # their own clean allowance (issue #91).
    normalized = normalize_email(email).encode()
    digest = hmac.new(
        settings.jwt_secret_key.get_secret_value().encode(), normalized, hashlib.sha256
    ).hexdigest()
    return f"{_KEY_PREFIX}{digest}"


def delay_for(failures: int) -> float:
    """Seconds to wait before answering, given this account's recent failures.

    The first few failures are free — people mistype passwords — and the delay
    then doubles, capped. The cap matters: each delayed request holds a
    connection, so an uncapped backoff would hand an attacker a way to tie up
    the server rather than merely being slowed by it.

    Args:
        failures: Failures recorded in the current window.

    Returns:
        Seconds to sleep; 0.0 below the free threshold.
    """
    over = failures - settings.login_throttle_free_attempts
    if over <= 0:
        return 0.0
    # Clamp the exponent before doubling. A sustained attack drives the counter
    # arbitrarily high, and 2**large overflows when multiplied by a float —
    # turning this guard into a 500 on the login endpoint, which is a better
    # outcome for the attacker than the throttle they were evading. 32 is far
    # past the cap for any sane base delay.
    return min(
        settings.login_throttle_base_delay * (2 ** min(over - 1, 32)),
        settings.login_throttle_max_delay,
    )


async def apply_delay(email: str) -> float:
    """Sleep for this account's current penalty, if any.

    Call **before** verifying the password: the delay must not depend on
    whether the account exists.

    Args:
        email: The address being authenticated.

    Returns:
        The number of seconds actually slept.
    """
    from app.core.redis import redis_client

    try:
        raw = await redis_client.get(_key(email))
    except Exception:
        logger.warning("login_throttle_unavailable", action="read", exc_info=True)
        return 0.0

    delay = delay_for(int(raw or 0))
    if delay > 0:
        await asyncio.sleep(delay)
    return delay


async def record_failure(email: str) -> int:
    """Count a failed attempt against this account.

    The window is refreshed on every failure, so sustained guessing keeps the
    penalty alive while an isolated typo ages out.

    Args:
        email: The address that failed to authenticate.

    Returns:
        The failure count in the current window, or 0 if it could not be recorded.
    """
    from app.core.redis import redis_client

    key = _key(email)
    try:
        failures = await redis_client.incr(key)
        await redis_client.expire(key, settings.login_throttle_window_seconds)
    except Exception:
        logger.warning("login_throttle_unavailable", action="record", exc_info=True)
        return 0

    if failures == settings.login_throttle_free_attempts + 1:
        # Log once, on the transition, rather than on every subsequent attempt.
        logger.warning("login_throttle_engaged", failures=failures)
    return int(failures)


async def clear(email: str) -> None:
    """Forget this account's failures after a successful authentication.

    Args:
        email: The address that authenticated.
    """
    from app.core.redis import redis_client

    try:
        await redis_client.delete(_key(email))
    except Exception:
        logger.warning("login_throttle_unavailable", action="clear", exc_info=True)
