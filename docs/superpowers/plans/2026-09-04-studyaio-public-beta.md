# StudyAIO Public Beta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take StudyAIO from its LAN-only Authelia-gated URL to a closed invite-only public beta at `https://studyaio.aleksanlab.me`, running on Z.ai/GLM with a bounded bill.

**Architecture:** The app stays on homelab VM 210 and is exposed through the existing Cloudflare → VPS Caddy (Helsinki) → Tailscale → PVE Caddy chain, the same path Jellyfin and Immich already use. PR #20–#22 already shipped the quota, metering and invite machinery, so the code work here is narrow: a management command that can produce the first admin credential (today none can be obtained at all), an `email` field on the admin update path, and two preflight checks. Everything else is configuration and edge work.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Celery, pytest + AsyncMock, bash, Caddy, Docker Compose, Infisical, Cloudflare.

**Spec:** `docs/superpowers/specs/2026-09-03-studyaio-public-beta-design.md`

## Before you write any Python: the format gate

`.github/workflows/ci.yml` runs **two** separate ruff steps in `services/app`, and
`backend-tests` has `needs: python-lint`, so either one failing blocks the whole
build before a single test runs:

```
ruff check .
ruff format --check .
```

`ruff check` passing does not imply `ruff format --check` passing. The code blocks
in this plan are wrapped at 88 columns; this project sets `line-length = 100`
(`services/app/pyproject.toml:3`). So **pasting a block from this plan verbatim
will fail the format gate.** After every Python change:

```bash
cd services/app
RUFF_CACHE_DIR="$CLAUDE_JOB_DIR/tmp/ruff" ruff format .
RUFF_CACHE_DIR="$CLAUDE_JOB_DIR/tmp/ruff" ruff format --check .
```

The `RUFF_CACHE_DIR` override is required — the repo's checked-in `.ruff_cache` is
not writable in the agent sandbox and ruff aborts with a permission error that
looks like a ruff bug rather than a cache problem.

If `ruff format` wants to reformat a file your task did not touch, stop: that is a
pre-existing violation and reformatting it would bury your change in noise.

---

## Phase boundaries

**Phase 1 (Tasks 1–7)** is code and docs in this repo, under CI, shipped as one PR.

**Phase 2 (Tasks 8–15)** is configuration and infrastructure across three trees. It is ordered, and the order matters: Task 8 produces the credential Tasks 14–15 need, and Task 13 must not run before Task 12 or the public hostname will not resolve. Phase 2 has no automated tests — each task carries the exact command and the exact expected output that constitutes its verification.

Do not start Phase 2 until Phase 1 is merged and deployed, because Task 8 runs the command Task 2 creates.

## File structure

**Phase 1 — created:**

| File | Responsibility |
|---|---|
| `services/app/app/cli.py` | Argument parsing and process exit codes for operator commands. No business logic. |
| `services/app/tests/unit/services/test_ensure_admin.py` | Unit tests for `admin_service.ensure_admin` |
| `services/app/tests/unit/test_cli.py` | Unit tests for the CLI entrypoint |
| `services/app/tests/unit/test_preflight_script.py` | Runs `scripts/preflight-check.sh` as a subprocess against generated `.env` fixtures |

**Phase 1 — modified:**

| File | Change |
|---|---|
| `services/app/app/services/admin_service.py` | Add `ensure_admin()`; add `email` to `update_user()` |
| `services/app/app/api/admin.py` | Add `email` to `UserUpdateRequest` |
| `scripts/preflight-check.sh` | Add AI-provider credential check and global-ceiling warning |
| `Makefile` | Add `ensure-admin` target |
| `docs/deployment.md` | New step 0; correct steps 4 and 5 |
| `.env.example` | Cloudflare body-size note on `MAX_UPLOAD_SIZE_MB` |

The CLI is deliberately thin — parsing and exit codes only — so that `ensure_admin` is testable without a subprocess, matching how every other behaviour in this codebase is tested.

---

## Task 1: `ensure_admin` service function

The instance can end up with no reachable admin: `_get_or_create_default_user` (`app/api/deps.py:108-116`) creates the default row with `hashed_password=None` and the unroutable `admin@studyaio.local`, and `require_role("admin")` depends on `get_current_user` (`app/api/deps.py:169`), not the self-hosted fallback. This function is the supported way out.

**Files:**
- Modify: `services/app/app/services/admin_service.py`
- Test: `services/app/tests/unit/services/test_ensure_admin.py`

- [ ] **Step 1: Write the failing tests**

Create `services/app/tests/unit/services/test_ensure_admin.py`:

```python
"""Tests for admin_service.ensure_admin — the first-admin bootstrap."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import DEFAULT_ADMIN_ID
from app.core.exceptions import UserExistsError
from app.services import admin_service


@pytest.fixture
def mock_session():
    """AsyncMock of AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _make_user_model(
    id=DEFAULT_ADMIN_ID,
    email="admin@studyaio.local",
    username="admin",
    role="admin",
    tier="pro",
    is_active=True,
):
    """Create a mock User model object."""
    user = MagicMock()
    user.id = id
    user.email = email
    user.username = username
    user.role = role
    user.tier = tier
    user.is_active = is_active
    user.email_verified = True
    user.created_at = datetime(2026, 1, 1, 10, 0, 0)
    user.updated_at = datetime(2026, 1, 1, 10, 0, 0)
    return user


def _minted(token="raw-token-abc"):
    """Stand in for user_service.MintedMagicLink."""
    link = MagicMock()
    link.raw_token = token
    return link


def _no_clash(session):
    """Make every `session.execute(select(...))` return no row."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result)


@pytest.mark.asyncio
class TestEnsureAdmin:
    """Tests for ensure_admin()."""

    async def test_repoints_the_default_admin_row(self, mock_session):
        """The default admin keeps its id, so the data it owns keeps its owner."""
        existing = _make_user_model()
        mock_session.get = AsyncMock(return_value=existing)
        _no_clash(mock_session)

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            user, token = await admin_service.ensure_admin(mock_session, "me@example.com")

        assert user.id == DEFAULT_ADMIN_ID
        assert user.email == "me@example.com"
        assert user.role == "admin"
        assert user.is_active is True
        assert token == "raw-token-abc"

    async def test_changing_the_email_clears_verification(self, mock_session):
        """A new address is unproven until its owner follows a link."""
        existing = _make_user_model()
        mock_session.get = AsyncMock(return_value=existing)
        _no_clash(mock_session)

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            await admin_service.ensure_admin(mock_session, "me@example.com")

        assert existing.email_verified is False

    async def test_unchanged_email_keeps_verification(self, mock_session):
        """Re-running with the same address must not un-verify it."""
        existing = _make_user_model(email="me@example.com")
        mock_session.get = AsyncMock(return_value=existing)
        _no_clash(mock_session)

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            await admin_service.ensure_admin(mock_session, "me@example.com")

        assert existing.email_verified is True

    async def test_rejects_an_email_owned_by_someone_else(self, mock_session):
        """Repointing onto a tester's address would hand over their account."""
        existing = _make_user_model()
        mock_session.get = AsyncMock(return_value=existing)
        other = _make_user_model(id="u-2", email="taken@example.com", role="user")
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=other)
        mock_session.execute = AsyncMock(return_value=result)

        with pytest.raises(UserExistsError):
            await admin_service.ensure_admin(mock_session, "taken@example.com")

    async def test_falls_back_to_any_existing_admin(self, mock_session):
        """A renamed or re-seeded instance may have an admin under another id."""
        mock_session.get = AsyncMock(return_value=None)
        found = _make_user_model(id="u-9", email="old@example.com")
        found_result = MagicMock()
        found_result.scalar_one_or_none = MagicMock(return_value=found)
        empty_result = MagicMock()
        empty_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(side_effect=[found_result, empty_result])

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            user, _ = await admin_service.ensure_admin(mock_session, "me@example.com")

        assert user.id == "u-9"

    async def test_creates_an_admin_when_none_exists(self, mock_session):
        """A fresh database has no admin row at all."""
        mock_session.get = AsyncMock(return_value=None)
        _no_clash(mock_session)
        created = _make_user_model(id="u-new", email="me@example.com")

        with patch.object(
            admin_service,
            "create_user",
            AsyncMock(return_value=(created, "fresh-token")),
        ) as create:
            user, token = await admin_service.ensure_admin(
                mock_session, "me@example.com", "alex"
            )

        create.assert_awaited_once_with(
            mock_session, "me@example.com", "alex", role="admin", tier="pro"
        )
        assert user.id == "u-new"
        assert token == "fresh-token"

    async def test_reactivates_a_deactivated_admin(self, mock_session):
        """A deactivated sole admin is exactly the lockout this recovers from."""
        existing = _make_user_model(is_active=False, role="user")
        mock_session.get = AsyncMock(return_value=existing)
        _no_clash(mock_session)

        with patch.object(
            admin_service.user_service,
            "request_password_reset",
            AsyncMock(return_value=_minted()),
        ):
            await admin_service.ensure_admin(mock_session, "admin@studyaio.local")

        assert existing.is_active is True
        assert existing.role == "admin"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/app && python -m pytest tests/unit/services/test_ensure_admin.py -v`

