"""Tests for the operator CLI."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import cli
from app.core.exceptions import UserExistsError


def _user(email="me@example.com", id="u-1", role="admin"):
    user = MagicMock()
    user.id = id
    user.email = email
    user.role = role
    return user


@pytest.fixture
def fake_session_factory():
    """Replace async_session_factory with a no-op async context manager."""
    session = AsyncMock()
    session.commit = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


class TestEnsureAdminCommand:
    """Tests for `ensure-admin`."""

    def test_prints_the_setup_url_and_exits_zero(self, fake_session_factory, capsys):
        """The link is the whole point — it must reach stdout."""
        factory, session = fake_session_factory
        with (
            patch.object(cli, "async_session_factory", factory),
            patch.object(
                cli.admin_service,
                "ensure_admin",
                AsyncMock(return_value=(_user(), "tok-123")),
            ),
            patch.object(cli.settings, "app_base_url", "https://studyaio.example.com"),
        ):
            code = cli.main(["ensure-admin", "--email", "me@example.com"])

        out = capsys.readouterr().out
        assert code == 0
        assert "https://studyaio.example.com/reset-password?token=tok-123" in out
        session.commit.assert_awaited_once()

    def test_url_encodes_the_token(self, fake_session_factory, capsys):
        """An unescaped token would truncate the query string."""
        factory, _ = fake_session_factory
        with (
            patch.object(cli, "async_session_factory", factory),
            patch.object(
                cli.admin_service,
                "ensure_admin",
                AsyncMock(return_value=(_user(), "a+b/c=")),
            ),
            patch.object(cli.settings, "app_base_url", "https://x.example.com"),
        ):
            cli.main(["ensure-admin", "--email", "me@example.com"])

        assert "token=a%2Bb%2Fc%3D" in capsys.readouterr().out

    def test_taken_email_exits_nonzero_without_a_link(self, fake_session_factory, capsys):
        """A failed run must not look like a successful one."""
        factory, session = fake_session_factory
        with (
            patch.object(cli, "async_session_factory", factory),
            patch.object(
                cli.admin_service,
                "ensure_admin",
                AsyncMock(side_effect=UserExistsError("email")),
            ),
        ):
            code = cli.main(["ensure-admin", "--email", "taken@example.com"])

        captured = capsys.readouterr()
        assert code == 1
        assert "reset-password" not in captured.out
        assert "already exists" in captured.err
        session.commit.assert_not_awaited()

    def test_passes_username_through(self, fake_session_factory):
        """--username only matters on a fresh database, but must not be dropped."""
        factory, _ = fake_session_factory
        ensure = AsyncMock(return_value=(_user(), "tok"))
        with (
            patch.object(cli, "async_session_factory", factory),
            patch.object(cli.admin_service, "ensure_admin", ensure),
            patch.object(cli.settings, "app_base_url", "https://x.example.com"),
        ):
            cli.main(["ensure-admin", "--email", "me@example.com", "--username", "alex"])

        assert ensure.await_args.args[1:] == ("me@example.com", "alex")

    def test_no_subcommand_exits_nonzero(self, capsys):
        """Bare `python -m app.cli` should explain itself, not traceback."""
        assert cli.main([]) == 2
        assert "ensure-admin" in capsys.readouterr().err
