"""Integration test for `python -m app.cli ensure-admin` — the break-glass path.

This is the only supported way to obtain a first admin credential, and the only
route back in if the admin account is lost: `require_role("admin")` needs a real
JWT, and the default admin row ships with no password and an undeliverable
address, so neither the admin API nor a self-service reset can produce one. Its
failure mode is "this instance cannot be administered at all".

The unit tests drive `admin_service.ensure_admin` with a mocked session factory,
which can only check that the right calls were made. What actually has to hold is
that the *printed link works against a real database* — that the token hashes to
a live row, that redeeming it sets a password, and that an earlier run's link is
dead, which is what the command promises in its own output:

    Any link printed by an earlier run of this command is now void — use only
    the newest one.

So this runs the command the way an operator does: as a subprocess, over the real
Postgres, and then redeems what it printed.

Why a subprocess and not an in-process call: `cli._ensure_admin` calls
`engine.dispose()` in a `finally`, and that engine is the module-level one every
other test in this suite shares. It also wraps everything in `asyncio.run`, which
cannot be called from inside a running loop. The subprocess is both the honest
reproduction and the safe one.

Row cleanup is manual here. The `db_session` fixture's SAVEPOINT rollback cannot
reach rows a *different process* committed, so `default_admin_row` deletes what
it made (magic_links go with it, `ON DELETE CASCADE`).
"""

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import sqlalchemy
from sqlalchemy import select

from app.api.deps import DEFAULT_ADMIN_ID
from app.core.auth import hash_magic_link_token, verify_password
from app.core.exceptions import AuthenticationError
from app.models.magic_link import MagicLink
from app.models.user import User
from app.services import user_service

# tests/integration/test_cli_ensure_admin.py -> services/app
APP_DIR = Path(__file__).parents[2]

ADMIN_EMAIL = "break-glass@example.com"

# Not a credential: long enough to clear MIN_PASSWORD_LENGTH, and shaped so a
# secret scanner has nothing to match on.
NEW_PASSWORD = "<test-placeholder-password>"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run `python -m app.cli ...` the way an operator would, against this DB.

    The three service variables are already exported into this process by
    `scripts/test-integration.sh` (or CI), and the child inherits them — which
    is the same contract the conftest checks for the in-process app.
    """
    return subprocess.run(
        [sys.executable, "-m", "app.cli", *args],
        cwd=APP_DIR,
        env={**os.environ},
        capture_output=True,
        text=True,
    )


def _token_from(stdout: str) -> str:
    """Pull the raw token out of the `open:` line the command prints."""
    for line in stdout.splitlines():
        if "?token=" in line:
            query = parse_qs(urlparse(line.split()[-1]).query)
            return query["token"][0]
    raise AssertionError(f"no set-password link in output:\n{stdout}")


@pytest.fixture
def default_admin_row(_run_migrations, _require_env):
    """Seed the default admin row, and remove it afterwards.

    `ensure_admin` looks for `DEFAULT_ADMIN_ID` first and only falls back to
    "any admin" when it is absent — and the conftest seeds an admin of its own,
    which the fallback would otherwise pick up and repoint. Creating the row the
    command is designed around keeps the target deterministic and leaves the
    shared fixture user alone.
    """
    engine = sqlalchemy.create_engine(_require_env["DATABASE_URL_SYNC"])
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO users (id, email, username, role, tier, is_active, "
                "email_verified, mfa_enabled) VALUES (:id, :email, :username, "
                "'admin', 'pro', true, false, false) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": DEFAULT_ADMIN_ID, "email": "admin@studyaio.local", "username": "admin"},
        )
        conn.commit()

    yield DEFAULT_ADMIN_ID

    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("DELETE FROM users WHERE id = :id"), {"id": DEFAULT_ADMIN_ID})
        conn.commit()
    engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_prints_a_link_that_redeems_against_the_real_database(default_admin_row):
    """The whole point of the command: an operator can get back in with it.

    Every step is checked against the database rather than the mock: the token
    the command printed hashes to a live, unused row, and redeeming it puts a
    working password on the account.
    """
    from app.core.database import async_session_factory

    result = _run_cli("ensure-admin", "--email", ADMIN_EMAIL)
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    token = _token_from(result.stdout)

    async with async_session_factory() as session:
        link = (
            await session.execute(
                select(MagicLink).where(MagicLink.token_hash == hash_magic_link_token(token))
            )
        ).scalar_one()
        assert link.user_id == DEFAULT_ADMIN_ID
        assert link.link_type == "password_reset"
        assert link.used_at is None
        assert link.expires_at > datetime.now(UTC)

        # The account is repointed to the address the operator asked for, and
        # left unverified until someone follows a link to it.
        user = await session.get(User, DEFAULT_ADMIN_ID)
        assert user.email == ADMIN_EMAIL
        assert user.role == "admin"
        assert user.is_active is True
        assert user.hashed_password is None

        # Redeem it. This is the assertion the mocked unit tests cannot make:
        # the link is not merely well-formed, it works.
        await user_service.reset_password_with_token(session, token, NEW_PASSWORD)
        await session.commit()

    async with async_session_factory() as session:
        user = await session.get(User, DEFAULT_ADMIN_ID)
        assert user.hashed_password is not None
        assert verify_password(NEW_PASSWORD, user.hashed_password)


@pytest.mark.asyncio(loop_scope="session")
async def test_a_second_run_voids_the_first_link(default_admin_row):
    """The supersession the command claims in its own output.

    Re-running is the normal response to a link that was mislaid or leaked, so
    "the older one is now void" has to be true and not just printed. Both halves
    matter: the old token must be refused, and the new one must still work — a
    revocation that took the live token with it would lock the operator out
    exactly when they were trying to get in.
    """
    from app.core.database import async_session_factory

    first = _run_cli("ensure-admin", "--email", ADMIN_EMAIL)
    assert first.returncode == 0, first.stderr
    first_token = _token_from(first.stdout)

    second = _run_cli("ensure-admin", "--email", ADMIN_EMAIL)
    assert second.returncode == 0, second.stderr
    second_token = _token_from(second.stdout)

    assert first_token != second_token

    async with async_session_factory() as session:
        with pytest.raises(AuthenticationError, match="already used"):
            await user_service.reset_password_with_token(session, first_token, NEW_PASSWORD)

    async with async_session_factory() as session:
        await user_service.reset_password_with_token(session, second_token, NEW_PASSWORD)
        await session.commit()

    async with async_session_factory() as session:
        user = await session.get(User, DEFAULT_ADMIN_ID)
        assert verify_password(NEW_PASSWORD, user.hashed_password)
