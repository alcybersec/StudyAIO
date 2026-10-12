"""Floor 2 (personal data out of logs): no email address in any log line (GL#38, SEC-08).

M33-S1-SAFETY-033 over backend ``40474fb``. Floor 2 already keeps credentials
out of logs; the consent work extends the same discipline to email addresses
and to the free text users type into AI feedback. Pins:

* **call sites**: no log call in ``app/`` passes an address-bearing value, in a
  keyword, a positional, an f-string, a ``["email"]`` subscript or a
  ``.get("email")``. This is the backend's sweep
  (``tests/unit/core/test_log_email_redaction.py``) widened: any identifier
  *ending* in ``email`` (``user_email``, ``owner.email``), recipients, the
  ``.log``/``.msg``/``.fatal`` methods and ``bind_contextvars``;
* **wiring**: after ``configure_logging`` the ``redact_emails`` processor runs
  after ``format_exc_info`` (so tracebacks are scrubbed) and immediately
  before the renderer, and every root handler carries ``EmailRedactingFilter``;
  a structlog line that carries an address in a field, the event or an
  exception reaches the handler stream without it;
* **payloads**: the profile response never exposes the raw consent record,
  and an AI feedback comment never reaches a usage event or a log line.
"""

from __future__ import annotations

import ast
import io
import logging
import re
from datetime import UTC, datetime

import pytest
import structlog

from tests.safety._source import APP_ROOT, parse, rel

LOG_METHODS = frozenset(
    {
        "debug",
        "info",
        "warning",
        "warn",
        "error",
        "exception",
        "critical",
        "fatal",
        "msg",
        "log",
        "bind",
        "new",
    }
)
CONTEXT_BINDERS = frozenset({"bind_contextvars"})
RECIPIENT_NAMES = frozenset(
    {"to", "recipient", "recipients", "to_addr", "to_address", "address", "addresses"}
)
_EMAIL_IDENT = re.compile(r"(^|_)e?mails?$|(^|_)email_?addr(ess)?(es)?$", re.IGNORECASE)


def is_email_ident(name: str | None) -> bool:
    """``email``, ``user_email``, ``emails``, ``email_address``; not ``email_verified``."""
    return bool(name) and (bool(_EMAIL_IDENT.search(name)) or name.lower() in RECIPIENT_NAMES)


def _is_log_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in CONTEXT_BINDERS
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr in CONTEXT_BINDERS:
        return True
    return func.attr in LOG_METHODS and "log" in ast.unparse(func.value).lower()


