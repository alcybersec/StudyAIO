"""Email case normalization across the account path (issue #91).

Nothing folded email case, and `users.email` was looked up by exact match
everywhere, which produced three separate failures from one omission:

1. An admin retyping the stored address in a different case read as a *change*,
   so `update_user` ran the full destructive repoint — sessions revoked, OAuth
   unlinked, outstanding magic links killed, `email_verified` cleared.
2. The repoint then stored the new casing, and since login looks up by exact
   match the user could no longer sign in. `request_password_reset` uses the
   same lookup and returns 202 either way, so they got no signal at all.
3. `alex@example.com` and `Alex@example.com` were two valid accounts — and
   `create_or_link_oauth`'s refusal to auto-link to a password-backed account
   (issue #70) did not fire, because the differently-cased row was not found.

The fake session below is the point of this file. `tests/unit` has no
database, and an `AsyncMock` session returns whatever the test wired regardless
of the SQL it was handed — so every assertion here would pass against the
unfixed code. `_FakeUserTable` answers from the statement's real bound
parameters instead, exactly as an exact-match unique index would, so a lookup
that forgets to normalize misses.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import (
    AuthenticationError,
    OAuthAccountLinkRequiredError,
    UserExistsError,
)
from app.core.utils import normalize_email
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.services import admin_service, user_service

# Not a credential: an argon2-shaped placeholder these tests only compare
# against a patched verifier.
PLACEHOLDER_HASH = "<test-placeholder>-argon2-hash"


def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-001",
        "email": "alex@example.com",
        "username": "alex",
        "hashed_password": PLACEHOLDER_HASH,
        "role": "user",
        "tier": "free",
        "is_active": True,
        "email_verified": True,
        "mfa_enabled": False,
        "mfa_secret": None,
        "backup_codes": None,
        "avatar_url": None,
        "last_login_at": None,
        "tokens_valid_from": None,
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for key, value in defaults.items():
        setattr(user, key, value)
    return user


def _bound(stmt) -> tuple[str, dict]:
    """The SQL text and bound parameters of a Core statement."""
    compiled = stmt.compile()
    return str(compiled), dict(compiled.params)


class _FakeUserTable:
    """An `AsyncSession` stand-in that answers `WHERE users.email = :x` exactly.

    Only equality on `email`, `username` and the OAuth identity is understood —
    that is every lookup on the paths under test. Anything else returns no row,
    which is the safe answer for a clash check. Writes (UPDATE/DELETE) are
    recorded rather than applied, so a test can assert that a repoint's
    destructive statements did *not* run.
    """

    def __init__(self, users: list[User], oauth_accounts: list[OAuthAccount] | None = None) -> None:
        self.users = users
        self.oauth_accounts = oauth_accounts or []
        self.writes: list[str] = []
        self.added: list[object] = []

    # -- AsyncSession surface -------------------------------------------------

    def add(self, obj) -> None:
        self.added.append(obj)
        # Rows become visible to later lookups in the same call, as they would
        # after a flush: `create_user` mints its setup link by looking the
        # account it just created back up by email.
        if isinstance(obj, User):
            self.users.append(obj)
        elif isinstance(obj, OAuthAccount):
            self.oauth_accounts.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def get(self, _model, primary_key):
        return next((u for u in self.users if u.id == primary_key), None)

    async def execute(self, stmt):
        sql, params = _bound(stmt)
        if not sql.lstrip().upper().startswith("SELECT"):
            self.writes.append(sql)
            return MagicMock()
        return self._select(sql, params)

    # -- lookup ---------------------------------------------------------------

    def _select(self, sql: str, params: dict):
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=self._match(sql, params))
        return result

    def _match(self, sql: str, params: dict):
        if "oauth_accounts.provider_user_id" in sql:
            wanted = params.get("provider_user_id_1")
            provider = params.get("provider_1")
            return next(
                (
                    a
                    for a in self.oauth_accounts
                    if a.provider_user_id == wanted and a.provider == provider
                ),
                None,
            )

        candidates = list(self.users)
        understood = False
        if "users.email = :email_1" in sql:
            candidates = [u for u in candidates if u.email == params.get("email_1")]
            understood = True
        if "users.username = :username_1" in sql:
            candidates = [u for u in candidates if u.username == params.get("username_1")]
            understood = True
        if "users.role = :role_1" in sql:
            candidates = [u for u in candidates if u.role == params.get("role_1")]
            understood = True
        if "users.id = :id_1" in sql:
            candidates = [u for u in candidates if u.id == params.get("id_1")]
            understood = True
        # `_repoint_email`'s clash check excludes the row being changed.
        if "users.id != :id_1" in sql:
            candidates = [u for u in candidates if u.id != params.get("id_1")]
            understood = True

        if not understood:
            return None
        return candidates[0] if candidates else None


class TestNormalizeEmail:
    """The shared helper. Whitespace and case both go."""

    def test_lowercases_the_domain(self):
        assert normalize_email("alex@EXAMPLE.com") == "alex@example.com"

    def test_lowercases_the_local_part_too(self):
        # Deliberate: RFC 5321 makes this technically case-sensitive. See the
        # function's docstring for why the whole address is folded anyway.
        assert normalize_email("Alex@example.com") == "alex@example.com"

    def test_strips_surrounding_whitespace(self):
        assert normalize_email("  Alex@Example.com \n") == "alex@example.com"

    def test_already_canonical_is_unchanged(self):
        assert normalize_email("alex@example.com") == "alex@example.com"


@pytest.mark.asyncio
class TestGetUserByEmail:
    """The lookup every other consequence is downstream of."""

    async def test_finds_the_row_whatever_the_casing(self):
        session = _FakeUserTable([_make_user(email="alex@example.com")])

        found = await user_service.get_user_by_email(session, "ALEX@Example.COM")

        assert found is not None
        assert found.id == "user-001"

    async def test_finds_the_row_despite_surrounding_whitespace(self):
        session = _FakeUserTable([_make_user(email="alex@example.com")])

        assert await user_service.get_user_by_email(session, " alex@example.com ") is not None

    async def test_a_genuinely_different_address_still_misses(self):
        session = _FakeUserTable([_make_user(email="alex@example.com")])

        assert await user_service.get_user_by_email(session, "someone@example.com") is None


@pytest.mark.asyncio
class TestAuthenticateUser:
    """Consequence 2: the lockout."""

    async def test_login_succeeds_with_any_casing(self):
        user = _make_user(email="alex@example.com")
        session = _FakeUserTable([user])

        with patch("app.services.user_service.verify_password", return_value=True):
            authenticated = await user_service.authenticate_user(
                session, "Alex@Example.com", "pw-does-not-matter"
            )

        assert authenticated is user

    async def test_login_succeeds_with_surrounding_whitespace(self):
        user = _make_user(email="alex@example.com")
        session = _FakeUserTable([user])

        with patch("app.services.user_service.verify_password", return_value=True):
            assert await user_service.authenticate_user(session, " alex@example.com ", "pw") is user

    async def test_an_unknown_address_is_still_rejected(self):
        session = _FakeUserTable([_make_user(email="alex@example.com")])

        with patch("app.services.user_service.verify_password", return_value=True):
            with pytest.raises(AuthenticationError):
                await user_service.authenticate_user(session, "nobody@example.com", "pw")


@pytest.mark.asyncio
class TestRegisterUser:
    """Consequence 3: duplicate accounts."""

    async def test_a_differently_cased_address_is_refused_as_a_duplicate(self):
        session = _FakeUserTable([_make_user(email="alex@example.com")])

        with patch("app.services.user_service.hash_password", return_value=PLACEHOLDER_HASH):
            with pytest.raises(UserExistsError):
                await user_service.register_user(
                    session, "Alex@Example.com", "alex2", "password-long-enough"
                )

        assert session.added == []

    async def test_the_stored_address_is_canonical(self):
        session = _FakeUserTable([])

        with patch("app.services.user_service.hash_password", return_value=PLACEHOLDER_HASH):
            user = await user_service.register_user(
                session, "  Alex@Example.COM ", "alex", "password-long-enough"
            )

        assert user.email == "alex@example.com"


@pytest.mark.asyncio
class TestOAuthLinkRefusal:
    """Consequence 3, second half: #70's protection reopened for any casing.

    `create_or_link_oauth` refuses to attach a provider identity to an account
    that has a password, because possession of the mailbox is not proof of that
    account. Exact-match lookup meant a differently-cased local account was not
    found, the refusal never fired, and the pre-account-takeover was back.
    """

    async def test_refuses_a_differently_cased_password_backed_account(self):
        session = _FakeUserTable([_make_user(email="alex@example.com")])

        with pytest.raises(OAuthAccountLinkRequiredError):
            await user_service.create_or_link_oauth(
                session,
                "google",
                "goog-123",
                "Alex@Example.com",
                email_verified=True,
            )

        assert session.added == []

    async def test_links_to_a_differently_cased_passwordless_account(self):
        """The other half of #70: no password means nothing to bypass."""
        user = _make_user(email="alex@example.com", hashed_password=None)
        session = _FakeUserTable([user])

        linked = await user_service.create_or_link_oauth(
            session,
            "google",
            "goog-123",
            "ALEX@example.com",
            email_verified=True,
        )

        assert linked is user
        assert len(session.added) == 1

    async def test_a_new_account_is_created_with_the_canonical_address(self):
        session = _FakeUserTable([])

        created = await user_service.create_or_link_oauth(
            session,
            "google",
            "goog-999",
            "New.Person@Example.COM",
            email_verified=True,
        )

        assert created.email == "new.person@example.com"


