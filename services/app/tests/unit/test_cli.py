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

    def test_warns_that_earlier_links_are_now_void(self, fake_session_factory, capsys):
        """A second run (e.g. fixing a typo'd --email) must not read as a hijack."""
        factory, _ = fake_session_factory
        with (
            patch.object(cli, "async_session_factory", factory),
            patch.object(
                cli.admin_service,
                "ensure_admin",
                AsyncMock(return_value=(_user(), "tok-123")),
            ),
            patch.object(cli.settings, "app_base_url", "https://studyaio.example.com"),
        ):
            cli.main(["ensure-admin", "--email", "me@example.com"])

        out = capsys.readouterr().out
        assert "Any link printed by an earlier run of this command is now void" in out

    def test_no_subcommand_exits_nonzero(self, capsys):
        """Bare `python -m app.cli` should explain itself, not traceback."""
        assert cli.main([]) == 2
        assert "ensure-admin" in capsys.readouterr().err


def _concept(name: str):
    concept = MagicMock()
    concept.name = name
    concept.description = f"description of {name}"
    concept.embedding = None
    return concept


class TestBackfillConceptEmbeddingsCommand:
    """Concepts created before issue #33 was fixed have NULL embeddings."""

    def _run(self, session, factory, batches, embed_side_effect=None):
        """Drive the command with a scripted sequence of unembedded batches."""
        session.scalar = AsyncMock(return_value=sum(len(b) for b in batches))
        results = []
        for batch in [*batches, []]:
            result = MagicMock()
            result.scalars.return_value.all.return_value = batch
            results.append(result)
        session.execute = AsyncMock(side_effect=results)
        session.rollback = AsyncMock()

        def _embed(concepts):
            for c in concepts:
                c.embedding = [0.1] * 384

        with patch.object(cli, "async_session_factory", factory):
            with patch(
                "app.services.concept_service._embed_concepts",
                side_effect=embed_side_effect or _embed,
            ) as embed:
                code = cli.main(["backfill-concept-embeddings", "--batch-size", "2"])
        return code, embed

    def test_embeds_every_batch_and_commits(self, fake_session_factory, capsys):
        factory, session = fake_session_factory
        code, embed = self._run(session, factory, [[_concept("a"), _concept("b")], [_concept("c")]])

        assert code == 0
        assert embed.call_count == 2
        assert session.commit.await_count == 2
        assert "3 concept(s) embedded" in capsys.readouterr().out

    def test_nothing_to_do_is_not_an_error(self, fake_session_factory, capsys):
        factory, session = fake_session_factory
        session.scalar = AsyncMock(return_value=0)

        with patch.object(cli, "async_session_factory", factory):
            code = cli.main(["backfill-concept-embeddings"])

        assert code == 0
        assert "nothing to do" in capsys.readouterr().out

    def test_a_provider_returning_nothing_stops_instead_of_looping(
        self, fake_session_factory, capsys
    ):
        """The query selects `embedding IS NULL`, so unembedded rows come back forever.

        Without this guard the command spins on the same batch indefinitely
        while reporting progress.
        """
        factory, session = fake_session_factory
        code, _ = self._run(
            session,
            factory,
            [[_concept("a")]],
            embed_side_effect=lambda concepts: None,
        )

        assert code == 1
        assert session.rollback.await_count == 1
        assert "returned nothing" in capsys.readouterr().err

    def test_it_is_listed_when_no_subcommand_is_given(self, capsys):
        assert cli.main([]) == 2
        assert "backfill-concept-embeddings" in capsys.readouterr().err
