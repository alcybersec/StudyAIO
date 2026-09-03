"""Error monitoring via Sentry.

Entirely inert unless `SENTRY_DSN` is set, so development, tests and
self-hosted installs pay nothing for it. `sentry_sdk` is an optional
dependency — a missing package degrades to a no-op rather than a crash.

Nothing here may raise: monitoring that takes the process down with it is
worse than no monitoring.
"""

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import structlog

from app.config import settings

logger = structlog.get_logger()

# Request headers that carry credentials verbatim.
SCRUB_HEADERS = frozenset(
    {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}
)

# Structured-data keys whose values are credentials. Magic-link tokens travel
# as `?token=` on password-reset and email-verification URLs, so `token` has to
# be in here even though it also appears in benign contexts.
SCRUB_KEYS = frozenset(
    {
        "password",
        "new_password",
        "current_password",
        "token",
        "access_token",
        "refresh_token",
        "raw_token",
        "token_hash",
        "secret",
        "client_secret",
        "api_key",
        "apikey",
        "jwt_secret_key",
        "authorization",
        "invite_code",
        "totp_code",
        "mfa_secret",
        "credentials",
    }
)

FILTERED = "[Filtered]"

_initialized = False


def _scrub_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Replace values of sensitive keys, in place, case-insensitively."""
    for key in list(data.keys()):
        if isinstance(key, str) and key.lower() in SCRUB_KEYS:
            data[key] = FILTERED
    return data


def _scrub_query(query: str) -> str:
    """Filter sensitive parameters out of a raw query string."""
    if not query:
        return query
    pairs = parse_qsl(query, keep_blank_values=True)
    if not pairs:
        return query
    return urlencode([(k, FILTERED if k.lower() in SCRUB_KEYS else v) for k, v in pairs])


def scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Strip credentials from an event before it leaves the process.

    Wired in as Sentry's `before_send`. Returning None would drop the event, so
    every failure path here returns the event unchanged instead.

    Args:
        event: The Sentry event payload.
        hint: Sentry's hint dict (unused).

    Returns:
        The scrubbed event.
    """
    try:
        request = event.get("request")
        if isinstance(request, dict):
            headers = request.get("headers")
            if isinstance(headers, dict):
                for key in list(headers.keys()):
                    if isinstance(key, str) and key.lower() in SCRUB_HEADERS:
                        headers[key] = FILTERED

            # Cookies are only ever session credentials here.
            request.pop("cookies", None)

            query_string = request.get("query_string")
            if isinstance(query_string, str):
                request["query_string"] = _scrub_query(query_string)

            url = request.get("url")
            if isinstance(url, str) and "?" in url:
                parts = urlsplit(url)
                request["url"] = urlunsplit(
                    (
                        parts.scheme,
                        parts.netloc,
                        parts.path,
                        _scrub_query(parts.query),
                        parts.fragment,
                    )
                )

            data = request.get("data")
            if isinstance(data, dict):
                _scrub_mapping(data)

        for section in ("extra", "tags"):
            value = event.get(section)
            if isinstance(value, dict):
                _scrub_mapping(value)
    except Exception:  # pragma: no cover - defensive
        logger.warning("sentry_scrub_failed", exc_info=True)

    return event


def _build_integrations(component: str) -> list[Any]:
    """Import and construct the integrations for a component.

    Args:
        component: "api" or "worker".

    Returns:
        Integration instances; empty if the optional imports are unavailable.
    """
    integrations: list[Any] = []

    if component == "api":
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        integrations.append(StarletteIntegration())
        integrations.append(FastApiIntegration())
    elif component == "worker":
        from sentry_sdk.integrations.celery import CeleryIntegration

        integrations.append(CeleryIntegration())

    return integrations


def init_sentry(component: str) -> bool:
    """Initialize Sentry for a process, if configured.

    Args:
        component: Which process this is — "api" or "worker". Tags every event
            and selects the framework integrations.

    Returns:
        True if Sentry was initialized, False if it is disabled, the SDK is not
        installed, or initialization failed.
    """
    global _initialized

    if _initialized:
        return True

    dsn = (settings.sentry_dsn or "").strip()
    if not dsn:
        logger.debug("sentry_disabled", reason="no_dsn", component=component)
        return False

    try:
        import sentry_sdk
    except ImportError:
        logger.warning("sentry_sdk_not_installed", component=component)
        return False

    # A stubbed-out module entry (or a failed import cached as None).
    if sentry_sdk is None:
        logger.warning("sentry_sdk_not_installed", component=component)
        return False

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.sentry_environment,
            release=settings.sentry_release or None,
            integrations=_build_integrations(component),
            traces_sample_rate=settings.sentry_traces_sample_rate,
            # Never let Sentry attach request bodies, headers or user identity
            # on its own — `scrub_event` decides what is safe.
            send_default_pii=False,
            before_send=scrub_event,
        )
        sentry_sdk.set_tag("component", component)
    except Exception:
        logger.warning("sentry_init_failed", component=component, exc_info=True)
        return False

    _initialized = True
    logger.info(
        "sentry_initialized",
        component=component,
        environment=settings.sentry_environment,
        release=settings.sentry_release or None,
    )
    return True
