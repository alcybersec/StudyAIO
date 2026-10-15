"""GET /api/study/items: owner-scoped batch fetch of study items by id."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.user import User

NOW = datetime(2026, 10, 15, tzinfo=UTC)


def _card(**over):
    base = {
        "id": "f1", "course_id": "c-1", "week": 2, "front": "q", "back": "a", "tags": [],
        "source_artifact_id": "a-1", "source_page_ref": 3, "generation_version": 1,
        "created_at": NOW, "origin": "targeted", "focus_topic": "TLS",
    }  # fmt: skip
    base.update(over)
    return SimpleNamespace(**base)


def _quiz(**over):
    base = {
        "id": "q1", "course_id": "c-1", "week": 2, "question_type": "short_answer",
        "question": "why", "options_json": None, "correct_answer": "x", "explanation": "e",
        "source_artifact_id": "a-1", "source_page_ref": 3, "generation_version": 1,
        "created_at": NOW, "origin": "pipeline", "focus_topic": None,
    }  # fmt: skip
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
async def client_user(mock_session):
    from app.api.deps import get_current_user, get_current_user_or_default
    from app.core.database import get_session
    from app.main import app

    user = MagicMock(spec=User)
    user.id = "user-1"
    user.is_active = True

    async def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_or_default] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, user
    app.dependency_overrides.clear()


class TestStudyItems:
    async def test_returns_items_with_provenance_and_scopes_to_the_caller(self, client_user):
        client, user = client_user
        lookup = AsyncMock(return_value=([_card()], [_quiz()]))
        with patch("app.api.study.asset_service.get_items_by_ids", lookup):
            response = await client.get(
                "/api/study/items", params={"flashcard_ids": ["f1"], "quiz_question_ids": ["q1"]}
            )
        assert response.status_code == 200
        assert lookup.await_args.args[1:] == (["f1"], ["q1"])
        assert lookup.await_args.kwargs["user_id"] == user.id  # load-bearing
        body = response.json()
        assert body["flashcards"][0]["origin"] == "targeted"
        assert body["flashcards"][0]["focus_topic"] == "TLS"
        assert body["quiz_questions"][0]["origin"] == "pipeline"

    async def test_more_than_fifty_ids_is_422(self, client_user):
        client, _ = client_user
        lookup = AsyncMock()
        with patch("app.api.study.asset_service.get_items_by_ids", lookup):
            response = await client.get(
                "/api/study/items",
                params={"flashcard_ids": [f"f{i}" for i in range(30)]}
                | {"quiz_question_ids": [f"q{i}" for i in range(21)]},
            )
        assert response.status_code == 422
        lookup.assert_not_awaited()

    async def test_no_ids_is_an_empty_result(self, client_user):
        client, _ = client_user
        response = await client.get("/api/study/items")
        assert response.status_code == 200
        assert response.json() == {"flashcards": [], "quiz_questions": []}


class TestGetItemsByIds:
    async def test_queries_are_joined_to_the_owner_and_active_only(self, mock_session):
        from app.services import asset_service

        await asset_service.get_items_by_ids(mock_session, ["f1"], ["q1"], user_id="user-1")
        calls = mock_session.execute.await_args_list
        assert len(calls) == 2
        for call in calls:
            compiled = call.args[0].compile()
            assert "courses.user_id" in str(compiled)
            assert "user-1" in compiled.params.values()
            assert "archived_at IS NULL" in str(compiled)

    async def test_empty_lists_run_no_query(self, mock_session):
        from app.services import asset_service

        assert await asset_service.get_items_by_ids(mock_session, [], [], user_id="u") == ([], [])
        mock_session.execute.assert_not_awaited()
