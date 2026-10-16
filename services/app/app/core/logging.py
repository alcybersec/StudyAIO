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

#: SQLAlchemy's `[parameters: ...]` section echoes bound values (tokens, emails,
#: ciphertext). Engines hide it; this is the backstop. Runs to the "(Background on
#: this error" trailer, or end of text, since the value may itself contain `]`.
_PARAMS_RE = re.compile(r"\[parameters:.*?(?=\n\(Background on this error|\Z)", re.DOTALL)
REDACTED_PARAMS = "[parameters: redacted]"


def _scrub_text(text: str) -> str:
    """Redact bound-parameter sections and address-shaped substrings in ``text``."""
    return _EMAIL_RE.sub(REDACTED_EMAIL, _PARAMS_RE.sub(REDACTED_PARAMS, text))


def _scrub(value: Any) -> Any:
    """Return ``value`` with every address-shaped substring replaced, recursively."""
    if isinstance(value, str):
        return _scrub_text(value)
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
        """Rewrite message, traceback and stack text so no address is emitted.

        ``Logger.exception`` (and ``exc_info=True``) make the stdlib Formatter
        append a traceback after the message; it is rendered here first and cached
        in ``exc_text`` (which the Formatter reuses) so it can be scrubbed too.
        Never drops the record. Only handlers carrying this filter are covered: a
        handler attached after :func:`configure_logging` must add it itself.
        """
        message = record.getMessage()
        scrubbed = _scrub_text(message)
        if scrubbed != message:
            record.msg = scrubbed
            record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = _scrub_text(record.exc_text)
        if record.stack_info:
            record.stack_info = _scrub_text(record.stack_info)
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
