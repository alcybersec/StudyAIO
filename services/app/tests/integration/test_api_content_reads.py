"""Read paths over seeded study content: courses, summaries, assets, search, exports, Q&A, settings.

Every route here is hit by two users holding the same course code, so a
response that is not scoped to the caller shows up as the wrong user's content.
"""

import io
import zipfile
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.usage_record import UsageRecord
from app.models.user_settings import UserSettings

from ._support import FakeAgent, seed_course

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestSummariesAndAssets:
    async def test_summary_by_id_is_owner_scoped(self, client_factory, two_tenants):
        alice, bob, a, b = two_tenants
        ok = await client_factory(alice).get(f"/api/summaries/{a.summary.id}")
        assert ok.status_code == 200
        assert ok.json()["content_md"].startswith("# ALICE-ONLY")
        assert ok.json()["version"] == 1
        cross = await client_factory(alice).get(f"/api/summaries/{b.summary.id}")
        assert cross.status_code == 404
        assert "BOB-ONLY" not in cross.text

    async def test_flashcards_and_quiz_return_only_callers_rows(self, client_factory, two_tenants):
        alice, bob, a, b = two_tenants
        client = client_factory(alice)
        cards = (
            await client.get("/api/assets/flashcards", params={"course_code": "NET101"})
        ).json()
        assert len(cards) == 2 and "BOB card" not in {c["front"] for c in cards}
        week = (
            await client.get("/api/assets/flashcards", params={"course_code": "NET101", "week": 3})
        ).json()
        assert len(week) == 2
        none = (
            await client.get("/api/assets/flashcards", params={"course_code": "NET101", "week": 9})
        ).json()
        assert none == []
        quiz = (await client.get("/api/assets/quiz", params={"course_code": "NET101"})).json()
        assert len(quiz) == 2
        quiz_week = (
            await client.get("/api/assets/quiz", params={"course_code": "NET101", "week": 3})
        ).json()
        assert {q["question_type"] for q in quiz_week} == {"multiple_choice", "short_answer"}
        bob_cards = (
            await client_factory(bob).get(
                "/api/assets/flashcards", params={"course_code": "NET101"}
            )
        ).json()
        assert [c["front"] for c in bob_cards] == ["BOB card"]


class TestSearch:
    async def test_global_search_finds_own_content_only(self, client_factory, two_tenants):
        alice, bob, a, b = two_tenants
        resp = await client_factory(alice).get("/api/search", params={"q": "sockets"})
        assert resp.status_code == 200
        text = resp.text
        assert "ALICE-ONLY" in text and "BOB-ONLY" not in text
        kinds = {r["kind"] for r in resp.json()["results"]}
        assert "course_week" in kinds

        by_course = (await client_factory(alice).get("/api/search", params={"q": "NET1"})).json()
        assert any(r["kind"] == "course" for r in by_course["results"])
        card = (await client_factory(bob).get("/api/search", params={"q": "BOB card"})).json()
        assert any(r["kind"] == "flashcard" for r in card["results"])
        cross = (await client_factory(alice).get("/api/search", params={"q": "BOB card"})).json()
        assert cross["results"] == []

    async def test_search_validation_and_wildcards_are_literal(self, client_factory, two_tenants):
        alice = two_tenants[0]
        client = client_factory(alice)
        assert (await client.get("/api/search", params={"q": "   "})).status_code == 400
        assert (await client.get("/api/search", params={"q": "x", "limit": 0})).status_code == 422
        pct = await client.get("/api/search", params={"q": "%"})
        assert pct.json()["results"] == []  # '%' matches literally, not everything


