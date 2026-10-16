"""SEC-014: Telegram pairing codes are stored as SHA-256 digests, never in the clear."""

import re

import pytest
from sqlalchemy import text

from app.core.exceptions import TelegramLinkError
from app.services import telegram_service

pytestmark = pytest.mark.asyncio(loop_scope="session")

HEX64 = re.compile(r"^[0-9a-f]{64}$")


async def _stored(db_session, user_id):
    return (
        await db_session.execute(
            text("SELECT link_token, verified, chat_id FROM telegram_links WHERE user_id = :u"),
            {"u": user_id},
        )
    ).one()


class TestPairingCodeDigest:
    async def test_database_holds_a_digest_not_the_code(self, make_user, db_session):
        user = await make_user()
        code = await telegram_service.generate_link_token(db_session, user.id)
        stored = (await _stored(db_session, user.id)).link_token
        assert HEX64.match(stored)
        assert stored != code

    async def test_verifying_with_the_code_links_and_consumes(self, make_user, db_session):
        user = await make_user()
        code = await telegram_service.generate_link_token(db_session, user.id)
        assert await telegram_service.verify_link(db_session, code, 4242, "stu") is True
        row = await _stored(db_session, user.id)
        assert row.verified is True and row.chat_id == 4242 and row.link_token is None
        with pytest.raises(TelegramLinkError):
            await telegram_service.verify_link(db_session, code, 4242)

    async def test_verifying_with_the_stored_digest_fails(self, make_user, db_session):
        user = await make_user()
        await telegram_service.generate_link_token(db_session, user.id)
        digest = (await _stored(db_session, user.id)).link_token
        with pytest.raises(TelegramLinkError):
            await telegram_service.verify_link(db_session, digest, 4242)
        row = await _stored(db_session, user.id)
        assert row.verified is False and row.link_token == digest
