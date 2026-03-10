"""Structured logging configuration with structlog."""

import logging
import sys

import structlog

from app.config import settings


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