def log_email_offences(tree: ast.AST) -> list[tuple[int, str]]:
    """``(line, what)`` for every log call that hands an address to the logger."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _is_log_call(node)):
            continue
        for kw in node.keywords:
            if is_email_ident(kw.arg):
                found.append((node.lineno, f"kwarg {kw.arg}"))
        for sub in [*node.args, *(k.value for k in node.keywords)]:
            for inner in ast.walk(sub):
                if isinstance(inner, ast.Attribute) and is_email_ident(inner.attr):
                    found.append((node.lineno, f".{inner.attr}"))
                elif isinstance(inner, ast.Name) and is_email_ident(inner.id):
                    found.append((node.lineno, inner.id))
                elif (
                    isinstance(inner, ast.Subscript)
                    and isinstance(inner.slice, ast.Constant)
                    and isinstance(inner.slice.value, str)
                    and is_email_ident(inner.slice.value)
                ):
                    found.append((node.lineno, f"[{inner.slice.value!r}]"))
                elif (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "get"
                    and inner.args
                    and isinstance(inner.args[0], ast.Constant)
                    and isinstance(inner.args[0].value, str)
                    and is_email_ident(inner.args[0].value)
                ):
                    found.append((node.lineno, f".get({inner.args[0].value!r})"))
    return found


def test_floor2_no_log_call_in_app_passes_an_email():
    offences, calls = [], 0
    for path in sorted(APP_ROOT.rglob("*.py")):
        tree = parse(path)
        calls += sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call) and _is_log_call(n))
        offences += [f"{rel(path)}:{line} {what}" for line, what in log_email_offences(tree)]
    assert calls > 200, f"log-call sweep matched only {calls} calls; detector broken?"
    assert not offences, (
        "log calls that pass an email address (log user_id instead):\n" + "\n".join(offences)
    )


@pytest.mark.parametrize(
    "bad",
    [
        "logger.info('x', email=user.email)",
        "logger.info('x', who=user.email)",
        "logger.warning('x', user_email=u)",
        "log.error(f'sent to {owner.email}')",
        "logger.info('x %s', to_email)",
        "logger.info('x', to=addr)",
        "logger.info('x', data=payload['email'])",
        "logger.info('x', v=payload.get('email'))",
        "self._log.msg('x', recipient=r)",
        "logger.bind(email=e).info('x')",
        "structlog.contextvars.bind_contextvars(email=e)",
        "bind_contextvars(contact=user.email)",
        "logging.getLogger(__name__).log(20, 'x %s', invitee_email)",
    ],
)
def test_floor2_email_log_detector_is_red_on(bad):
    assert log_email_offences(ast.parse(bad)), bad


@pytest.mark.parametrize(
    "ok",
    [
        "logger.info('x', user_id=user.id, email_sent=True)",
        "logger.info('x', email_verified=user.email_verified)",
        "logger.info('email_dispatched', template=name)",
        "send_email(to=user.email)",
        "logger.info('x', count=len(emails_sent))",
    ],
)
def test_floor2_email_log_detector_accepts(ok):
    assert log_email_offences(ast.parse(ok)) == [], ok


# ── wiring ─────────────────────────────────────────────────────────────


@pytest.fixture
def configured_logging():
    """Run configure_logging with a fresh root handler, restore afterwards.

    Yields the root handlers as configure_logging left them: pytest adds its
    own capture handler for the call phase, after configuration, which is
    exactly the "handler added later" case the filter does not cover.
    """
    from app.core.logging import configure_logging

    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    saved_config = structlog.get_config()
    stream = io.StringIO()
    root.handlers = [logging.StreamHandler(stream)]
    try:
        configure_logging("INFO")
        yield list(root.handlers), stream
    finally:
        root.handlers = saved_handlers
        root.setLevel(saved_level)
        structlog.configure(**saved_config)


def test_floor2_redaction_runs_after_exc_formatting_and_right_before_the_renderer(
    configured_logging,
):
    from app.core.logging import redact_emails

    procs = structlog.get_config()["processors"]
    assert redact_emails in procs
    idx = procs.index(redact_emails)
    assert structlog.processors.format_exc_info in procs[:idx], procs
    assert idx == len(procs) - 2, f"only the renderer may follow redact_emails: {procs}"
    assert isinstance(
        procs[-1], structlog.processors.JSONRenderer | structlog.dev.ConsoleRenderer
    ), procs


def test_floor2_every_root_handler_has_the_email_filter(configured_logging):
    from app.core.logging import EmailRedactingFilter

    handlers, _stream = configured_logging
    assert handlers
    for handler in handlers:
        assert any(isinstance(f, EmailRedactingFilter) for f in handler.filters), handler


def test_floor2_structlog_line_reaches_the_handler_without_an_address(configured_logging):
    """Field, event, nested value, ``exc_info=True`` traceback and a stdlib record."""
    _handlers, stream = configured_logging
    log = structlog.get_logger("floor2-email")
    try:
        raise ValueError("provider rejected floor2-exc@example.com")
    except ValueError:
        log.warning(
            "notify floor2-event@example.com",
            who="floor2-field@example.com",
            nested={"k": ["floor2-nested@example.org"]},
            exc_info=True,
        )
    logging.getLogger("floor2-stdlib").warning("stdlib %s", "floor2-stdlib@example.net")
    out = stream.getvalue()
    assert "floor2-" in out and "ValueError" in out, "probe is vacuous: " + out
    assert "@example." not in out, out


def test_floor2_logger_exception_traceback_is_redacted(configured_logging):
    _handlers, stream = configured_logging
    try:
        raise ValueError("provider rejected floor2-exc2@example.com")
    except ValueError:
        structlog.get_logger("floor2-email").exception("send_failed")
    out = stream.getvalue()
    assert "send_failed" in out
    assert "@example." not in out, out


def test_floor2_worker_configures_redacting_logging():
    tree = parse(APP_ROOT / "worker.py")
    called = {
        ast.unparse(n.func).rsplit(".", 1)[-1] for n in ast.walk(tree) if isinstance(n, ast.Call)
    }
    assert "configure_logging" in called


def test_floor2_worker_setup_logging_signal_installs_the_filter(configured_logging):
    """Celery fires ``setup_logging`` in worker and beat; prefork children inherit it."""
    from celery.signals import setup_logging

    import app.worker  # noqa: F401  (connects the receiver)
    from app.core.logging import EmailRedactingFilter, redact_emails

    root = logging.getLogger()
    structlog.reset_defaults()
    root.handlers = [logging.StreamHandler(io.StringIO())]
    responses = setup_logging.send(
        sender=None, loglevel="INFO", logfile=None, format="", colorize=False
    )
    assert responses, "no receiver on celery setup_logging: Celery hijacks the root logger"
    assert redact_emails in structlog.get_config()["processors"]
    assert root.handlers
    for handler in root.handlers:
        assert any(isinstance(f, EmailRedactingFilter) for f in handler.filters), handler


# ── payloads ───────────────────────────────────────────────────────────


def test_floor2_profile_payload_hides_the_raw_consent_record(make_user):
    from app.api.auth_schemas import UserProfileResponse

    user = make_user(
        id="floor2-profile",
        ai_processing_consent_at=datetime(2026, 1, 2, tzinfo=UTC),
        ai_processing_consent_version=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    from unittest.mock import patch

    from app.config import settings

    # e2106eb: the profile's ai_consent_version is the instance's *required*
    # version, never the user's stored one.
    with patch.object(settings, "ai_consent_version", 7):
        dumped = UserProfileResponse.model_validate(user).model_dump(mode="json")
    assert dumped.get("ai_consent_version") == 7
    assert "ai_processing_consent_at" not in dumped
    assert "ai_processing_consent_version" not in dumped
    assert "2026-01-02" not in str(dumped)
    assert "ai_consent_required" in dumped
    schema = UserProfileResponse.model_json_schema(mode="serialization")["properties"]
    assert not {"ai_processing_consent_at", "ai_processing_consent_version"} & set(schema)


def test_floor2_usage_properties_cannot_carry_free_text():
    from app.services import usage_service

    assert not {"comment", "text", "email", "note", "content", "body"} & set(
        usage_service.ALLOWED_PROPERTY_KEYS
    )
    assert not usage_service._valid_properties({"target_type": "a comment with spaces"})
    assert not usage_service._valid_properties({"target_type": "x@example.com"})
    assert not usage_service._valid_properties({"comment": "x"})


def _mentions_comment(node: ast.AST) -> bool:
    for inner in ast.walk(node):
        if isinstance(inner, ast.Attribute) and inner.attr == "comment":
            return True
        if isinstance(inner, ast.Name) and inner.id == "comment":
            return True
        if isinstance(inner, ast.keyword) and inner.arg == "comment":
            return True
        if isinstance(inner, ast.Constant) and inner.value == "comment":
            return True
    return False


FEEDBACK_MODULES = ("app/api/ai_feedback.py", "app/services/ai_feedback_service.py")


def comment_leaks(tree: ast.AST) -> list[int]:
    """Lines where a log call or a usage record mentions the feedback comment."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        is_usage = ast.unparse(node.func).endswith("usage_service.record")
        if (is_usage or _is_log_call(node)) and _mentions_comment(node):
            out.append(node.lineno)
    return out


