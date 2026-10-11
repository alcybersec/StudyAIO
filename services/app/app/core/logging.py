"""Structured logging configuration with structlog."""

import logging
import re
import sys
from typing import Any

import structlog

from app.config import settings

#: Deliberately loose: it is better to redact a near-miss than to leak an address.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-']+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
REDACTED_EMAIL = "[redacted-email]"


def _scrub(value: Any) -> Any:
    """Return ``value`` with every address-shaped substring replaced, recursively."""
    if isinstance(value, str):
        return _EMAIL_RE.sub(REDACTED_EMAIL, value)
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_scrub(v) for v in value)
    return value


def redact_emails(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor: no email address survives in any event field (SEC-08).

    Defence in depth behind the call-site rule (log ``user_id``, never an
    address): it covers an address that arrives inside an exception message, a
    provider error or free text. Runs before the renderer.
    """
    return {k: _scrub(v) for k, v in event_dict.items()}


class EmailRedactingFilter(logging.Filter):
    """stdlib counterpart of :func:`redact_emails` for non-structlog records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Rewrite the record's message so no address is emitted; never drops it."""
        message = record.getMessage()
        scrubbed = _EMAIL_RE.sub(REDACTED_EMAIL, message)
        if scrubbed != message:
            record.msg = scrubbed
            record.args = None
        return True


def _should_use_json() -> bool:
    """Determine if JSON renderer should be used based on config."""
    fmt = settings.log_format.lower()
    if fmt == "json":
        return True
    if fmt == "console":
        return False
    # "auto" — use JSON if not running in a terminal (e.g. Docker/CI)
    return not sys.stderr.isatty()


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog with JSON renderer in production, pretty in dev."""
    use_json = _should_use_json()

    renderer = structlog.processors.JSONRenderer() if use_json else structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.processors.format_exc_info,
            redact_emails,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Records that bypass structlog (uvicorn, libraries) get the same redaction.
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, EmailRedactingFilter) for f in handler.filters):
            handler.addFilter(EmailRedactingFilter())