Expected: 7 errors, `AttributeError: module 'app.services.admin_service' has no attribute 'ensure_admin'`.

- [ ] **Step 3: Write the implementation**

Add to `services/app/app/services/admin_service.py`, immediately after `create_user` (which ends at line 599 with `return user, minted.raw_token`):

```python
async def ensure_admin(
    session: AsyncSession,
    email: str,
    username: str | None = None,
) -> tuple[User, str]:
    """Guarantee one reachable admin account and mint its set-password link.

    Targets the self-hosted default admin row when it exists, so every course
    and artifact it already owns keeps its owner and no data migration is
    needed. Falls back to any other admin, and creates one only when the
    instance has none.

    This is the only path to a first admin credential: `require_role("admin")`
    needs a real JWT, and the default row is created with no password and an
    undeliverable address, so neither the admin API nor a self-service reset
    can produce one.

    Args:
        session: Database session.
        email: Address the admin should be reachable at.
        username: Display name, used only when creating a new account.

    Returns:
        (user, raw_setup_token)

    Raises:
        UserExistsError: If `email` already belongs to a different account.
    """
    from app.api.deps import DEFAULT_ADMIN_ID

    user = await session.get(User, DEFAULT_ADMIN_ID)
    if user is None:
        result = await session.execute(
            select(User).where(User.role == "admin").order_by(User.created_at).limit(1)
        )
        user = result.scalar_one_or_none()

    if user is None:
        return await create_user(
            session, email, username or "admin", role="admin", tier="pro"
        )

    if user.email != email:
        clash = await session.execute(
            select(User).where(User.email == email, User.id != user.id)
        )
        if clash.scalar_one_or_none():
            raise UserExistsError("email")
        user.email = email
        # A new address is unproven until its owner follows a link.
        user.email_verified = False

    # Demotion or deactivation is one of the lockouts this recovers from.
    user.role = "admin"
    user.is_active = True
    user.updated_at = datetime.now(UTC)
    await session.flush()

    minted = await user_service.request_password_reset(
        session, user.email, expires_in_hours=user_service.ACCOUNT_SETUP_TOKEN_HOURS
    )
    if minted is None:  # pragma: no cover - the row was just flushed
        raise RuntimeError("Could not mint a setup link for the admin account")

    logger.info("ensure_admin", user_id=user.id, created=False)
    return user, minted.raw_token
```

`DEFAULT_ADMIN_ID` is imported inside the function to keep the service layer from taking a module-level dependency on `app.api`, which is the layer above it. Note this is a layering choice, not a necessity: `app/api/deps.py` imports only `user_service`, so hoisting the import would *not* actually cycle — verified empirically. Do not repeat a circularity claim about it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd services/app && python -m pytest tests/unit/services/test_ensure_admin.py -v`

Expected: 7 passed.

- [ ] **Step 5: Run the full admin service suite for regressions**

Run: `cd services/app && python -m pytest tests/unit/services/test_admin_service.py tests/unit/services/test_admin_user_lifecycle.py -q`

Expected: all pass, no failures.

- [ ] **Step 6: Commit**

```bash
git add services/app/app/services/admin_service.py services/app/tests/unit/services/test_ensure_admin.py
git commit -m "feat(admin): ensure_admin bootstraps a reachable admin account"
```

---

## Task 2: CLI entrypoint

**Files:**
- Create: `services/app/app/cli.py`
- Test: `services/app/tests/unit/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `services/app/tests/unit/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/app && python -m pytest tests/unit/test_cli.py -v`

Expected: collection error, `ModuleNotFoundError: No module named 'app.cli'`.

- [ ] **Step 3: Write the implementation**

Create `services/app/app/cli.py`:

```python
"""Operator commands for StudyAIO.

Run inside the API container:

    docker compose exec api python -m app.cli ensure-admin --email you@example.com

`ensure-admin` is the only supported way to obtain a first admin credential.
The set-password link it prints is a bearer credential for the account, so it
goes to stdout and is never written to the structured log — the same rule
`user_service` applies to reset links in SaaS mode.
"""

import argparse
import asyncio
import sys
from urllib.parse import quote_plus

from app.config import settings
from app.core.database import async_session_factory
from app.core.exceptions import StudyAIOError
from app.services import admin_service


async def _ensure_admin(email: str, username: str | None) -> int:
    """Bootstrap an admin account and print its set-password link."""
    async with async_session_factory() as session:
        try:
            user, token = await admin_service.ensure_admin(session, email, username)
        except (StudyAIOError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        await session.commit()

    base = settings.app_base_url.rstrip("/")
    print(f"admin:  {user.email}  (id {user.id}, role {user.role})")
    print(f"open:   {base}/reset-password?token={quote_plus(token)}")
    print("")
    print("The link is single-use and expires in 24 hours. It is a credential —")
    print("do not paste it into a shared channel or an issue tracker.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command")

    ensure = sub.add_parser(
        "ensure-admin",
        help="Guarantee a reachable admin account and print its set-password link",
    )
    ensure.add_argument("--email", required=True, help="Address the admin logs in with")
    ensure.add_argument(
        "--username",
        default=None,
        help="Display name, used only when no admin account exists yet",
    )

    args = parser.parse_args(argv)

    if args.command == "ensure-admin":
        return asyncio.run(_ensure_admin(args.email, args.username))

    parser.print_usage(sys.stderr)
    print("error: a command is required (ensure-admin)", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd services/app && python -m pytest tests/unit/test_cli.py -v`

