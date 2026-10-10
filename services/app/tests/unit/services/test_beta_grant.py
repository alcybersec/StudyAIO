"""PROD-08: grant Pro to beta users — idempotent, logged, operator-run."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import cli
from app.services import admin_service


def _user(email, tier="free", id=None):
    u = MagicMock()
    u.email = email
    u.tier = tier
    u.id = id or f"id-{email}"
    return u


def _session_returning(users):
    result = MagicMock()
    result.scalars.return_value.all.return_value = users
    session = AsyncMock()
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
class TestGrantBetaPro:
    async def test_free_users_become_pro_and_pro_are_left_alone(self):
        free, pro = _user("a@x.com"), _user("b@x.com", tier="pro")
        session = _session_returning([free, pro])

        out = await admin_service.grant_beta_pro(session, emails=["a@x.com", "b@x.com"])

        assert free.tier == "pro"
        assert out.granted == ["a@x.com"]
        assert out.already_pro == ["b@x.com"]

    async def test_second_run_changes_nothing(self):
        users = [_user("a@x.com")]
        session = _session_returning(users)
        await admin_service.grant_beta_pro(session, emails=["a@x.com"])
        out = await admin_service.grant_beta_pro(session, emails=["a@x.com"])
        assert out.granted == []
        assert out.already_pro == ["a@x.com"]

    async def test_unknown_emails_are_reported_not_created(self):
        session = _session_returning([_user("a@x.com")])
        out = await admin_service.grant_beta_pro(session, emails=["A@X.com", "ghost@x.com"])
        assert out.missing == ["ghost@x.com"]

    async def test_dry_run_changes_nothing(self):
        u = _user("a@x.com")
        out = await admin_service.grant_beta_pro(
            _session_returning([u]), emails=["a@x.com"], dry_run=True
        )
        assert u.tier == "free"
        assert out.granted == ["a@x.com"]

    async def test_requires_exactly_one_selector(self):
        with pytest.raises(ValueError):
            await admin_service.grant_beta_pro(_session_returning([]))
        with pytest.raises(ValueError):
            await admin_service.grant_beta_pro(
                _session_returning([]), emails=["a@x.com"], created_before=date(2026, 1, 1)
            )

    async def test_each_grant_is_logged(self):
        session = _session_returning([_user("a@x.com", id="u-1")])
        with patch.object(admin_service.logger, "info") as log:
            await admin_service.grant_beta_pro(session, emails=["a@x.com"])
        assert any(
            c.args[0] == "beta_pro_granted" and c.kwargs.get("user_id") == "u-1"
            for c in log.call_args_list
        )

    async def test_created_before_selects_by_date_filter(self):
        session = _session_returning([_user("a@x.com")])
        out = await admin_service.grant_beta_pro(session, created_before=date(2026, 10, 1))
        sql = str(session.execute.call_args[0][0])
        assert "users.created_at <" in sql
        assert out.granted == ["a@x.com"]


class TestGrantProCommand:
    @pytest.fixture
    def factory(self):
        session = AsyncMock()
        f = MagicMock()
        f.return_value.__aenter__ = AsyncMock(return_value=session)
        f.return_value.__aexit__ = AsyncMock(return_value=False)
        return f, session

    def test_emails_are_granted_and_committed(self, factory, capsys):
        f, session = factory
        res = admin_service.BetaGrantResult(granted=["a@x.com"], already_pro=[], missing=[])
        with (
            patch.object(cli, "async_session_factory", f),
            patch.object(cli.admin_service, "grant_beta_pro", AsyncMock(return_value=res)) as g,
        ):
            code = cli.main(["grant-pro", "--emails", "a@x.com,b@x.com"])
        assert code == 0
        assert g.await_args.kwargs["emails"] == ["a@x.com", "b@x.com"]
        session.commit.assert_awaited_once()
        assert "granted: 1" in capsys.readouterr().out

    def test_created_before_parses_a_date(self, factory):
        f, _ = factory
        res = admin_service.BetaGrantResult([], [], [])
        with (
            patch.object(cli, "async_session_factory", f),
            patch.object(cli.admin_service, "grant_beta_pro", AsyncMock(return_value=res)) as g,
        ):
            cli.main(["grant-pro", "--created-before", "2026-10-11"])
        assert g.await_args.kwargs["created_before"] == date(2026, 10, 11)

    def test_dry_run_does_not_commit(self, factory):
        f, session = factory
        res = admin_service.BetaGrantResult(["a@x.com"], [], [])
        with (
            patch.object(cli, "async_session_factory", f),
            patch.object(cli.admin_service, "grant_beta_pro", AsyncMock(return_value=res)),
        ):
            cli.main(["grant-pro", "--emails", "a@x.com", "--dry-run"])
        session.commit.assert_not_awaited()

    def test_a_selector_is_required(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["grant-pro"])