@pytest.mark.asyncio
class TestAdminUpdateUserEmail:
    """Consequence 1: the destructive no-op repoint."""

    async def test_case_only_change_revokes_nothing(self):
        user = _make_user(email="alex@example.com", email_verified=True)
        session = _FakeUserTable([user])

        await admin_service.update_user(session, "user-001", email="Alex@Example.com")

        # The three tells of `_repoint_email`, none of which may have happened.
        assert user.tokens_valid_from is None, "sessions were revoked for a no-op"
        assert user.email_verified is True, "verification was cleared for a no-op"
        assert session.writes == [], f"destructive statements ran: {session.writes}"

    async def test_case_only_change_leaves_the_address_canonical(self):
        user = _make_user(email="alex@example.com")
        session = _FakeUserTable([user])

        result = await admin_service.update_user(session, "user-001", email="ALEX@EXAMPLE.COM")

        assert user.email == "alex@example.com"
        assert result["email"] == "alex@example.com"

    async def test_a_legacy_mixed_case_row_is_folded_without_a_repoint(self):
        """A row written before the migration is repaired, not repointed.

        Without this branch the comparison would see a difference against the
        stored `Alex@…`, and an admin echoing the address back would trigger
        exactly the destructive path this issue is about.
        """
        user = _make_user(email="Alex@Example.com", email_verified=True)
        session = _FakeUserTable([user])

        await admin_service.update_user(session, "user-001", email="alex@example.com")

        assert user.email == "alex@example.com"
        assert user.tokens_valid_from is None
        assert user.email_verified is True
        assert session.writes == []

    async def test_a_real_change_still_repoints(self):
        """The guard must not swallow the case it exists to allow."""
        user = _make_user(email="wrong@example.com", email_verified=True)
        session = _FakeUserTable([user])

        await admin_service.update_user(session, "user-001", email="Right@Example.com")

        assert user.email == "right@example.com"
        assert user.tokens_valid_from is not None, "a real repoint must revoke sessions"
        assert user.email_verified is False
        assert any("oauth_accounts" in sql for sql in session.writes)
        assert any("magic_links" in sql for sql in session.writes)

    async def test_a_case_differing_address_owned_by_someone_else_is_refused(self):
        """Otherwise the repoint would create the duplicate the index forbids."""
        user = _make_user(id="user-001", email="alex@example.com")
        other = _make_user(id="user-002", email="taken@example.com", username="taken")
        session = _FakeUserTable([user, other])

        with pytest.raises(UserExistsError):
            await admin_service.update_user(session, "user-001", email="Taken@Example.com")


