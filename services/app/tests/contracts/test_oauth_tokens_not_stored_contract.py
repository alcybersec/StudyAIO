"""Contract test for `models.secrets-at-rest v2` (docs/CONTRACTS.md, M34-S2-SEC-013).

OAuth sign-in stops storing the provider's tokens (``safety`` R1, user decision
2026-10-16). ``oauth_accounts.access_token`` and ``.refresh_token`` were written
at every sign-in and read by nothing. Pins:

1. ``create_or_link_oauth`` has no token parameters, and ``oauth_callback``
   passes none.
2. ``user_service`` assigns the two attributes only to ``None`` and never
   passes them to ``OAuthAccount(...)``; both write branches leave them
   ``None`` (**green today** when called without tokens: pins the behaviour).
3. Google's authorize URL no longer asks for ``access_type=offline``.
4. One revision after ``b2d4f6a8c0e1`` nulls both columns on every row, keeps
   every row and every other column, is idempotent, and its downgrade changes
   nothing and says the values "cannot be restored".
5. The columns stay (one release, ``deploy.sh``'s backward-compatibility rule):
   still mapped, still ``EncryptedText``, still nullable (**green today**).

Red until ``backend`` lands 1-3 and ``data`` lands 4.
"""

import ast
import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from tests.contracts import _revision_runner as rr
from tests.contracts._weakspot_docs import APP_ROOT, contract_section

HEADING = "### models.secrets-at-rest v2"
TOKEN_ATTRS = {"access_token", "refresh_token"}


def test_entry_is_v2_and_states_the_rules():
    flat = " ".join(contract_section(HEADING).split())
    assert "v2: OAuth sign-in tokens are not stored" in flat
    assert "cannot be restored" in flat
    assert "access_type=offline" in flat


# --- 1. no token reaches the service ------------------------------------------


def test_create_or_link_oauth_takes_no_tokens():
    from app.services.user_service import create_or_link_oauth

    params = list(inspect.signature(create_or_link_oauth).parameters)
    assert params == [
        "session",
        "provider",
        "provider_user_id",
        "email",
        "email_verified",
        "avatar_url",
    ], f"create_or_link_oauth parameters are {params} (`backend`, SEC-013 rule 1)"


def _calls(path, func_name: str) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and (getattr(n.func, "attr", None) or getattr(n.func, "id", None)) == func_name
    ]


def test_oauth_callback_passes_no_tokens():
    calls = _calls(APP_ROOT / "app" / "api" / "auth.py", "create_or_link_oauth")
    assert calls, "oauth_callback no longer calls create_or_link_oauth"
    passed = {k.arg for c in calls for k in c.keywords} & TOKEN_ATTRS
    assert not passed, f"oauth_callback still passes {sorted(passed)} (`backend`, rule 1)"


# --- 2. nothing writes them ---------------------------------------------------


def test_user_service_writes_the_tokens_only_as_none():
    path = APP_ROOT / "app" / "services" / "user_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                is_token = isinstance(target, ast.Attribute) and target.attr in TOKEN_ATTRS
                is_none = isinstance(node.value, ast.Constant) and node.value.value is None
                if is_token and not is_none:
                    bad.append(f"line {node.lineno}: {ast.unparse(node)}")
    for call in _calls(path, "OAuthAccount"):
        for k in call.keywords:
            if k.arg in TOKEN_ATTRS:
                bad.append(f"line {call.lineno}: OAuthAccount({k.arg}=...)")
    assert not bad, "user_service still stores provider tokens (`backend`, rule 2):\n" + "\n".join(
        bad
    )


def test_nothing_in_app_reads_the_oauth_tokens():
    """Only the rotation list in ``cli.py`` may name the two columns' table."""
    hits = []
    for path in sorted((APP_ROOT / "app").rglob("*.py")):
        rel = path.relative_to(APP_ROOT).as_posix()
        if rel in {"app/cli.py", "app/models/oauth_account.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "OAuthAccount" not in text and "oauth_accounts" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if (
                isinstance(node, ast.Attribute)
                and node.attr in TOKEN_ATTRS
                and isinstance(node.ctx, ast.Load)
                and "oauth" in ast.unparse(node.value).lower()
            ):
                hits.append(f"{rel}:{node.lineno}: {ast.unparse(node)}")
    assert not hits, "OAuth tokens are read (rule 2):\n" + "\n".join(hits)


