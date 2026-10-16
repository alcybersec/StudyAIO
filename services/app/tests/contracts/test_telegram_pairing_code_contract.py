"""Contract test for `models.telegram-pairing-code v1` (docs/CONTRACTS.md, M34-S2-SEC-014).

Telegram pairing codes are stored as SHA-256 digests (``safety`` R3, user
decision 2026-10-16), as magic-link and invite tokens already are. Pins:

1. ``generate_link_token`` returns the plaintext code and stores only
   ``hash_magic_link_token(code)`` (64 lowercase hex), for a new and an
   existing link.
2. ``verify_link`` looks the row up by the digest of the presented code, in
   SQL; the plaintext never appears in the statement; a hit consumes the code.
3. A miss raises ``TelegramLinkError("Invalid or expired link token")``
   (**green today**).
4. No log line carries the code or its digest, on success, on a miss or
   through the webhook handler (**green today** for the plaintext).
5. One revision after ``b2d4f6a8c0e1`` nulls every unused code on upgrade and
   on downgrade, keeps every row and every linked chat, and is idempotent.
6. The column keeps its name and ``String(64)`` (**green today**).

Red until ``backend`` lands 1-2 and ``data`` lands 5.
"""

import hashlib
from unittest.mock import MagicMock

import pytest
from structlog.testing import capture_logs

from tests.contracts import _revision_runner as rr
from tests.contracts._weakspot_docs import contract_section

HEADING = "### models.telegram-pairing-code v1"
CODE = "pairing-code-contract-0123456789abcdefghijklm"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_entry_names_the_hash_and_the_invalidation():
    flat = " ".join(contract_section(HEADING).split())
    assert "hash_magic_link_token(code)" in flat
    assert 'TelegramLinkError("Invalid or expired link token")' in flat
    assert "Why invalidate rather than hash in place" in flat


def test_the_shared_hash_is_hex_sha256():
    from app.core.auth import hash_magic_link_token

    assert hash_magic_link_token(CODE) == _digest(CODE)


# --- 1. generate stores the digest ----------------------------------------------


@pytest.mark.parametrize("existing", [False, True], ids=["new-link", "existing-link"])
async def test_generate_stores_only_the_digest(mock_session, existing):
    from app.models.telegram_link import TelegramLink
    from app.services import telegram_service

    row = TelegramLink(id="l1", user_id="u1", link_token="old", verified=True) if existing else None
    mock_session.execute.return_value.scalar_one_or_none.return_value = row
    with capture_logs() as logs:
        code = await telegram_service.generate_link_token(mock_session, "u1")

    if existing:
        stored = row.link_token
    else:
        added = [c.args[0] for c in mock_session.add.call_args_list]
        assert len(added) == 1 and isinstance(added[0], TelegramLink)
        stored = added[0].link_token
    assert isinstance(code, str) and len(code) >= 43
    assert stored != code, "the plaintext pairing code is stored (`backend`, rule 1)"
    assert stored == _digest(code), "the stored value is not hash_magic_link_token(code)"
    dumped = repr(logs)
    assert code not in dumped and stored not in dumped, "the code or its digest is logged"


# --- 2/3. verify looks up by digest -------------------------------------------------


def _compiled(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


async def test_verify_looks_up_by_digest_and_consumes(mock_session):
    from app.services import telegram_service

    link = MagicMock(user_id="u1", link_token=_digest(CODE))
    mock_session.execute.return_value.scalar_one_or_none.return_value = link
    with capture_logs() as logs:
        assert await telegram_service.verify_link(mock_session, CODE, 4242, "someone") is True

    sql = _compiled(mock_session.execute.await_args.args[0])
    assert _digest(CODE) in sql, "verify_link does not look the code up by its digest (rule 2)"
    assert CODE not in sql, "verify_link compares the plaintext code (rule 2)"
    assert link.link_token is None and link.verified is True and link.chat_id == 4242
    dumped = repr(logs)
    assert CODE not in dumped and _digest(CODE) not in dumped


async def test_presenting_the_stored_digest_is_looked_up_as_its_own_digest(mock_session):
    """A database reader who sends the digest as the code must not match it."""
    from app.core.exceptions import TelegramLinkError
    from app.services import telegram_service

    stored = _digest(CODE)
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    with pytest.raises(TelegramLinkError):
        await telegram_service.verify_link(mock_session, stored, 1)
    sql = _compiled(mock_session.execute.await_args.args[0])
    assert _digest(stored) in sql, "the presented value is compared without hashing (rule 2)"


async def test_miss_raises_the_existing_error_and_logs_nothing_secret(mock_session):
    from app.core.exceptions import TelegramLinkError
    from app.services import telegram_service

    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    with capture_logs() as logs, pytest.raises(TelegramLinkError) as err:
        await telegram_service.verify_link(mock_session, CODE, 1)
    assert str(err.value) == "Invalid or expired link token"
    assert CODE not in repr(logs) and _digest(CODE) not in repr(logs)


async def test_webhook_never_logs_the_start_text(mock_session):
    from app.services import telegram_service

    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    update = {"message": {"text": f"/start {CODE}", "chat": {"id": 7}, "from": {}}}
    with capture_logs() as logs:
        reply = await telegram_service.handle_telegram_webhook(mock_session, update)
    assert "Invalid or expired" in reply
    assert CODE not in repr(logs) and _digest(CODE) not in repr(logs)


# --- 5. the revision ----------------------------------------------------------------


def _row(id_, user_id, **values):
    base = {"chat_id": None, "username": None, "link_token": None}
    return {"id": id_, "user_id": user_id, **base, **values}


def _seed(conn):
    conn.execute(
        rr.TELEGRAM_LINKS.insert(),
        [
            # pending, issued by the old code: plaintext
            _row("a", "u1", verified=False, link_token="x" * 43),
            # linked: the code was consumed
            _row("b", "u2", verified=True, chat_id=42, username="bob"),
            # a digest (e.g. written by the new code before a downgrade)
            _row("c", "u3", verified=False, link_token=_digest(CODE)),
        ],
    )


LINKED = [("a", "u1", False, None), ("b", "u2", True, 42), ("c", "u3", False, None)]


@pytest.fixture(scope="module")
def revision():
    return rr.find_revision("telegram_links", "data")


def _shape(found):
    return [(r["id"], r["user_id"], r["verified"], r["chat_id"]) for r in found]


@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_revision_invalidates_every_unused_code(revision, direction):
    engine = rr.scratch_engine(_seed)
    rr.run(engine, revision, direction)
    found = rr.rows(engine, rr.TELEGRAM_LINKS)
    assert _shape(found) == LINKED, f"{direction} deleted a row or unlinked a chat"
    assert [r["username"] for r in found] == [None, "bob", None]
    assert all(r["link_token"] is None for r in found), f"{direction} left a usable code"
    rr.run(engine, revision, direction)
    assert rr.rows(engine, rr.TELEGRAM_LINKS) == found, f"a second {direction} changed something"


# --- 6. the column (green today) ----------------------------------------------------


def test_column_keeps_its_name_and_width():
    import sqlalchemy as sa

    from app.models.telegram_link import TelegramLink

    col = TelegramLink.__table__.c["link_token"]
    assert isinstance(col.type, sa.String) and col.type.length == 64
    assert col.nullable and col.unique