def test_floor2_feedback_comment_never_reaches_a_log_or_usage_event():
    leaks = []
    for module in FEEDBACK_MODULES:
        leaks += [f"{module}:{line}" for line in comment_leaks(parse(APP_ROOT.parent / module))]
    assert not leaks, f"AI feedback comment passed to a log or usage event: {leaks}"


def test_floor2_comment_leak_detector_is_red():
    bad = [
        "logger.info('x', comment=vote.comment)",
        "await usage_service.record(s, u.id, 'feedback_given', properties={'c': body.comment})",
        "logger.info(f'{comment}')",
    ]
    for src in bad:
        assert comment_leaks(ast.parse(src)), src
    assert comment_leaks(ast.parse("logger.info('x', rating=vote.rating)")) == []


@pytest.mark.asyncio
async def test_floor2_feedback_comment_absent_from_events_and_logs(async_client, make_user):
    """Behavioural: a vote with a comment produces a usage event and log lines without it."""
    from unittest.mock import AsyncMock, patch

    from structlog.testing import capture_logs

    from app.api.deps import get_current_user_or_default
    from app.main import app

    caller = make_user(id="floor2-feedback-caller")

    async def user_override():
        return caller

    app.dependency_overrides[get_current_user_or_default] = user_override
    secret = "floor2 secret remark floor2-c@example.com"
    with (
        patch(
            "app.services.ai_feedback_service.resolve_target_course", AsyncMock(return_value="c")
        ),
        patch("app.api.ai_feedback.usage_service.record", AsyncMock(return_value=True)) as record,
        capture_logs() as logs,
    ):
        resp = await async_client.put(
            "/api/feedback",
            json={
                "target_type": "summary",
                "target_id": "t",
                "rating": -1,
                "reason": "other",
                "comment": secret,
            },
        )
    assert resp.status_code == 200, resp.text
    assert record.await_count == 1
    assert "secret remark" not in repr(record.await_args)
    assert "secret remark" not in repr(logs), logs
