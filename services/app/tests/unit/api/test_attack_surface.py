"""Attack classes the app already survives, pinned so it keeps doing so.

Each class below was exercised by hand against the live instance and behaved
correctly; none of them had a test, so none of them was protected from a
regression. That is the whole reason this file exists — "we checked once" is not
a property of the code, it is a property of an afternoon.

Covered here: SQL injection through search, path traversal through an upload
filename, CORS origin reflection, and invite-code enumeration. The fifth class
from the same list — privilege escalation from `role="user"` to the admin
endpoints — is covered by a route walk in `test_endpoint_authn_guard.py`, since
it wants the same route enumeration rather than a hand-picked endpoint.
"""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.dialects import postgresql

from app.config import settings
from app.core.exceptions import InviteError
from app.core.storage import reset_storage
from app.core.utils import sanitize_filename
from app.main import app
from app.models.invite_code import InviteCode
from app.services import artifact_service, invite_service, search_service

# The three shapes an injection attempt takes: a destructive statement smuggled
# through a terminator, a tautology that would widen a WHERE clause, and a UNION
# that would graft another table onto the result set.
SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE courses; --",
    "' OR '1'='1",
    "' UNION SELECT email, hashed_password FROM users --",
]


# No class-level asyncio mark: pytest.ini sets asyncio_mode=auto, and marking a
# class that also holds sync tests makes pytest warn on each of them.
class TestSqlInjectionIsLiteralText:
    """Search payloads must reach Postgres as a bound value, never as SQL."""

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    async def test_search_binds_the_payload_instead_of_interpolating_it(self, payload):
        """Compile the real statements and check where the payload ends up.

        Asserting "the request returned 200" would pass just as happily against
        an f-string query that had already dropped the table, so this looks at
        the SQL itself: the payload must appear in the bound parameters and must
        *not* appear anywhere in the compiled statement text.

        The bound value is the payload after `escape_like`, which neutralises
        LIKE metacharacters -- so `hashed_password` binds as `hashed\\_password`.
        Both forms are checked against the SQL text, and the escaped one against
        the parameters.
        """
        session = AsyncMock()
        rows = MagicMock()
        rows.all.return_value = []
        session.execute.return_value = rows

        await search_service.search_all(session, "user-001", payload, limit=10)

        escaped = search_service.escape_like(payload)
        statements = [call.args[0] for call in session.execute.await_args_list]
        assert statements, "search_all issued no queries -- the assertions below are vacuous"

        for statement in statements:
            compiled = statement.compile(dialect=postgresql.dialect())
            assert payload not in str(compiled), (
                f"payload interpolated into the SQL text:\n{compiled}"
            )
            assert escaped not in str(compiled), (
                f"escaped payload interpolated into the SQL text:\n{compiled}"
            )
            assert any(escaped in str(v) for v in compiled.params.values()), (
                f"payload is not among the bound parameters: {compiled.params}"
            )

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    async def test_search_endpoint_echoes_the_payload_and_changes_nothing(
        self, async_client, mock_session, payload
    ):
        """End to end: the payload comes back as the search term, and nothing is written."""
        response = await async_client.get("/api/search", params={"q": payload})

        assert response.status_code == 200
        assert response.json()["query"] == payload
        assert response.json()["results"] == []
        mock_session.commit.assert_not_awaited()

    def test_like_wildcards_in_a_payload_are_escaped(self):
        """`%` and `_` are LIKE metacharacters, not a second injection vector.

        Unescaped, `'%' OR ...` would still be *safe* SQL but a match-everything
        pattern. `escape_like` is what keeps a search term a search term.
        """
        assert search_service.escape_like("100%_done") == r"100\%\_done"
        assert search_service.escape_like(r"back\slash") == r"back\\slash"


class TestUploadFilenamePathTraversal:
    """A filename is attacker-controlled text, not a path."""

    async def test_traversal_filename_stays_inside_the_uploads_directory(self):
        """`../../../etc/cron.d/x.pdf` must land in uploads/, flattened.

        The interesting assertion is not the stored key's shape but the resolved
        absolute path: `LocalStorageBackend` joins the key onto `data_dir`
        directly, so a single surviving `..` segment would write outside it. The
        walk of the temp directory afterwards is what proves nothing escaped —
        checking only the returned path would miss a second file written along
        the way.
        """
        payload = "../../../etc/cron.d/x.pdf"
        session = AsyncMock()
        session.add = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(settings, "data_dir", tmpdir):
                reset_storage()
                try:
                    artifact = await artifact_service.create_upload_artifact(
                        session,
                        content=b"%PDF-1.4 test",
                        original_filename=payload,
                        sha256="a" * 64,
                        user_id="user-001",
                    )
                finally:
                    reset_storage()

                root = Path(tmpdir).resolve()
                uploads = root / "uploads"
                stored = (root / artifact.file_path).resolve()

                assert ".." not in Path(artifact.file_path).parts
                assert stored.is_relative_to(uploads), f"{stored} escaped {uploads}"
                assert stored.is_file()

                written = sorted(p.resolve() for p in root.rglob("*") if p.is_file())
                assert written == [stored], f"unexpected files written: {written}"

        # The original name is still recorded verbatim — it is display text, and
        # keeping it is what makes flattening the *stored* name sufficient.
        assert artifact.original_filename == payload

    @pytest.mark.parametrize(
        "payload",
        [
            "../../../etc/cron.d/x.pdf",
            "..\\..\\windows\\system32\\x.pdf",
            "/etc/passwd",
            "uploads/../../secret.pdf",
        ],
    )
    def test_sanitize_filename_drops_every_separator(self, payload):
        """The primitive the guarantee rests on: no separator survives."""
        cleaned = sanitize_filename(payload)
        assert "/" not in cleaned
        assert "\\" not in cleaned
        assert not Path(cleaned).is_absolute()
        assert ".." not in Path(cleaned).parts