Expected: 5 passed.

- [ ] **Step 5: Add the Makefile target**

In `Makefile`, add `ensure-admin` to the `.PHONY` list on line 1, and add this block after the `preflight` target (lines 39-40):

```makefile
ensure-admin:
	@if [ -z "$(email)" ]; then echo "Usage: make ensure-admin email=you@example.com"; exit 1; fi
	docker compose exec api python -m app.cli ensure-admin --email $(email)
```

- [ ] **Step 6: Verify the command runs for real against the dev stack**

Run:
```bash
docker compose up -d
make migrate
make ensure-admin email=dev@example.com
```

Expected: two lines of output, the second containing `/reset-password?token=`. A traceback here means the async session or import wiring is wrong in a way the mocked unit tests cannot catch.

- [ ] **Step 7: Commit**

```bash
git add services/app/app/cli.py services/app/tests/unit/test_cli.py Makefile
git commit -m "feat(cli): add ensure-admin operator command"
```

---

## Task 3: Allow an admin to change a user's email

`UserUpdateRequest` (`app/api/admin.py:49-54`) carries `role`, `tier` and `is_active` only, so `admin@studyaio.local` cannot be repointed through the API. Task 1 fixes it once from the CLI; this closes it permanently **in the API**.

Note the limit, which this task does not remove: the admin UI still cannot send the field, because `services/ui/src/types/index.ts`'s `AdminUserUpdate` has no `email` and the form sends single-field patches. So after this task an operator corrects an address via the CLI, `curl`, or `/docs` — not by clicking. Wiring the UI is separate work (TS types, the form, vitest coverage), deliberately out of Phase 1; the beta is unblocked by the CLI and the API alone.

**Files:**
- Modify: `services/app/app/services/admin_service.py:87-127`
- Modify: `services/app/app/api/admin.py:49-54`
- Test: `services/app/tests/unit/services/test_admin_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `services/app/tests/unit/services/test_admin_service.py`:

```python
@pytest.mark.asyncio
class TestUpdateUserEmail:
    """Tests for update_user(email=...)."""

    async def test_changes_the_email(self, mock_session):
        """An operator must be able to fix an unroutable address."""
        # `_make_user_model` defaults email_verified to False, so it must be set
        # explicitly here or the assertion below passes without the code running.
        user = _make_user_model(email="admin@studyaio.local", email_verified=True)
        mock_session.get = AsyncMock(return_value=user)
        empty = MagicMock()
        empty.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=empty)

        result = await admin_service.update_user(
            mock_session, "user-001", email="real@example.com"
        )

        assert result["email"] == "real@example.com"
        assert user.email_verified is False

    async def test_rejects_an_email_already_in_use(self, mock_session):
        """Two accounts sharing an address would make login ambiguous."""
        user = _make_user_model()
        mock_session.get = AsyncMock(return_value=user)
        taken = MagicMock()
        taken.scalar_one_or_none = MagicMock(return_value=_make_user_model(id="u-2"))
        mock_session.execute = AsyncMock(return_value=taken)

        with pytest.raises(UserExistsError):
            await admin_service.update_user(
                mock_session, "user-001", email="taken@example.com"
            )

    async def test_leaves_the_email_alone_when_not_passed(self, mock_session):
        """The existing role/tier/is_active calls must not change behaviour."""
        user = _make_user_model(email="keep@example.com", email_verified=True)
        mock_session.get = AsyncMock(return_value=user)

        await admin_service.update_user(mock_session, "user-001", tier="pro")

        assert user.email == "keep@example.com"
        assert user.email_verified is True
```

Add `UserExistsError` to that file's imports:

```python
from app.core.exceptions import UserExistsError
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/app && python -m pytest tests/unit/services/test_admin_service.py -k UpdateUserEmail -v`

Expected: 3 failures, `TypeError: update_user() got an unexpected keyword argument 'email'`.

- [ ] **Step 3: Write the implementation**

In `services/app/app/services/admin_service.py`, change the `update_user` signature and body. Replace lines 87-92:

```python
async def update_user(
    session: AsyncSession,
    user_id: str,
    role: str | None = None,
    tier: str | None = None,
    is_active: bool | None = None,
    email: str | None = None,
) -> dict | None:
```

Then, after the `_guard_last_admin` call (line 118) and before `if role is not None:`, insert:

```python
    if email is not None and email != user.email:
        clash = await session.execute(
            select(User).where(User.email == email, User.id != user.id)
        )
        if clash.scalar_one_or_none():
            raise UserExistsError("email")
        user.email = email
        # A new address is unproven until its owner follows a link.
        user.email_verified = False
```

Add `email` to the docstring's Args block and `UserExistsError` to the Raises block.

- [ ] **Step 4: Add the field to the request schema**

In `services/app/app/api/admin.py`, replace lines 49-54:

```python
class UserUpdateRequest(BaseModel):
    """Request to update a user's role, tier, active status, or email."""

    role: str | None = None
    tier: str | None = None
    is_active: bool | None = None
    email: EmailStr | None = None
```

Confirm `EmailStr` is imported at the top of the file; if not, add it:

```python
from pydantic import BaseModel, EmailStr
```

Then find the `update_user` route (line 244) and add `email=body.email` to its `admin_service.update_user(...)` call, keeping the existing arguments.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd services/app && python -m pytest tests/unit/services/test_admin_service.py tests/unit/api -q`

Expected: all pass. The API tests catch a mismatch between the route call and the new signature.

- [ ] **Step 6: Commit**

```bash
git add services/app/app/services/admin_service.py services/app/app/api/admin.py services/app/tests/unit/services/test_admin_service.py
git commit -m "feat(admin): let an admin correct a user's email"
```

---

## Task 4: Preflight checks the AI provider credential

`AGENT_BACKEND=zai` with an empty `ZAI_API_KEY` passes preflight today and then fails every pipeline run — the symptom is broken uploads, arbitrarily far from the cause.

**Files:**
- Modify: `scripts/preflight-check.sh`
- Test: `services/app/tests/unit/test_preflight_script.py`

- [ ] **Step 1: Write the failing tests**

Create `services/app/tests/unit/test_preflight_script.py`:

