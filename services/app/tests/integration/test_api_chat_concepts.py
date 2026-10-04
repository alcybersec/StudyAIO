"""Chat sessions (RAG over real pgvector chunks) and the knowledge graph.

The agent is the only fake. Retrieval runs real vector search against rows the
test seeded, so a chat answer built from another user's chunks would show up in
the agent's recorded context.
"""

import json
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.concept import Concept
from app.models.usage_record import UsageRecord

from ._support import FakeAgent, seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
def agent():
    fake = FakeAgent()
    with (
        patch("app.services.chat_service.get_agent", return_value=fake),
        patch("app.agents.factory.get_agent", return_value=fake),
    ):
        yield fake


class TestChatSessions:
    async def test_session_lifecycle_and_ownership(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        await seed_course(db_session, owner.id, code="CHT101")
        client = client_factory(owner)

        created = await client.post(
            "/api/chat/sessions", json={"title": "Exam prep", "course_code": "CHT101"}
        )
        assert created.status_code == 201
        sid = created.json()["id"]
        assert created.json()["course_id"] is not None

        listed = (await client.get("/api/chat/sessions")).json()["sessions"]
        assert [s["id"] for s in listed] == [sid]
        assert (await client_factory(stranger).get("/api/chat/sessions")).json()["sessions"] == []
        assert (
            await client_factory(stranger).get(f"/api/chat/sessions/{sid}/messages")
        ).status_code == 404
        assert (
            await client_factory(stranger).delete(f"/api/chat/sessions/{sid}")
        ).status_code == 404
        # Scoping a session to someone else's course code is a 404, not a silent link.
        assert (
            await client_factory(stranger).post(
                "/api/chat/sessions", json={"course_code": "CHT101"}
            )
        ).status_code == 404

        assert (await client.delete(f"/api/chat/sessions/{sid}")).status_code == 204
        assert (
            await db_session.execute(select(ChatSession).where(ChatSession.id == sid))
        ).first() is None

    async def test_send_message_stores_both_turns_with_rag_and_meters_usage(
        self, client_factory, make_user, db_session, agent
    ):
        alice, bob = await make_user(), await make_user()
        a = await seed_course(db_session, alice.id, code="CHT101")
        await seed_course(db_session, bob.id, code="CHT202")
        client = client_factory(alice)
        sid = (await client.post("/api/chat/sessions", json={"course_code": "CHT101"})).json()["id"]

        resp = await client.post(
            f"/api/chat/sessions/{sid}/messages", json={"content": "Explain the TCP handshake"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user_message"]["role"] == "user"
        assert body["assistant_message"]["content"].startswith("Stub answer")

        # Retrieval handed the agent only Alice's chunks.
        assert dict(agent.calls)["answer"]["chunks"] == len(a.chunks)

        stored = (
            (await db_session.execute(select(ChatMessage).where(ChatMessage.session_id == sid)))
            .scalars()
            .all()
        )
        assert sorted(m.role for m in stored) == ["assistant", "user"]
        chat = await db_session.get(ChatSession, sid)
        assert chat.message_count == 2
        assert chat.title.startswith("Explain the TCP")  # auto-titled from first message
        usage = (
            await db_session.execute(select(UsageRecord).where(UsageRecord.user_id == alice.id))
        ).scalar_one()
        assert usage.ai_calls_count == 1

        history = (await client.get(f"/api/chat/sessions/{sid}/messages")).json()["messages"]
        assert [m["role"] for m in history] == ["user", "assistant"]
        page = (
            await client.get(f"/api/chat/sessions/{sid}/messages", params={"limit": 1, "offset": 1})
        ).json()["messages"]
        assert len(page) == 1

    async def test_send_message_to_foreign_or_unknown_session_is_404(
        self, client_factory, make_user, agent
    ):
        owner, stranger = await make_user(), await make_user()
        sid = (await client_factory(owner).post("/api/chat/sessions", json={})).json()["id"]
        for who, target in ((stranger, sid), (owner, "nope")):
            resp = await client_factory(who).post(
                f"/api/chat/sessions/{target}/messages", json={"content": "hi"}
            )
            assert resp.status_code == 404
        assert agent.calls == []  # no AI spend on a rejected request

    async def test_agent_failure_becomes_apology_not_500(
        self, client_factory, make_user, db_session
    ):
        class Broken(FakeAgent):
            async def answer_question(self, question, context_chunks):
                raise RuntimeError("provider down")

        user = await make_user()
        client = client_factory(user)
        sid = (await client.post("/api/chat/sessions", json={})).json()["id"]
        with patch("app.services.chat_service.get_agent", return_value=Broken()):
            resp = await client.post(f"/api/chat/sessions/{sid}/messages", json={"content": "q"})
        assert resp.status_code == 200
        assert "encountered an error" in resp.json()["assistant_message"]["content"]

    async def test_message_scope_and_validation(self, client_factory, make_user, db_session, agent):
        user = await make_user()
        await seed_course(db_session, user.id, code="CHT101")
        client = client_factory(user)
        sid = (await client.post("/api/chat/sessions", json={})).json()["id"]
        ok = await client.post(
            f"/api/chat/sessions/{sid}/messages",
            json={"content": "scoped", "course_code": "CHT101", "week": 3},
        )
        assert ok.status_code == 200
        assert (
            await client.post(
                f"/api/chat/sessions/{sid}/messages", json={"content": "x", "course_code": "NOPE"}
            )
        ).status_code == 404
        assert (
            await client.post(f"/api/chat/sessions/{sid}/messages", json={"content": ""})
        ).status_code == 422

    async def test_streaming_emits_tokens_then_done_and_persists(
        self, client_factory, make_user, db_session, agent
    ):
        user = await make_user()
        await seed_course(db_session, user.id, code="CHT101")
        client = client_factory(user)
        sid = (await client.post("/api/chat/sessions", json={"course_code": "CHT101"})).json()["id"]

        resp = await client.post(
            f"/api/chat/sessions/{sid}/messages/stream", json={"content": "stream please"}
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = [
            line.removeprefix("event:").strip()
            for line in resp.text.splitlines()
            if line.startswith("event:")
        ]
        assert events[0] == "user_message" and events[-1] == "done"
        assert "token" in events
        done_data = [
            line.removeprefix("data:").strip()
            for line in resp.text.splitlines()
            if line.startswith("data:")
        ][-1]
        assert json.loads(done_data)["content"].startswith("Stub answer")
        stored = (
            (await db_session.execute(select(ChatMessage).where(ChatMessage.session_id == sid)))
            .scalars()
            .all()
        )
        assert len(stored) == 2

    async def test_streaming_unknown_session_reports_error_event(
        self, client_factory, make_user, agent
    ):
        resp = await client_factory(await make_user()).post(
            "/api/chat/sessions/nope/messages/stream", json={"content": "hi"}
        )
        assert "event: error" in resp.text and "Chat session not found" in resp.text


class TestConcepts:
    async def _extract(self, client, artifact_id):
        return await client.post(f"/api/concepts/extract/{artifact_id}")

    async def test_extract_graph_detail_related_and_filters(
        self, client_factory, make_user, db_session, agent
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id, code="KG101")
        client = client_factory(user)

        resp = await self._extract(client, seeded.artifact.id)
        assert resp.status_code == 201, resp.text
        assert resp.json() == {
            "artifact_id": seeded.artifact.id,
            "concept_count": 2,
            "relation_count": 1,
        }
        # Extracting again upserts rather than duplicating.
        again = await self._extract(client, seeded.artifact.id)
        assert again.json()["concept_count"] == 2 and again.json()["relation_count"] == 0
        stored = (
            (await db_session.execute(select(Concept).where(Concept.user_id == user.id)))
            .scalars()
            .all()
        )
        assert sorted(c.name for c in stored) == ["TCP", "UDP"]
        assert all(c.mention_count == 2 and c.embedding is not None for c in stored)

        graph = (await client.get("/api/concepts/graph")).json()
        assert len(graph["nodes"]) == 2 and len(graph["edges"]) == 1
        scoped = (await client.get("/api/concepts/graph", params={"course_code": "KG101"})).json()
        assert len(scoped["nodes"]) == 2

        listed = (await client.get("/api/concepts", params={"search": "reliable"})).json()
        assert [c["name"] for c in listed] == ["TCP"]
        tcp_id = listed[0]["id"]

        detail = (await client.get(f"/api/concepts/{tcp_id}")).json()
        assert detail["name"] == "TCP"
        assert [r["concept_name"] for r in detail["outgoing_relations"]] == ["UDP"]
        related = await client.get(f"/api/concepts/{tcp_id}/related")
        assert related.status_code == 200
        assert "UDP" in {r["name"] for r in related.json()}

    async def test_concepts_are_owner_scoped(self, client_factory, make_user, db_session, agent):
        owner, stranger = await make_user(), await make_user()
        seeded = await seed_course(db_session, owner.id, code="KG101")
        await self._extract(client_factory(owner), seeded.artifact.id)
        concept_id = (await client_factory(owner).get("/api/concepts")).json()[0]["id"]

        other = client_factory(stranger)
        assert (await other.get("/api/concepts")).json() == []
        assert (await other.get(f"/api/concepts/{concept_id}")).status_code == 404
        assert (await other.get(f"/api/concepts/{concept_id}/related")).json() == []
        assert (await other.get("/api/concepts/graph")).json() == {"nodes": [], "edges": []}
        assert (await self._extract(other, seeded.artifact.id)).status_code == 404
        assert (
            await other.get("/api/concepts", params={"course_code": "KG101"})
        ).status_code == 404

    async def test_extract_refuses_unprocessed_artifacts(
        self, client_factory, make_user, db_session, agent
    ):
        user = await make_user()
        seeded = await seed_course(db_session, user.id, code="KG101")
        client = client_factory(user)
        seeded.artifact.week = None
        await db_session.flush()
        assert (await self._extract(client, seeded.artifact.id)).status_code == 400
        assert (await self._extract(client, "nope")).status_code == 404
        assert agent.calls == []
