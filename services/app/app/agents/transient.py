"""Classify AI failures as transient (worth retrying) or permanent (TECH-04, GL#22).

A transient failure is one the same request may well survive a minute later:
a timeout, a 429, a 5xx, a dropped connection. Everything else (auth, bad
request, unparseable output, missing credential) fails fast, exactly as before.
"""

import re

import httpx

from app.core.exceptions import AgentError


class TransientAgentError(AgentError):
    """An AgentError caused by a condition expected to clear on its own."""


#: Statuses worth retrying: request timeout, too early, rate limit, any 5xx.
_TRANSIENT_STATUSES = frozenset({408, 425, 429})

#: SDK exception class names (anthropic / openai / ollama). Matched by name so the
#: classifier needs no import of every SDK.
_TRANSIENT_CLASS_NAMES = frozenset(
    {
        "APITimeoutError",
        "APIConnectionError",
        "RateLimitError",
        "InternalServerError",
        "OverloadedError",
        "ServiceUnavailableError",
    }
)

_TRANSIENT_TEXT = re.compile(
    r"\b(?:408|425|429|50[0-9]|52[0-9])\b|rate[ _-]?limit|overloaded|"
    r"econnreset|connection reset|connection (?:aborted|refused)|"
    r"temporarily unavailable|service unavailable|timed? ?out",
    re.IGNORECASE,
)


def is_transient_error(exc: BaseException) -> bool:
    """True when ``exc`` (an SDK or network exception) is worth retrying."""
    if isinstance(exc, (TimeoutError, ConnectionError, httpx.TransportError)):
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status in _TRANSIENT_STATUSES or 500 <= status < 600
    return any(cls.__name__ in _TRANSIENT_CLASS_NAMES for cls in type(exc).__mro__)


def is_transient_text(text: str) -> bool:
    """True when CLI output describes a transient failure."""
    return bool(text and _TRANSIENT_TEXT.search(text))