```python
"""Tests for scripts/preflight-check.sh.

The script is the last gate before a beta deploy, so its checks are worth
guarding. It is bash, so these run it as a subprocess against generated .env
fixtures and assert on exit code and output.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[4] / "scripts" / "preflight-check.sh"

BASE_ENV = {
    "JWT_SECRET_KEY": "<test-placeholder>",
    "POSTGRES_PASSWORD": "<test-placeholder>",
    "CORS_ORIGINS": "https://studyaio.example.com",
    "SELF_HOSTED": "false",
    "REGISTRATION_MODE": "invite",
    "SMTP_HOST": "smtp.resend.com",
    "SMTP_FROM_EMAIL": "beta@example.com",
    "COOKIE_SECURE": "true",
    "OPENAPI_ENABLED": "false",
    "GLOBAL_MAX_AI_CALLS_PER_DAY": "300",
}


def _write_env(tmp_path: Path, **overrides) -> Path:
    """Write a .env fixture: BASE_ENV plus overrides. A None value omits a key."""
    values = {**BASE_ENV, **overrides}
    path = tmp_path / ".env"
    path.write_text(
        "".join(f"{k}={v}\n" for k, v in values.items() if v is not None)
    )
    return path


def _run(env_file: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), str(env_file)],
        capture_output=True,
        text=True,
    )


@pytest.fixture(autouse=True)
def _requires_bash():
    if shutil.which("bash") is None:  # pragma: no cover - CI always has bash
        pytest.skip("bash not available")


class TestProviderCredential:
    """The selected AGENT_BACKEND must have the key it needs."""

    def test_zai_without_a_key_fails(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="zai"))
        assert result.returncode == 1
        assert "ZAI_API_KEY" in result.stdout

    def test_zai_with_a_key_passes(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="zai", ZAI_API_KEY="<test-placeholder>"))
        assert result.returncode == 0, result.stdout

    def test_openai_without_a_key_fails(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="openai"))
        assert result.returncode == 1
        assert "OPENAI_API_KEY" in result.stdout

    def test_anthropic_api_without_a_key_fails(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="anthropic_api"))
        assert result.returncode == 1
        assert "ANTHROPIC_API_KEY" in result.stdout

    def test_claude_code_needs_no_key(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="claude_code"))
        assert result.returncode == 0, result.stdout

    def test_ollama_needs_no_key(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="ollama"))
        assert result.returncode == 0, result.stdout

    def test_unset_backend_defaults_to_claude_code(self, tmp_path):
        """An operator who never set AGENT_BACKEND is on the CLI default."""
        result = _run(_write_env(tmp_path, AGENT_BACKEND=None))
        assert result.returncode == 0, result.stdout

    def test_an_unknown_backend_fails(self, tmp_path):
        result = _run(_write_env(tmp_path, AGENT_BACKEND="gpt5-turbo-max"))
        assert result.returncode == 1
        assert "AGENT_BACKEND" in result.stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/app && python -m pytest tests/unit/test_preflight_script.py -v`

Expected: `test_zai_without_a_key_fails`, `test_openai_without_a_key_fails`, `test_anthropic_api_without_a_key_fails` and `test_an_unknown_backend_fails` all fail because the script exits 0. The rest pass.

- [ ] **Step 3: Write the implementation**

In `scripts/preflight-check.sh`, insert this section after the *Outbound email* block (which ends with its closing `fi`) and before `# ── Cookie Secure ──`:

```bash
# ── AI provider credentials ───────────────────────────────────────

AGENT_BACKEND=$(get_val "AGENT_BACKEND")
AGENT_BACKEND=${AGENT_BACKEND:-claude_code}

# A backend selected without its key fails at the first pipeline stage, and the
# symptom (uploads that never produce a summary) points nowhere near the cause.
require_key() {
    local backend="$1" var="$2"
    if [[ -z "$(get_val "$var")" ]]; then
        error "AGENT_BACKEND=$backend but $var is unset — every pipeline run will fail."
    else
        ok "AGENT_BACKEND=$backend with $var set"
    fi
}

case "$AGENT_BACKEND" in
    zai)           require_key zai ZAI_API_KEY ;;
    openai)        require_key openai OPENAI_API_KEY ;;
    anthropic_api) require_key anthropic_api ANTHROPIC_API_KEY ;;
    claude_code)
        ok "AGENT_BACKEND=claude_code — credentials come from the mounted ~/.claude"
        ;;
    ollama)
        ok "AGENT_BACKEND=ollama — no API key required"
        ;;
    *)
        error "AGENT_BACKEND='$AGENT_BACKEND' is not one of: claude_code, anthropic_api, openai, zai, ollama"
        ;;
esac
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd services/app && python -m pytest tests/unit/test_preflight_script.py -v`

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/preflight-check.sh services/app/tests/unit/test_preflight_script.py
git commit -m "feat(preflight): fail when the selected AI backend has no credential"
```

---

## Task 5: Preflight warns when no spend ceiling is set

`global_max_ai_calls_per_day` and `global_max_ai_tokens_per_day` default to `0`, which means unlimited (`app/config.py:134-135`). In SaaS mode that is the one setting standing between a metered provider and an unbounded bill.

**Files:**
- Modify: `scripts/preflight-check.sh`
- Test: `services/app/tests/unit/test_preflight_script.py`

- [ ] **Step 1: Write the failing tests**

Append to `services/app/tests/unit/test_preflight_script.py`:

```python
class TestSpendCeiling:
    """SaaS mode without a ceiling is a warning, not an error."""

    def test_warns_when_both_ceilings_are_unset(self, tmp_path):
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="zai",
                ZAI_API_KEY="<test-placeholder>",
                GLOBAL_MAX_AI_CALLS_PER_DAY=None,
            )
        )
        assert result.returncode == 0, result.stdout
        assert "WARN" in result.stdout
        assert "GLOBAL_MAX_AI" in result.stdout

    def test_warns_when_both_ceilings_are_zero(self, tmp_path):
        """0 means unlimited, which is the same exposure as unset."""
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="zai",
                ZAI_API_KEY="<test-placeholder>",
                GLOBAL_MAX_AI_CALLS_PER_DAY="0",
                GLOBAL_MAX_AI_TOKENS_PER_DAY="0",
            )
        )
        assert result.returncode == 0, result.stdout
        assert "GLOBAL_MAX_AI" in result.stdout

    def test_a_token_ceiling_alone_is_enough(self, tmp_path):
        result = _run(
            _write_env(
                tmp_path,
                AGENT_BACKEND="zai",
                ZAI_API_KEY="<test-placeholder>",
                GLOBAL_MAX_AI_CALLS_PER_DAY="0",
                GLOBAL_MAX_AI_TOKENS_PER_DAY="2000000",
            )
        )
        assert result.returncode == 0, result.stdout
        assert "Spend ceiling set" in result.stdout

    def test_self_hosted_is_not_warned(self, tmp_path):
        """A single-user box paying its own bill needs no ceiling."""
        result = _run(
            _write_env(
                tmp_path,
                SELF_HOSTED="true",
                AGENT_BACKEND="claude_code",
                SMTP_HOST=None,
                SMTP_FROM_EMAIL=None,
                GLOBAL_MAX_AI_CALLS_PER_DAY=None,
            )
        )
        assert "GLOBAL_MAX_AI" not in result.stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/app && python -m pytest tests/unit/test_preflight_script.py -k SpendCeiling -v`

Expected: `test_warns_when_both_ceilings_are_unset` and `test_warns_when_both_ceilings_are_zero` fail — no such warning is emitted.

- [ ] **Step 3: Write the implementation**

In `scripts/preflight-check.sh`, insert after the AI-provider section added in Task 4:

```bash
# ── Spend ceiling ─────────────────────────────────────────────────