class TestExport:
    async def test_obsidian_export_contains_only_owners_content(self, client_factory, two_tenants):
        alice, bob, a, b = two_tenants
        resp = await client_factory(alice).get("/api/exports/obsidian/NET101")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/zip")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            names = zf.namelist()
            blob = "\n".join(zf.read(n).decode("utf-8", "ignore") for n in names)
        assert any(n.endswith("Week03.md") for n in names)
        assert "ALICE-ONLY" in blob and "BOB-ONLY" not in blob
        assert "ALICE card" in blob and "BOB card" not in blob

    async def test_export_week_filter_and_errors(self, client_factory, two_tenants):
        alice = two_tenants[0]
        client = client_factory(alice)
        assert (
            await client.get("/api/exports/obsidian/NET101", params={"weeks": "3"})
        ).status_code == 200
        assert (
            await client.get("/api/exports/obsidian/NET101", params={"weeks": "a,b"})
        ).status_code == 400
        assert (await client.get("/api/exports/obsidian/NOPE")).status_code == 404


class TestQA:
    async def test_answer_uses_only_callers_chunks_and_meters_usage(
        self, client_factory, make_user, db_session
    ):
        alice, bob = await make_user(), await make_user()
        a = await seed_course(db_session, alice.id, code="NET101")
        await seed_course(db_session, bob.id, code="NET202")  # same text, other owner
        agent = FakeAgent()
        with patch("app.api.qa.get_agent", return_value=agent):
            resp = await client_factory(alice).post(
                "/api/qa/ask", json={"question": "How does TCP connect?", "course_code": "NET101"}
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["answer"].startswith("Stub answer")
        assert body["chunks_searched"] == len(a.chunks)  # not Alice + Bob
        usage = (
            await db_session.execute(select(UsageRecord).where(UsageRecord.user_id == alice.id))
        ).scalar_one()
        assert usage.ai_calls_count == 1
        assert dict(agent.calls)["answer"]["chunks"] == len(a.chunks)

    async def test_no_content_returns_helpful_empty_answer(self, client_factory, make_user):
        empty = await make_user()
        with patch("app.api.qa.get_agent") as get_agent:
            resp = await client_factory(empty).post("/api/qa/ask", json={"question": "anything?"})
        assert resp.status_code == 200
        assert resp.json()["chunks_searched"] == 0 and resp.json()["citations"] == []
        get_agent.assert_not_called()  # nothing to answer from, so no AI spend

    async def test_unknown_course_is_404(self, client_factory, make_user):
        user = await make_user()
        resp = await client_factory(user).post(
            "/api/qa/ask", json={"question": "q", "course_code": "NOPE999"}
        )
        assert resp.status_code == 404

    async def test_agent_failure_is_reported_not_swallowed(self, client_factory, two_tenants):
        alice = two_tenants[0]

        class Broken(FakeAgent):
            async def answer_question(self, question, context_chunks):
                raise RuntimeError("provider down")

        with patch("app.api.qa.get_agent", return_value=Broken()):
            resp = await client_factory(alice).post("/api/qa/ask", json={"question": "q"})
        assert resp.status_code == 500

    async def test_shared_course_code_between_users_still_answers(
        self, client_factory, two_tenants
    ):
        alice = two_tenants[0]
        with patch("app.api.qa.get_agent", return_value=FakeAgent()):
            resp = await client_factory(alice).post(
                "/api/qa/ask", json={"question": "sockets?", "course_code": "NET101"}
            )
        assert resp.status_code == 200

    async def test_course_code_of_another_user_is_404(self, client_factory, make_user, db_session):
        owner, stranger = await make_user(), await make_user()
        await seed_course(db_session, owner.id, code="PRIVATE77")
        resp = await client_factory(stranger).post(
            "/api/qa/ask", json={"question": "q", "course_code": "PRIVATE77"}
        )
        assert resp.status_code == 404


class TestSettings:
    async def test_defaults_then_update_roundtrip(self, client_factory, make_user, db_session):
        user = await make_user()
        client = client_factory(user)
        initial = (await client.get("/api/settings")).json()
        assert initial["agent_backend"] == "studyaio"
        assert initial["openai_api_key_configured"] is False

        resp = await client.put(
            "/api/settings",
            json={
                "flashcard_count_per_week": 7,
                "theme": "dark",
                "language": "ru",
                "classification_confidence_threshold": 0.5,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["flashcard_count_per_week"] == 7
        assert body["theme"] == "dark" and body["language"] == "ru"
        again = (await client.get("/api/settings")).json()
        assert again["flashcard_count_per_week"] == 7
        assert again["classification_confidence_threshold"] == 0.5

    async def test_secrets_are_write_only_and_clearable(
        self, client_factory, make_user, db_session
    ):
        user = await make_user()
        client = client_factory(user)
        secret = "sk-test-SUPER-SECRET-VALUE"
        put = await client.put("/api/settings", json={"openai_api_key": secret})
        assert put.status_code == 200
        assert put.json()["openai_api_key_configured"] is True
        assert secret not in put.text
        assert secret not in (await client.get("/api/settings")).text

        # Stored for the owner (the agent factory needs it) but never returned.
        row = (
            await db_session.execute(select(UserSettings).where(UserSettings.user_id == user.id))
        ).scalar_one()
        assert row.settings_json["openai_api_key"] == secret

        # An empty value leaves it unchanged; clear_secrets removes it.
        await client.put("/api/settings", json={"openai_api_key": "", "theme": "light"})
        assert (await client.get("/api/settings")).json()["openai_api_key_configured"] is True
        await client.put("/api/settings", json={"clear_secrets": ["openai_api_key"]})
        assert (await client.get("/api/settings")).json()["openai_api_key_configured"] is False

    async def test_settings_are_per_user(self, client_factory, make_user):
        a, b = await make_user(), await make_user()
        await client_factory(a).put(
            "/api/settings",
            json={"anthropic_api_key": "sk-ant-ALICE", "quiz_question_count_per_week": 9},
        )
        other = (await client_factory(b).get("/api/settings")).json()
        assert other["anthropic_api_key_configured"] is False
        assert other["quiz_question_count_per_week"] != 9

    async def test_validation_errors(self, client_factory, make_user):
        client = client_factory(await make_user())
        assert (await client.put("/api/settings", json={})).status_code == 400
        for bad in (
            {"agent_backend": "skynet"},
            {"claude_model": "gpt"},
            {"flashcard_count_per_week": 0},
            {"classification_confidence_threshold": 2},
            {"claude_cli_credentials": "not json"},
            {"theme": "neon"},
            {"language": "xx"},
        ):
            resp = await client.put("/api/settings", json=bad)
            assert resp.status_code == 422, (bad, resp.text)

    async def test_test_ai_connection(self, client_factory, make_user):
        client = client_factory(await make_user())
        with patch("app.agents.factory.get_agent", return_value=FakeAgent()):
            ok = await client.post("/api/settings/test-ai")
        assert ok.status_code == 200 and ok.json()["status"] == "ok"

        class Broken(FakeAgent):
            async def classify_lecture(self, *a, **k):
                raise RuntimeError("bad key sk-LEAKME")

        with patch("app.agents.factory.get_agent", return_value=Broken()):
            bad = await client.post("/api/settings/test-ai")
        assert bad.status_code == 502
        assert bad.json()["detail"]

    async def test_test_ai_failure_does_not_echo_provider_error_text(
        self, client_factory, make_user
    ):
        # The scrub can only remove values it knows: the caller's stored credential
        # (and the instance's). A provider that echoes the key it was sent must not
        # get it back out through the response.
        stored = "sk-LEAKME-0123456789"

        class Broken(FakeAgent):
            async def classify_lecture(self, *a, **k):
                raise RuntimeError(f"Incorrect API key provided: {stored}")

        client = client_factory(await make_user())
        put = await client.put(
            "/api/settings", json={"agent_backend": "openai", "openai_api_key": stored}
        )
        assert put.status_code == 200, put.text
        with patch("app.agents.factory.get_agent", return_value=Broken()):
            bad = await client.post("/api/settings/test-ai")
        assert bad.status_code == 502
        assert stored not in bad.text
        assert "[redacted]" in bad.json()["detail"]