@pytest.mark.asyncio
class TestAdminCreateUser:
    """The other admin write path onto `users.email`."""

    async def test_refuses_a_differently_cased_existing_address(self):
        session = _FakeUserTable([_make_user(email="alex@example.com")])

        with pytest.raises(UserExistsError):
            await admin_service.create_user(session, "Alex@Example.com", "alex2")

    async def test_stores_the_canonical_address(self):
        session = _FakeUserTable([])

        user, _token = await admin_service.create_user(session, " New@Example.COM ", "newbie")

        assert user.email == "new@example.com"


@pytest.mark.asyncio
class TestEnsureAdmin:
    """Re-running ensure-admin must not sign the operator out of their console."""

    async def test_case_only_difference_is_not_a_repoint(self):
        admin = _make_user(id="admin-1", email="admin@example.com", role="admin", username="admin")
        session = _FakeUserTable([admin])

        await admin_service.ensure_admin(session, "Admin@Example.com")

        assert admin.tokens_valid_from is None
        assert admin.email == "admin@example.com"
        assert not any("oauth_accounts" in sql for sql in session.writes)


class TestLoginThrottleKey:
    """The throttle already folded case; it must keep doing so via one helper.

    Two spellings of one address sharing a counter is the point — otherwise an
    attacker gets a fresh allowance per casing.
    """

    def test_casing_does_not_change_the_key(self):
        from app.core import login_throttle

        assert login_throttle._key("Alex@Example.com") == login_throttle._key("alex@example.com")

    def test_whitespace_does_not_change_the_key(self):
        from app.core import login_throttle

        assert login_throttle._key(" alex@example.com ") == login_throttle._key("alex@example.com")