GLOBAL_CALLS=$(get_val "GLOBAL_MAX_AI_CALLS_PER_DAY")
GLOBAL_TOKENS=$(get_val "GLOBAL_MAX_AI_TOKENS_PER_DAY")
GLOBAL_CALLS=${GLOBAL_CALLS:-0}
GLOBAL_TOKENS=${GLOBAL_TOKENS:-0}

# Per-user quotas cannot bound the operator's bill: N testers times their
# individual limits is unbounded in aggregate. Only in SaaS mode — a
# self-hosted box is paying for its own usage.
if [[ "$SELF_HOSTED" == "false" ]]; then
    if [[ "$GLOBAL_CALLS" == "0" && "$GLOBAL_TOKENS" == "0" ]]; then
        warn "GLOBAL_MAX_AI_CALLS_PER_DAY and GLOBAL_MAX_AI_TOKENS_PER_DAY are both 0 (unlimited) — nothing caps what the instance spends."
    else
        ok "Spend ceiling set (calls=$GLOBAL_CALLS, tokens=$GLOBAL_TOKENS; 0 = unlimited)"
    fi
fi
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd services/app && python -m pytest tests/unit/test_preflight_script.py -v`

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/preflight-check.sh services/app/tests/unit/test_preflight_script.py
git commit -m "feat(preflight): warn when SaaS mode has no spend ceiling"
```

---

## Task 6: Correct the closed-beta runbook

`docs/deployment.md` steps 4 and 5 predate PR #22 and now give wrong advice, and no step explains how to obtain the admin credential steps 3 and 4 both require.

**Files:**
- Modify: `docs/deployment.md`
- Modify: `.env.example:79`

- [ ] **Step 1: Add step 0 before the existing step 1**

In `docs/deployment.md`, immediately after the *Running a Closed Beta* heading and its `make preflight` sentence, insert:

```markdown
**0. Create an admin account.** Every step below needs one, and a fresh
instance has none you can log in to: the self-hosted default admin is created
with no password and an undeliverable `admin@studyaio.local` address, and the
admin API requires a real session. Bootstrap one while still in self-hosted
mode:

```bash
make ensure-admin email=you@example.com
```

The command prints a single-use set-password link valid for 24 hours. It
targets the existing default admin row when there is one, so everything that
account already owns keeps its owner. Follow the link, set a password, and
confirm you can log in **before** changing `SELF_HOSTED` — after the flip the
default identity no longer exists and there is no other way in.

The link is a bearer credential for an admin account. Do not paste it into a
shared channel.
```

- [ ] **Step 2: Replace step 4**

Replace the step 4 paragraph (currently: *"**4. Raise the free-tier limits.** `app/services/quota_service.py` caps the free tier at 1 course, 5 uploads/month and 20 AI calls/day. A real student hits that in one sitting — give beta testers `tier=pro` (Admin → Users) or raise the constants."*) with:

```markdown
**4. Raise the free-tier limits.** The defaults are shaped for a paywall, not a
beta: 1 course and 5 uploads/month. Keep testers on the **free** tier and raise
the limits by environment instead of promoting them to `pro`, which
short-circuits every per-user check and leaves only the global ceiling:

```env
FREE_MAX_COURSES=10
FREE_MAX_UPLOADS_PER_MONTH=60
FREE_MAX_AI_CALLS_PER_DAY=200
```

`0` means unlimited for any of these. `PRO_MAX_*` exist too, if you would rather
raise the pro tier than the free one.

The three do not need to balance: at roughly four pipeline calls per upload, 200
calls/day would allow ~50 uploads in a day, so the monthly upload cap is what
actually bounds pipeline usage. The daily call limit is there to bound chat and
Q&A, which no upload cap touches.
```

- [ ] **Step 3: Correct step 5's provider advice**

Replace step 5 with:

```markdown
**5. Decide who pays for AI.** `AGENT_BACKEND=claude_code` shells out to the CLI
using the credentials mounted into the worker, so every tester's usage bills to
that personal account — fine for a single-user box, wrong for a beta serving
other people. For a closed beta prefer a metered key:

```env
AGENT_BACKEND=zai
ZAI_MODEL=glm-5.3-flash
ZAI_API_KEY=...
```

`anthropic_api` is the higher-quality, higher-cost alternative. Preflight fails
if the backend you select has no credential. Cap spend at the provider account
level as well as in the app — the in-app ceiling can be defeated by a bug, and
two independent limits are the point.

Testers *can* supply their own credentials in Settings → AI Providers, which
moves the cost to them, but it is a rough first-run experience.
```

- [ ] **Step 4: Note the Cloudflare body limit in `.env.example`**

Replace line 79 of `.env.example` (`MAX_UPLOAD_SIZE_MB=100`) with:

```
# Keep this below your edge proxy's request body limit. Cloudflare's free and
# Pro plans cap bodies at 100MB, so a value of 100 makes a large lecture fail
# as an opaque 413 the app never sees. 50 keeps the rejection in the app.
MAX_UPLOAD_SIZE_MB=100
```

- [ ] **Step 5: Verify the doc renders and links resolve**

Run: `grep -n "ensure-admin\|FREE_MAX_COURSES\|glm-5.3-flash" docs/deployment.md`

Expected: at least one hit for each, in the *Running a Closed Beta* section.

- [ ] **Step 6: Commit**

```bash
git add docs/deployment.md .env.example
git commit -m "docs(beta): document the admin bootstrap and correct stale quota advice"
```

---

## Task 7: Ship Phase 1

- [ ] **Step 1: Run the full backend suite**

Run: `cd services/app && python -m pytest tests/unit tests/golden -q`

Expected: all pass, and 27 more tests than before this plan — 7 (Task 1) + 5 (Task 2) + 3 (Task 3) + 8 (Task 4) + 4 (Task 5).

- [ ] **Step 2: Run the linter**

Run: `make lint-python`

Expected: no errors. Run `make lint-python-fix` if ruff reports fixable issues, then re-run.

- [ ] **Step 3: Open the PR**

```bash
git push -u origin HEAD
gh pr create --title "Public beta: admin bootstrap, preflight gates, beta runbook" --body "Implements Phase 1 of docs/superpowers/specs/2026-09-03-studyaio-public-beta-design.md.

- ensure_admin + python -m app.cli ensure-admin: the only path to a first admin credential
- admins can correct a user's email
- preflight fails on a backend with no credential, warns on no spend ceiling in SaaS mode
- closed-beta runbook: new step 0, corrected quota and provider advice"
```

- [ ] **Step 4: Wait for CI green, then merge**

