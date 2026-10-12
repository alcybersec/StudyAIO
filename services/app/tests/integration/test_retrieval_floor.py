"""The relevance floor (GL#35) against real pgvector search.

The suite's default embeddings put every text close together, so seeded chunks
always clear the floor. Here the *query* embeds orthogonally to every stored
chunk (cosine similarity 0), which is exactly "nothing in my materials is
relevant": the reply is fixed, the agent is never called, and no AI usage is
metered.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.models.usage_record import UsageRecord

from ._support import FakeAgent, FixedEmbeddings, seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _OrthogonalQuery(FixedEmbeddings):
    """Queries land on an axis no stored chunk uses."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vec = [0.0] * 384
        vec[2] = 1.0
        return [list(vec) for _ in texts]


@pytest.fixture
def agent():
    fake = FakeAgent()
    with (
        patch("app.services.chat_service.get_agent", return_value=fake),
        patch("app.api.qa.get_agent", return_value=fake),
        patch("app.agents.factory.get_agent", return_value=fake),
    ):
        yield fake


@pytest.fixture
def orthogonal_query():
    provider = _OrthogonalQuery()
    targets = (
        "app.agents.embeddings.get_embedding_provider",
        "app.api.qa.get_embedding_provider",
        "app.services.chat_service.get_embedding_provider",
    )
    patches = [patch(t, return_value=provider) for t in targets]
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


async def _usage_rows(db_session, user_id) -> int:
    return await db_session.scalar(
        select(func.count()).select_from(UsageRecord).where(UsageRecord.user_id == user_id)
    )


class TestBelowFloor:
    async def test_qa_below_floor_is_fixed_reply_without_ai_call_or_usage(
        self, client_factory, make_user, db_session, agent, orthogonal_query
    ):
        user = await make_user()
        await seed_course(db_session, user.id, code="FLR101")

        resp = await client_factory(user).post(
            "/api/qa/ask", json={"question": "hello there", "course_code": "FLR101"}
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["answer"] == "I couldn't find this in your materials for FLR101."
        assert body["citations"] == []
        assert body["chunks_searched"] == 0
        assert agent.calls == []
        assert await _usage_rows(db_session, user.id) == 0

    async def test_unscoped_small_talk_is_also_below_floor(
        self, client_factory, make_user, db_session, agent, orthogonal_query
    ):
        user = await make_user()
        await seed_course(db_session, user.id, code="FLR101")

        resp = await client_factory(user).post("/api/qa/ask", json={"question": "thanks!"})

        assert resp.status_code == 200, resp.text
        assert resp.json()["answer"].startswith("I couldn't find this in your materials")
        assert agent.calls == []
        assert await _usage_rows(db_session, user.id) == 0

    async def test_chat_below_floor_is_fixed_reply_without_ai_call_or_usage(
        self, client_factory, make_user, db_session, agent, orthogonal_query
    ):
        user = await make_user()
        await seed_course(db_session, user.id, code="FLR101")
        client = client_factory(user)
        sid = (await client.post("/api/chat/sessions", json={"course_code": "FLR101"})).json()["id"]

        resp = await client.post(
            f"/api/chat/sessions/{sid}/messages", json={"content": "what's up"}
        )

        assert resp.status_code == 200, resp.text
        reply = resp.json()["assistant_message"]
        assert reply["content"].startswith("I couldn't find this in your materials")
        assert not reply.get("citations")
        assert agent.calls == []
        assert await _usage_rows(db_session, user.id) == 0

    async def test_other_tenants_chunks_never_lift_a_question_over_the_floor(
        self, client_factory, make_user, db_session, agent
    ):
        # Default embeddings: everything is similar. The asker owns no chunks,
        # so the fixed reply must still come back rather than a borrowed answer.
        owner, asker = await make_user(), await make_user()
        await seed_course(db_session, owner.id, code="FLR101")

        resp = await client_factory(asker).post("/api/qa/ask", json={"question": "tcp handshake"})

        assert resp.status_code == 200, resp.text
        assert resp.json()["citations"] == []
        assert agent.calls == []
        assert await _usage_rows(db_session, asker.id) == 0
