"""Tests for structured logging configuration."""

from unittest.mock import patch

import structlog

from app.core.logging import _should_use_json, configure_logging


class TestLogRendererSelection:
    """Verify correct renderer is chosen based on config and environment."""

    def test_json_format_uses_json_renderer(self):
        """LOG_FORMAT=json should always use JSONRenderer."""
        with patch("app.core.logging.settings") as mock_settings:
            mock_settings.log_format = "json"
            assert _should_use_json() is True

    def test_console_format_uses_console_renderer(self):
        """LOG_FORMAT=console should always use ConsoleRenderer."""
        with patch("app.core.logging.settings") as mock_settings:
            mock_settings.log_format = "console"
            assert _should_use_json() is False

    def test_auto_format_json_when_not_tty(self):
        """LOG_FORMAT=auto should use JSON when not in a terminal."""
        with (
            patch("app.core.logging.settings") as mock_settings,
            patch("sys.stderr") as mock_stderr,
        ):
            mock_settings.log_format = "auto"
            mock_stderr.isatty.return_value = False
            assert _should_use_json() is True

    def test_auto_format_console_when_tty(self):
        """LOG_FORMAT=auto should use console when in a terminal."""
        with (
            patch("app.core.logging.settings") as mock_settings,
            patch("sys.stderr") as mock_stderr,
        ):
            mock_settings.log_format = "auto"
            mock_stderr.isatty.return_value = True
            assert _should_use_json() is False

    def test_configure_logging_runs_without_error(self):
        """configure_logging() should complete without raising."""
        with patch("app.core.logging.settings") as mock_settings:
            mock_settings.log_format = "console"
            configure_logging("INFO")

        # Verify structlog is configured by getting a logger
        log = structlog.get_logger()
        assert log is not None


class TestUrlLoggersCapped:
    """Libraries that log full request URLs at INFO are capped at WARNING (SEC-015 F1)."""

    def test_configure_logging_caps_url_logging_libraries(self):
        import logging

        names = (
            "httpx",
            "httpcore",
            "googleapiclient",
            "stripe",
            "requests_oauthlib",
            "oauthlib",
            "botocore",
            "boto3",
            "urllib3",
        )
        saved = {n: logging.getLogger(n).level for n in names}
        root = logging.getLogger()
        root_level = root.level
        try:
            root.setLevel(logging.DEBUG)
            for n in names:
                logging.getLogger(n).setLevel(logging.NOTSET)
            configure_logging("DEBUG")
            root.setLevel(logging.DEBUG)
            for n in names:
                assert logging.getLogger(n).getEffectiveLevel() >= logging.WARNING, n
        finally:
            root.setLevel(root_level)
            for n, level in saved.items():
                logging.getLogger(n).setLevel(level)