Expected jobs: Python Lint, Backend Tests, Integration Tests, Frontend Checks, E2E Tests. All must pass. Merging to `main` triggers `deploy.yml`, which builds GHCR images and rolls VM 210.

- [ ] **Step 5: Confirm the deploy landed**

Run: `gh run list --workflow=deploy.yml --limit 1`

Expected: the newest run is `completed success`. Its final step verifies `/health/ready` and the UI port, so a green run means the new image is live on VM 210.

---

## Task 8: Bootstrap the admin on VM 210

Still in self-hosted mode. This produces the credential every later task needs, and it is fully reversible — it sets a password on a row that had none.

**Host:** VM 210 (192.168.1.169), stack at `/opt/studyaio`

- [ ] **Step 1: Confirm the new image is running**

```bash
ssh 192.168.1.169 "cd /opt/studyaio && docker compose exec -T api python -c 'import app.cli; print(\"cli present\")'"
```

Expected: `cli present`. If it errors, the deploy in Task 7 did not land and the rest of this task will fail.

- [ ] **Step 2: Record who owns the existing data**

```bash
ssh 192.168.1.169 "cd /opt/studyaio && docker compose exec -T db psql -U studyaio -d studyaio -c \"select id, email, username, role, tier, is_active, hashed_password is null as no_password from users order by created_at;\""
```

Expected: at least one row. Note whether `00000000-0000-0000-0000-000000000001` is present and whether `no_password` is `t`. Save this output into the session notes — it is the before-state for the rollback.

- [ ] **Step 3: Bootstrap the admin**

```bash
ssh 192.168.1.169 "cd /opt/studyaio && docker compose exec -T api python -m app.cli ensure-admin --email <your-real-address>"
```

Expected: an `admin:` line naming the row from step 2, and an `open:` line with a `/reset-password?token=` URL. Note that `APP_BASE_URL` is still the internal hostname at this point, so the link points at `studyaio.home.aleksanlab.me` — that is correct and reachable now.

- [ ] **Step 4: Set the password and log in**

Open the printed URL in a browser on the LAN, set a password, then log in at `https://studyaio.home.aleksanlab.me`.

- [ ] **Step 5: Prove the credential reaches the admin API**

In the browser, load `https://studyaio.home.aleksanlab.me/api/admin/metrics`.

Expected: JSON including `total_users` and today's AI spend against the configured ceiling. A 401 or 403 here means the account is not actually an admin and Tasks 14–15 cannot proceed.

- [ ] **Step 6: Record it**

Append to the homelab-runbook session notes for this work: the command run, the user id it targeted, and that admin API access was confirmed. Do **not** record the token or the password.

---

## Task 9: Transactional email and DNS

**Trees:** Resend dashboard, Cloudflare dashboard for `aleksanlab.me`

- [ ] **Step 1: Create the Resend account and verify the sending domain**

Add the domain to Resend and create the DNS records it asks for in the `aleksanlab.me` Cloudflare zone — an SPF `TXT`, a DKIM `CNAME` or `TXT`, and the DMARC `TXT` if not already present. These are DNS-only records (grey cloud), never proxied.

- [ ] **Step 2: Wait for verification and confirm**

```bash
dig +short TXT aleksanlab.me | grep -i spf
```

Expected: an SPF record including Resend's sending domain. The Resend dashboard should show the domain `verified`.

- [ ] **Step 3: Create an API key and note the SMTP settings**

Resend's SMTP endpoint is `smtp.resend.com:587`, username `resend`, password the API key. Do not put it in a file yet — it goes into Infisical in Task 10.

- [ ] **Step 4: Send one test message**

```bash
curl -s -X POST https://api.resend.com/emails \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{"from":"beta@aleksanlab.me","to":"<your-address>","subject":"StudyAIO beta test","text":"Delivery works."}'
```

Expected: a JSON response with an `id`, and the message arriving in the inbox — not the spam folder. If it lands in spam, fix DNS now; step 5 of Task 15 depends on testers actually receiving mail.

---

## Task 10: Flip the app to SaaS mode

**Host:** VM 210, secrets via Infisical project `studyaio`

- [ ] **Step 1: Generate the new JWT secret**

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Rotating it invalidates every existing session, including your own from Task 8. That is expected — log in again afterwards.

- [ ] **Step 2: Set every value in Infisical**

Add or update these in the `studyaio` project. Do not hand-edit `/opt/studyaio/.env`; `infisical-compose-studyaio.service` regenerates it and a manual edit will be silently reverted.

```
SELF_HOSTED=false
REGISTRATION_MODE=invite
APP_BASE_URL=https://studyaio.aleksanlab.me
CORS_ORIGINS=https://studyaio.aleksanlab.me
OAUTH_REDIRECT_BASE_URL=https://studyaio.aleksanlab.me
COOKIE_SECURE=true
OPENAPI_ENABLED=false
JWT_SECRET_KEY=<from step 1>
POSTGRES_PASSWORD=<a new value, currently the literal "studyaio">
AGENT_BACKEND=zai
ZAI_MODEL=glm-5.3-flash
ZAI_API_KEY=<key>
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=<Resend API key>
SMTP_FROM_EMAIL=beta@aleksanlab.me
SMTP_FROM_NAME=StudyAIO
SMTP_USE_TLS=true
SENTRY_DSN=<dsn>
MAX_UPLOAD_SIZE_MB=50
FREE_MAX_COURSES=10
FREE_MAX_UPLOADS_PER_MONTH=60
FREE_MAX_AI_CALLS_PER_DAY=200
GLOBAL_MAX_AI_CALLS_PER_DAY=300
```

`GLOBAL_MAX_AI_TOKENS_PER_DAY` is deliberately left unset until Task 14 measures a real run.

`VITE_SENTRY_DSN` does **not** belong here — Vite inlines it at build time, so it is a GitHub Actions secret consumed by `deploy.yml`, not a runtime variable.

Changing `POSTGRES_PASSWORD` on an existing database does not change the role's password. Either leave it and accept the preflight warning, or run
`docker compose exec -T db psql -U studyaio -d studyaio -c "alter role studyaio with password '<new>';"`
and set the variable to match, then recreate the stack. Getting this half-done breaks every DB connection, so do both or neither.

- [ ] **Step 2b: Regenerate the env file and confirm**

```bash
ssh 192.168.1.169 "sudo systemctl restart infisical-compose-studyaio.service && grep -c . /opt/studyaio/.env"
```

Expected: a non-zero count, and the unit `active (exited)` without errors.

- [ ] **Step 3: Run preflight — the gate**

```bash
ssh 192.168.1.169 "cd /opt/studyaio && bash scripts/preflight-check.sh .env"
```

Expected: `0 errors`. Any error stops this task. If `scripts/` is not present on the host, copy it: `scp scripts/preflight-check.sh 192.168.1.169:/opt/studyaio/scripts/`.

- [ ] **Step 4: Roll the stack**

```bash
ssh 192.168.1.169 "cd /opt/studyaio && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d && sleep 10 && docker compose ps"
```

