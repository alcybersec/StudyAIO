"""The Celery worker/beat processes install the email-redacting log config (GL#38 F2)."""

import io
import logging

import pytest
import structlog
from celery.signals import setup_logging
from celery.utils.log import get_task_logger

from app import worker
from app.core.logging import EmailRedactingFilter, redact_emails


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.reset_defaults()


def test_worker_connects_setup_logging_receiver():
    receivers = [r() for _, r, *_ in setup_logging.receivers]
    assert worker.configure_worker_logging in receivers


def test_worker_logging_setup_installs_redaction(restore_logging):
    logging.getLogger().handlers.clear()
    worker.configure_worker_logging()

    assert redact_emails in structlog.get_config()["processors"]
    handlers = logging.getLogger().handlers
    assert handlers
    assert all(any(isinstance(f, EmailRedactingFilter) for f in h.filters) for h in handlers)


def test_task_log_with_address_is_redacted(restore_logging):
    logging.getLogger().handlers.clear()
    worker.configure_worker_logging()
    stream = io.StringIO()
    logging.getLogger().handlers[0].setStream(stream)

    get_task_logger("app.pipeline.notification_tasks").warning("delivery failed for bob@school.edu")
    structlog.get_logger("x").warning("send failed", to="bob@school.edu")

    out = stream.getvalue()
    assert "bob@school.edu" not in out
    assert out.count("[redacted-email]") == 2