async def test_known_identity_sign_in_clears_stored_tokens(mock_session):
    from app.services import user_service

    existing = MagicMock(user_id="u1", access_token="gho_old", refresh_token="1//old")
    mock_session.execute.return_value.scalar_one_or_none.return_value = existing
    user = MagicMock(avatar_url="x")
    with patch.object(user_service, "get_user_by_id", AsyncMock(return_value=user)):
        await user_service.create_or_link_oauth(
            mock_session, provider="github", provider_user_id="42", email="a@example.com"
        )
    assert existing.access_token is None and existing.refresh_token is None


async def test_new_link_stores_no_tokens(mock_session):
    from app.models.oauth_account import OAuthAccount
    from app.services import user_service

    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    user = MagicMock(id="u1", hashed_password=None, avatar_url="x")
    with patch.object(user_service, "get_user_by_email", AsyncMock(return_value=user)):
        await user_service.create_or_link_oauth(
            mock_session,
            provider="google",
            provider_user_id="g-1",
            email="a@example.com",
            email_verified=True,
        )
    added = [c.args[0] for c in mock_session.add.call_args_list]
    links = [a for a in added if isinstance(a, OAuthAccount)]
    assert len(links) == 1
    assert links[0].access_token is None and links[0].refresh_token is None


# --- 3. do not ask Google for a refresh token -------------------------------------


def test_google_authorize_url_does_not_request_offline_access():
    from app.core import oauth

    config = {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "client_id": "cid",
        "scope": "openid email profile",
    }
    with patch.object(oauth, "get_provider_config", return_value=config):
        url = oauth.build_authorize_url("google", "state-1")
    query = parse_qs(urlparse(url).query)
    assert "access_type" not in query, "Google is still asked for offline access (rule 3)"
    assert query.get("prompt") == ["select_account"]
    assert query.get("scope") == ["openid email profile"]


# --- 4. the revision --------------------------------------------------------------


def _seed(conn):
    conn.execute(
        rr.OAUTH_ACCOUNTS.insert(),
        [
            {
                "id": "a",
                "user_id": "u1",
                "provider": "github",
                "provider_user_id": "1",
                "access_token": "enc:v1:abc",
                "refresh_token": None,
            },
            {
                "id": "b",
                "user_id": "u2",
                "provider": "google",
                "provider_user_id": "2",
                "access_token": "ya29.legacy-plaintext",
                "refresh_token": "1//refresh",
            },
            {
                "id": "c",
                "user_id": "u3",
                "provider": "google",
                "provider_user_id": "3",
                "access_token": None,
                "refresh_token": None,
            },
        ],
    )


IDENTITY = [
    ("a", "u1", "github", "1"),
    ("b", "u2", "google", "2"),
    ("c", "u3", "google", "3"),
]


@pytest.fixture(scope="module")
def revision():
    return rr.find_revision("oauth_accounts", "data")


def _identity(found):
    return [(r["id"], r["user_id"], r["provider"], r["provider_user_id"]) for r in found]


def test_upgrade_nulls_both_tokens_and_keeps_every_link(revision):
    engine = rr.scratch_engine(_seed)
    rr.run(engine, revision, "upgrade")
    found = rr.rows(engine, rr.OAUTH_ACCOUNTS)
    assert _identity(found) == IDENTITY, "upgrade deleted or altered an identity link"
    assert all(r["access_token"] is None and r["refresh_token"] is None for r in found)
    rr.run(engine, revision, "upgrade")
    assert rr.rows(engine, rr.OAUTH_ACCOUNTS) == found, "a second upgrade changed something"


def test_downgrade_changes_nothing_and_says_so(revision):
    engine = rr.scratch_engine(_seed)
    rr.run(engine, revision, "upgrade")
    before = rr.rows(engine, rr.OAUTH_ACCOUNTS)
    rr.run(engine, revision, "downgrade")
    assert rr.rows(engine, rr.OAUTH_ACCOUNTS) == before
    doc = " ".join((revision.__doc__ or "").split()).lower()
    assert "cannot be restored" in doc, "the revision docstring must say so (rule 5)"


# --- 5. the columns stay for one release (green today) ------------------------------


def test_columns_stay_mapped_encrypted_and_nullable():
    from app.core.secret_box import EncryptedText
    from app.models.oauth_account import OAuthAccount

    table = OAuthAccount.__table__
    for name in TOKEN_ATTRS:
        col = table.c[name]
        assert isinstance(col.type, EncryptedText), f"oauth_accounts.{name} is not EncryptedText"
        assert col.nullable, f"oauth_accounts.{name} must stay nullable"