Expected: `api`, `ui`, `worker`, `beat`, `db`, `redis` all `Up`, with `api` and `worker` healthy. If `api` restarts in a loop, check `docker compose logs api` for the default-JWT `RuntimeError` (`app/main.py:127-131`) — it refuses to boot rather than run insecurely.

- [ ] **Step 5: Confirm SaaS mode is actually on**

```bash
ssh 192.168.1.169 "curl -fsS http://localhost:8000/api/auth/config"
```

Expected: JSON with `"self_hosted": false` and `"registration_enabled": true`. `self_hosted: true` means the variable did not reach the container.

- [ ] **Step 6: Log in again over the internal hostname**

At `https://studyaio.home.aleksanlab.me`, log in with the Task 8 credentials. Your old session is dead from the JWT rotation; a successful fresh login proves the account survived the flip. **If this fails, stop** — go back to Task 8's `ensure-admin`, which still works, rather than proceeding to expose a box you cannot administer.

---

## Task 11: Public Caddy site on the PVE proxy

**Tree:** `homelab-runbook`, `inventory/caddy/Caddyfile`

- [ ] **Step 1: Add the public site block**

Add a new top-level block after the `jellyfin.{$DOMAIN}` block (which ends around line 600). It is top-level, not inside the `*.home.{$DOMAIN}` wildcard, because this host is public.

```caddy
# StudyAIO (public beta, via VPS reverse proxy)
# No Authelia: the app owns its own auth, and forward-auth would consume the
# app's Authorization header. CrowdSec applies via the global order directive.
studyaio.{$DOMAIN} {
	crowdsec

	# The global log block does not produce per-request lines for a site.
	log {
		output file /var/log/caddy/studyaio.log {
			roll_size 10MiB
			roll_keep 5
		}
	}

	# chat, uploads, courseops and exports all stream; buffering breaks token
	# streaming and pipeline progress. Needed on this hop and on the VPS.
	handle /api/* {
		reverse_proxy 192.168.1.169:8000 {
			flush_interval -1
			header_down -Server
		}
	}

	handle /health/* {
		reverse_proxy 192.168.1.169:8000
	}

	handle {
		reverse_proxy 192.168.1.169:3001 {
			header_down -Server
		}
	}
}
```

Leave the existing `@studyaio` block inside the wildcard untouched — it keeps LAN administration behind Authelia, and it is the fallback if this task is rolled back.

- [ ] **Step 2: Validate before reloading**

```bash
ssh 192.168.1.200 "docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile"
```

Expected: `Valid configuration`. Do not reload on anything else — a broken Caddyfile takes down every homelab service, not just this one.

- [ ] **Step 3: Reload**

```bash
ssh 192.168.1.200 "docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile"
```

Expected: no output, exit 0.

- [ ] **Step 4: Confirm the new host answers before DNS exists**

```bash
ssh 192.168.1.200 "curl -fsS -o /dev/null -w '%{http_code}\n' -H 'Host: studyaio.aleksanlab.me' https://127.0.0.1/health/ready --insecure"
```

Expected: `200`. This proves the block routes to VM 210 without depending on Cloudflare or the VPS yet.

- [ ] **Step 5: Confirm the internal host still works**

Load `https://studyaio.home.aleksanlab.me` in a browser. Expected: the Authelia prompt, then the app. A regression here means the new top-level block is shadowing the wildcard.

- [ ] **Step 6: Commit the runbook change**

```bash
cd /home/alex/homelab-runbook
git add inventory/caddy/Caddyfile
git commit -m "caddy: public studyaio.aleksanlab.me site for the closed beta"
```

---

## Task 12: VPS Caddy site and Cloudflare record

**Trees:** `/opt/caddy/Caddyfile` on `finland-vpn-1` (untracked), Cloudflare zone `aleksanlab.me`

- [ ] **Step 1: Add the site to the VPS Caddyfile**

SSH as `bridge` (`ssh vpn_finland_1`), edit `/opt/caddy/Caddyfile`, and add a block mirroring the existing `jellyfin.aleksanlab.me` one:

```caddy
studyaio.aleksanlab.me {
	reverse_proxy https://192.168.1.200 {
		header_up Host {host}
		flush_interval -1
		header_down -Server
		header_down -x-response-time-ms
		transport http {
			tls_server_name studyaio.aleksanlab.me
		}
	}
}
```

`192.168.1.200` is reachable because PVE advertises `192.168.1.0/24` as a Tailscale subnet route and the VPS runs with `--accept-routes`. Copy the exact shape of the neighbouring Jellyfin block rather than this snippet if they differ — that block is known-good in production.

- [ ] **Step 2: Validate and reload**

```bash
ssh vpn_finland_1 "cd /opt/caddy && docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile && docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile"
```

Expected: `Valid configuration`, then no output.

- [ ] **Step 3: Create the Cloudflare record**

In the `aleksanlab.me` zone, add `studyaio` → `45.148.127.199`, **proxied** (orange cloud), matching `jellyfin`.

- [ ] **Step 4: Verify end to end from outside the LAN**

```bash
curl -fsS -o /dev/null -w '%{http_code} %{ssl_verify_result}\n' https://studyaio.aleksanlab.me/health/ready
```

Expected: `200 0`. Run this from a machine that is not on the homelab LAN — from inside, split-horizon DNS can make a broken public path look fine.

- [ ] **Step 5: Verify the SPA loads and its API calls succeed**

Open `https://studyaio.aleksanlab.me` in a browser with devtools open. Expected: the login page renders, and `/api/auth/config` returns 200 with `self_hosted: false`. A blank page with a 401 on `/api/*` means an Authelia block is still in the path.

- [ ] **Step 6: Record the untracked change**

The VPS Caddyfile is not in version control, so nothing else will capture this. Append the exact block to the homelab-runbook session notes for this work, and update the VPS layout memory if the site list is enumerated there.

---

## Task 13: Backups, monitoring and alerting

- [ ] **Step 1: Add a nightly pg_dump on VM 210**

VM 210 is in `backup-all-pbs`, but that is a crash-consistent snapshot of a running Postgres. Create `/usr/local/bin/studyaio-pg-dump.sh` on VM 210, modelled on the existing `immich-pg-dump.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
DEST=/opt/studyaio/backups
mkdir -p "$DEST"
cd /opt/studyaio
docker compose exec -T db pg_dump -U studyaio -Fc studyaio \
  > "$DEST/studyaio-$(date +%F).dump"
find "$DEST" -name 'studyaio-*.dump' -mtime +14 -delete
```

- [ ] **Step 2: Schedule it before the PBS window**

Create `/etc/cron.d/studyaio-pg-dump`:

```
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
30 1 * * * root /usr/local/bin/studyaio-pg-dump.sh
```

`PATH` is set explicitly because `/etc/cron.d` does not inherit it, and `docker` would otherwise not be found — a failure mode that no interactive shell test reproduces.

- [ ] **Step 3: Prove it works now, not tomorrow**

```bash
ssh 192.168.1.169 "sudo /usr/local/bin/studyaio-pg-dump.sh && ls -lh /opt/studyaio/backups/"
```

