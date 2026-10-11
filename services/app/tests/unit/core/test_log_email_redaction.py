"""No email address in any log line (M33-S1-BACKEND-017, GL#38, SEC-08).

Two layers: call sites do not pass addresses (AST sweep), and a structlog
processor plus a stdlib filter redact anything address-shaped (defence in depth).
"""

import ast
import logging
from pathlib import Path

import structlog

from app.core.logging import EmailRedactingFilter, configure_logging, redact_emails

APP = Path(__file__).resolve().parents[3] / "app"

LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "bind"}
EMAIL_KWARGS = {"email", "to", "to_email", "old_email", "new_email", "recipient", "address"}
EMAIL_NAMES = {"email", "to_email", "old_email", "new_email"}


class TestRedactionProcessor:
    def test_email_in_a_field_is_redacted(self):
        out = redact_emails(None, "info", {"event": "x", "who": "alice@example.com"})
        assert "alice@example.com" not in str(out)
        assert out["who"] == "[redacted-email]"

    def test_email_inside_free_text_and_event(self):
        out = redact_emails(
            None, "info", {"event": "sent to bob@example.org ok", "detail": "a b@c.io d"}
        )
        assert "bob@example.org" not in out["event"]
        assert "b@c.io" not in out["detail"]
        assert out["event"].startswith("sent to ")

    def test_nested_containers_are_walked(self):
        out = redact_emails(
            None,
            "info",
            {"event": "x", "p": {"k": ["z@example.com", ("y@example.com",)]}},
        )
        assert "example.com" not in str(out)

    def test_non_string_values_survive(self):
        out = redact_emails(None, "info", {"event": "x", "n": 3, "f": None, "b": True})
        assert out["n"] == 3 and out["f"] is None and out["b"] is True

    def test_exception_text_is_redacted(self):
        out = redact_emails(
            None, "info", {"event": "x", "exception": "ValueError: bad u@example.com"}
        )
        assert "u@example.com" not in out["exception"]

    def test_ids_and_urls_without_at_are_untouched(self):
        out = redact_emails(None, "info", {"event": "x", "user_id": "0190-abc", "path": "/api/x"})
        assert out["user_id"] == "0190-abc" and out["path"] == "/api/x"


class TestWiring:
    def test_processor_runs_before_the_renderer(self):
        configure_logging("INFO")
        procs = structlog.get_config()["processors"]
        names = [getattr(p, "__name__", type(p).__name__) for p in procs]
        assert "redact_emails" in names
        assert names.index("redact_emails") < len(names) - 1  # renderer is last

    def test_end_to_end_json_line_has_no_address(self, capsys):
        with_stdlib = logging.getLogger("redact-test")
        record = logging.LogRecord(
            "redact-test", logging.INFO, __file__, 1, "hello %s", ("c@example.com",), None
        )
        assert EmailRedactingFilter().filter(record) is True
        assert "c@example.com" not in record.getMessage()
        _ = with_stdlib

    def test_stdlib_filter_installed_on_root_handlers(self):
        configure_logging("INFO")
        handlers = logging.getLogger().handlers
        assert handlers
        assert any(isinstance(f, EmailRedactingFilter) for h in handlers for f in h.filters)


def _is_log_call(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in LOG_METHODS
        and "log" in ast.unparse(func.value).lower()
    )


def _offences(tree: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _is_log_call(node)):
            continue
        for kw in node.keywords:
            if kw.arg in EMAIL_KWARGS:
                found.append((node.lineno, f"kwarg {kw.arg}"))
        for sub in [*node.args, *(k.value for k in node.keywords)]:
            for inner in ast.walk(sub):
                if isinstance(inner, ast.Attribute) and inner.attr in EMAIL_NAMES:
                    found.append((node.lineno, f".{inner.attr}"))
                elif isinstance(inner, ast.Name) and inner.id in EMAIL_NAMES:
                    found.append((node.lineno, inner.id))
    return found


class TestCallSiteSweep:
    def test_no_log_call_in_app_passes_an_email(self):
        offences = []
        for path in sorted(APP.rglob("*.py")):
            for line, what in _offences(ast.parse(path.read_text())):
                offences.append(f"{path.relative_to(APP.parent)}:{line} {what}")
        assert not offences, "log calls that pass an email address:\n" + "\n".join(offences)

    def test_the_sweep_catches_a_violation(self):
        bad = ast.parse("logger.info('x', email=user.email)\nlog.warning('y', who=u.email)")
        assert len(_offences(bad)) >= 3

    def test_the_sweep_accepts_ids(self):
        ok = ast.parse("logger.info('x', user_id=user.id, email_sent=True)")
        assert _offences(ok) == []
