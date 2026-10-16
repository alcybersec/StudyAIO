"""Bound parameters never reach an exception message or a log line (floor 2).

A flush that fails in the OAuth callback is logged with ``logger.exception``;
SQLAlchemy's DBAPI error text then carries ``[parameters: ...]`` with every bound
value (OAuth tokens, emails, credential ciphertext). Two layers: every engine is
built with ``hide_parameters=True``, and the log redaction strips the section if
one still arrives.
"""

import ast
import json
import logging
import sys
from pathlib import Path

import pytest
import structlog
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.exc import IntegrityError

from app.core.database import engine
from app.core.logging import EmailRedactingFilter, configure_logging, redact_emails

APP = Path(__file__).resolve().parents[3] / "app"
SENTINEL = "sentinel-oauth-token-9f3a"
FACTORIES = {"create_engine", "create_async_engine"}


def _factory_calls():
    for path in APP.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if name in FACTORIES:
                    yield path, node


class TestEveryEngineHidesParameters:
    def test_at_least_one_factory_call_is_found(self):
        assert list(_factory_calls())

    def test_every_factory_call_passes_hide_parameters_true(self):
        for path, node in _factory_calls():
            kw = {k.arg: k.value for k in node.keywords}
            assert "hide_parameters" in kw, f"{path.name}:{node.lineno} lacks hide_parameters"
            assert isinstance(kw["hide_parameters"], ast.Constant)
            assert kw["hide_parameters"].value is True, f"{path.name}:{node.lineno}"

    def test_the_live_engine_has_it_set(self):
        assert engine.sync_engine.hide_parameters is True


def _forced_unique_violation() -> IntegrityError:
    eng = create_engine("sqlite://", hide_parameters=engine.sync_engine.hide_parameters)
    t = Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("tok", String))
    t.metadata.create_all(eng)
    with pytest.raises(IntegrityError) as info, eng.begin() as conn:
        conn.execute(t.insert().values(id=1, tok=SENTINEL))
        conn.execute(t.insert().values(id=1, tok=SENTINEL))
    return info.value


class TestRenderedErrorHasNoBoundValue:
    def test_exception_message_omits_the_bound_value(self):
        exc = _forced_unique_violation()
        assert SENTINEL not in str(exc)
        assert "[parameters:" not in str(exc)

    def test_logged_exception_omits_the_bound_value(self, capsys):
        configure_logging("INFO")
        try:
            raise _forced_unique_violation()
        except IntegrityError:
            structlog.get_logger("t").exception("oauth_callback_failed")
        out = capsys.readouterr()
        assert SENTINEL not in out.out + out.err


RENDERED = (
    "(sqlite3.IntegrityError) UNIQUE constraint failed\n"
    "[SQL: INSERT INTO t (id, tok) VALUES (?, ?)]\n"
    f"[parameters: (1, '{SENTINEL}')]\n"
    "(Background on this error at: https://sqlalche.me/e/20/gkpj)"
)


class TestParametersSectionIsStripped:
    def test_processor_strips_section_and_keeps_the_rest(self):
        out = redact_emails(None, "error", {"event": "x", "exception": RENDERED})
        assert SENTINEL not in out["exception"]
        assert "[SQL: INSERT" in out["exception"]
        assert "Background on this error" in out["exception"]

    def test_section_containing_brackets_is_stripped(self):
        text = f"[parameters: ({{'a': ['{SENTINEL}']}},)]\n(Background on this error at: x)"
        out = redact_emails(None, "error", {"event": text})
        assert SENTINEL not in out["event"]

    def test_section_at_end_of_text_is_stripped(self):
        out = redact_emails(None, "error", {"event": f"boom\n[parameters: ('{SENTINEL}',)]"})
        assert SENTINEL not in out["event"]

    def test_stdlib_filter_strips_message_and_traceback(self):
        rec = logging.LogRecord("n", logging.ERROR, "f", 1, RENDERED, None, None)
        EmailRedactingFilter().filter(rec)
        assert SENTINEL not in rec.getMessage()
        try:
            raise ValueError(RENDERED)
        except ValueError:
            rec = logging.LogRecord("n", logging.ERROR, "f", 1, "m", None, sys.exc_info())
        EmailRedactingFilter().filter(rec)
        assert SENTINEL not in rec.exc_text

    def test_text_without_the_section_is_unchanged(self):
        assert redact_emails(None, "i", {"event": "plain [x: y]"})["event"] == "plain [x: y]"

    def test_result_is_json_serialisable(self):
        json.dumps(redact_emails(None, "i", {"event": RENDERED}))