Expected: a `.dump` file of non-trivial size. A zero-byte file means `pg_dump` failed and the redirect swallowed it.

- [ ] **Step 4: Add the Uptime Kuma monitor**

Add an HTTP monitor for `https://studyaio.aleksanlab.me/health/ready`, expecting 200, checked every 60s. Point it at the public URL, not the container — the whole edge chain is what can break.

- [ ] **Step 5: Add the spend and failure alerts**

Add Prometheus rules for pipeline failure rate and for daily AI spend approaching `GLOBAL_MAX_AI_CALLS_PER_DAY`. Set severity `critical` for both: `warning` routes only through n8n, and these are the two signals that must not be missed during a beta.

- [ ] **Step 6: Commit the runbook changes**

```bash
cd /home/alex/homelab-runbook
git add -A
git commit -m "studyaio: nightly pg_dump, uptime monitor, beta alerts"
```

---

## Task 14: Validate GLM on a real lecture and set the ceilings

The highest-risk step in the whole plan. The prompts were tuned for Claude. `tests/golden/test_summary_structure.py` derives its required section list from `prompts/summarize.txt`, but it runs against a fixture, not a live model — so `glm-5.3-flash` can produce structurally different summaries with the entire suite green.

- [ ] **Step 1: Note the starting spend**

Load `https://studyaio.aleksanlab.me/api/admin/metrics` and record today's AI calls and tokens.

- [ ] **Step 2: Upload a real multi-week lecture PDF**

Use a genuine course PDF, not a one-page sample — classification and summarization behave differently on real material.

- [ ] **Step 3: Watch the pipeline complete**

```bash
ssh 192.168.1.169 "cd /opt/studyaio && docker compose logs -f worker"
```

Expected: `ingest` → `classify` → `extract` → `summarize` → `index` → `assets` all succeeding. Any adapter error here is a Z.ai wiring problem, not a prompt problem.

- [ ] **Step 4: Read the generated summary against the prompt contract**

Open the summary in the UI and check it has all eight sections the prompt requires: Overview, Key Concepts, Definitions, Diagrams & Visual Descriptions, Code Examples, Formulas & Algorithms, Key Takeaways, Connections — plus the `*Sources: … Version: N.*` footer, and `###`/`####` subsections under Key Concepts rather than a flat bullet list.

If sections are missing or reordered, **stop the beta rollout here.** The options are to tighten `prompts/summarize.txt` for GLM, move to `glm-5.3` (non-flash), or fall back to `anthropic_api`. Do not hand out invite codes against a model that produces summaries the UI and the golden fixture disagree with.

- [ ] **Step 5: Check classification, flashcards and the quiz by eye**

Confirm the course code, week number and title are right, and that generated flashcards and quiz questions are about the lecture rather than generic. This is the output testers will judge the product on.

- [ ] **Step 6: Measure the cost of one upload**

Reload `/api/admin/metrics` and subtract the step 1 figures. That difference is the real per-upload cost.

- [ ] **Step 7: Set the token ceiling from the measurement**

With cost-per-upload known, compute a daily token ceiling for the expected tester count with headroom, and set `GLOBAL_MAX_AI_TOKENS_PER_DAY` in Infisical. Re-tune `GLOBAL_MAX_AI_CALLS_PER_DAY` from its interim 300 at the same time. Restart the stack and re-run preflight; it should now report the ceiling as `[ OK ]` rather than warning.

- [ ] **Step 8: Set the provider-side cap**

Set a hard spend limit on the Z.ai account. Two independent ceilings is the point — the in-app one can be defeated by a bug in the app.

---

## Task 15: Verify the beta and open the door

- [ ] **Step 1: Registration is gated**

Attempt sign-up at `https://studyaio.aleksanlab.me/register` with no code, then with a nonsense code. Expected: both rejected, with the same message — an attacker must not learn whether a code exists.

- [ ] **Step 2: Mint a code and redeem it**

```bash
curl -X POST https://studyaio.aleksanlab.me/api/admin/invites \
  -H 'Content-Type: application/json' \
  --cookie 'access_token=<your admin token>' \
  -d '{"max_uses": 1, "expires_in_days": 30, "note": "self-test"}'
```

Register a throwaway account with the returned code. Expected: success. Then try the same code again. Expected: rejected — it is single-use.

- [ ] **Step 3: Verification email arrives externally**

Check the throwaway account's inbox for the verification email, and follow the link. Expected: delivered to the inbox, not spam, and the unverified banner clears. "SMTP configured" is not evidence; delivery is.

- [ ] **Step 4: Password reset round trip**

Request a reset for the throwaway account, follow the emailed link, set a new password, log in with it. Expected: all four steps succeed. This is the path that saves a locked-out tester, and it is the one that fails silently when misconfigured.

- [ ] **Step 5: Streaming works through both hops**

Ask a question in the chat UI on the public URL. Expected: tokens appear incrementally, not all at once after a pause. A single delayed block means `flush_interval -1` is missing on one of the two Caddy hops.

- [ ] **Step 6: Session handling on the real domain**

Log in, refresh the page, confirm the session survives. Then change the password. Expected: a deliberate sign-out with the reason shown on the login page, not an unexplained 401.

- [ ] **Step 7: The ceiling actually bites**

Temporarily set `GLOBAL_MAX_AI_CALLS_PER_DAY` to a value below today's usage and restart the API. Attempt an upload. Expected: HTTP 429 with a `Retry-After` header. Confirm a pipeline already running finishes rather than being killed. Restore the real value afterwards and confirm uploads work again.

- [ ] **Step 8: Delete the throwaway account**

Use Admin → Users to delete it, and confirm from `/api/admin/metrics` that `total_users` drops. This also exercises the deletion path on real data before a tester ever asks for it.

- [ ] **Step 9: Mint the real invite codes**

One code per tester, with a `note` naming them so a leaked code can be traced to the account it created.

- [ ] **Step 10: Write the session notes**

Record in `homelab-runbook/sessions/2026-09-04_studyaio-public-beta/`: the Caddy blocks added on both proxies, the Infisical keys set, the measured per-upload cost and the ceilings chosen, and the verification results. Note explicitly that the VPS Caddyfile is untracked, so these notes are the only record of that change.

---

## Rollback

Ordered from cheapest to most complete:

1. **Stop new signups:** set `REGISTRATION_MODE=closed` in Infisical and restart the API. Existing testers keep working; nobody new gets in. No edge change.
2. **Withdraw from the internet:** delete the Cloudflare `studyaio` record and remove the VPS Caddy block. The internal `studyaio.home.aleksanlab.me` host is untouched throughout, so LAN access never depended on any of this.
3. **Back to single-user:** set `SELF_HOSTED=true`. The default-identity fallback returns. This is why Task 1 sets a password on the existing default-admin row instead of moving data to a new account — the same row works in both modes.
4. **Back to Claude:** set `AGENT_BACKEND=claude_code`. Metering keeps working; token counts go to zero because the CLI reports no usage.

Phase 1 needs no rollback: `ensure_admin` and the preflight checks are additive, and every existing call site keeps its behaviour.