@pytest.mark.asyncio
class TestCorsOriginReflection:
    """The browser's only defence against a hostile page reading the API."""

    @staticmethod
    def _configured_origin() -> str:
        """Read the first configured origin rather than hard-coding one.

        `CORS_ORIGINS` is deployment configuration; a test that hard-coded
        `http://localhost:3000` would start failing the day the default changed,
        for a reason that has nothing to do with CORS.
        """
        origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        assert origins, "no CORS origins configured -- nothing to assert"
        return origins[0]

    async def _get_health(self, origin: str) -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/health", headers={"Origin": origin})

    async def test_foreign_origin_gets_no_allow_origin_header(self):
        """No header at all — not the origin echoed, and not `*`."""
        response = await self._get_health("https://evil.example.com")

        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    async def test_configured_origin_is_allowed(self):
        """The positive control: the middleware is running and does allow someone.

        Without this, the assertion above would pass just as well if CORS were
        switched off entirely, or if the request never reached the middleware.
        """
        origin = self._configured_origin()
        response = await self._get_health(origin)

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def _invite(**overrides) -> InviteCode:
    """A redeemable invite, before the overrides that spoil it."""
    defaults = {
        "id": "invite-001",
        "code": "BETA-AAAABBBB",
        "max_uses": 1,
        "used_count": 0,
        "expires_at": datetime.now(UTC) + timedelta(days=30),
        "revoked_at": None,
    }
    defaults.update(overrides)
    return InviteCode(**defaults)


def _session_finding(invite: InviteCode | None) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = invite
    session.execute.return_value = result
    return session


# The four ways a code can fail. "Unknown" is the state an attacker is trying to
# distinguish from the rest: if a spent or expired code produced a different
# answer, the endpoint would confirm which guesses were real codes.
FAILING_CODES: dict[str, InviteCode | None] = {
    "unknown": None,
    "spent": _invite(max_uses=1, used_count=1),
    "expired": _invite(expires_at=datetime.now(UTC) - timedelta(days=1)),
    "revoked": _invite(revoked_at=datetime.now(UTC) - timedelta(days=1)),
}


@pytest.mark.asyncio
class TestInviteCodeEnumeration:
    """Unknown, spent, expired and revoked codes must be indistinguishable.

    THIS IS DELIBERATE. `redeem_invite` returns one message for every failure
    mode on purpose, and the temptation to "improve the error message" — "that
    code has already been used", "that invite expired on the 3rd" — is exactly
    what would reintroduce the oracle: each of those tells a stranger that the
    code they guessed is a real one, which turns brute-forcing the invite
    alphabet into a search with feedback.

    If a future change needs to distinguish these cases, distinguish them in the
    log (`invite_code_rejected` already records `found=`), never in the response.
    """

    @pytest.mark.parametrize("case", sorted(FAILING_CODES))
    async def test_every_failure_mode_raises_the_same_error(self, case):
        session = _session_finding(FAILING_CODES[case])
        with pytest.raises(InviteError) as excinfo:
            await invite_service.redeem_invite(session, "BETA-AAAABBBB")
        assert str(excinfo.value) == "That invite code is not valid"

    async def test_the_messages_are_identical_to_each_other(self):
        """Asserted as a set, so the four cases are compared rather than each
        being compared to a literal that a careless edit could update in one go."""
        messages = set()
        for invite in FAILING_CODES.values():
            with pytest.raises(InviteError) as excinfo:
                await invite_service.redeem_invite(_session_finding(invite), "BETA-AAAABBBB")
            messages.add(str(excinfo.value))
        assert len(messages) == 1, f"invite failures are distinguishable: {messages}"

    async def test_registration_responses_are_byte_identical(self, async_client, mock_session):
        """The oracle lives at the HTTP boundary, so assert it there too.

        Only three cases: `POST /api/auth/register` is rate-limited to 3/minute
        and a fourth request would measure the throttle rather than the message.
        Revoked is covered at service level above.
        """
        responses = []
        with patch.object(settings, "registration_mode", "invite"):
            for case in ("unknown", "spent", "expired"):
                mock_session.execute.return_value.scalar_one_or_none.return_value = FAILING_CODES[
                    case
                ]
                responses.append(
                    await async_client.post(
                        "/api/auth/register",
                        json={
                            "email": "attacker@example.com",
                            "username": "attacker",
                            "password": "<test-placeholder>Aa1!",
                            "invite_code": "BETA-AAAABBBB",
                        },
                    )
                )

        assert {r.status_code for r in responses} == {400}
        assert len({r.text for r in responses}) == 1, (
            f"register distinguishes invite failure modes: {[r.text for r in responses]}"
        )
