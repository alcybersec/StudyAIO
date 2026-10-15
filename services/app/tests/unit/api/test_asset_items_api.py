"""API tests for flashcard / quiz item create, edit, delete (GL#48)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.asset_service import ItemNotFoundError, NoSourceArtifactError


def _card(**kw):
    fc = MagicMock()
    fc.id = kw.get("id", "fc-new")
    fc.course_id = "c-1"
    fc.week = 3
    fc.front = "f"
    fc.back = "b"
    fc.tags = []
    fc.source_artifact_id = "a-1"
    fc.source_page_ref = 0
    fc.generation_version = 1
    fc.origin = "user"
    fc.focus_topic = None
    fc.created_at = datetime(2026, 1, 1)
    return fc


def _quiz(**kw):
    q = MagicMock()
    q.id = kw.get("id", "q-new")
    q.course_id = "c-1"
    q.week = 3
    q.question_type = "multiple_choice"
    q.question = "q?"
    q.options_json = ["A. x", "B. y"]
    q.correct_answer = "A"
    q.explanation = ""
    q.source_artifact_id = "a-1"
    q.source_page_ref = 0
    q.generation_version = 1
    q.origin = "user"
    q.focus_topic = None
    q.created_at = datetime(2026, 1, 1)
    return q


SVC = "app.api.assets.asset_service"
FC_BODY = {"course_code": "CSIT302", "week": 3, "front": " Q ", "back": "A"}
QZ_BODY = {
    "course_code": "CSIT302",
    "week": 3,
    "question_type": "multiple_choice",
    "question": "What?",
    "options": ["A. x", "B. y"],
    "correct_answer": "B",
}


@pytest.mark.asyncio
class TestFlashcardItems:
    async def test_create_returns_201_and_scopes_to_caller(self, async_client, default_test_user):
        with patch(f"{SVC}.create_flashcard", new_callable=AsyncMock, return_value=_card()) as m:
            r = await async_client.post("/api/assets/flashcards", json=FC_BODY)
        assert r.status_code == 201
        assert r.json()["origin"] == "user"
        assert m.await_args.kwargs.get("user_id") == default_test_user.id
        assert m.await_args.kwargs["front"] == "Q"  # stripped

    async def test_create_unknown_course_is_404(self, async_client):
        with patch(
            f"{SVC}.create_flashcard", new_callable=AsyncMock, side_effect=ItemNotFoundError
        ):
            r = await async_client.post("/api/assets/flashcards", json=FC_BODY)
        assert r.status_code == 404

    async def test_create_without_source_is_409_with_code(self, async_client):
        with patch(
            f"{SVC}.create_flashcard", new_callable=AsyncMock, side_effect=NoSourceArtifactError
        ):
            r = await async_client.post("/api/assets/flashcards", json=FC_BODY)
        assert r.status_code == 409
        assert r.json()["detail"] == "no_source_artifact"

    @pytest.mark.parametrize(
        "patch_body",
        [{"front": "   "}, {"week": 0}, {"week": 53}, {"back": "x" * 4001}, {"course_code": ""}],
    )
    async def test_create_validation_422(self, async_client, patch_body):
        r = await async_client.post("/api/assets/flashcards", json={**FC_BODY, **patch_body})
        assert r.status_code == 422

    async def test_patch_returns_new_copy_and_scopes_lookup(self, async_client, default_test_user):
        with patch(f"{SVC}.update_flashcard", new_callable=AsyncMock, return_value=_card()) as m:
            r = await async_client.patch("/api/assets/flashcards/fc-1", json={"front": "x"})
        assert r.status_code == 200
        assert r.json()["id"] == "fc-new"
        assert m.await_args.args[1] == "fc-1"
        assert m.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_patch_foreign_is_404_and_scoped(self, async_client, default_test_user):
        with patch(
            f"{SVC}.update_flashcard", new_callable=AsyncMock, side_effect=ItemNotFoundError
        ) as m:
            r = await async_client.patch("/api/assets/flashcards/other", json={"back": "x"})
        assert r.status_code == 404
        assert m.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_patch_empty_body_is_422(self, async_client):
        r = await async_client.patch("/api/assets/flashcards/fc-1", json={})
        assert r.status_code == 422

    async def test_delete_archives_204_scoped(self, async_client, default_test_user):
        with patch(f"{SVC}.archive_flashcard", new_callable=AsyncMock) as m:
            r = await async_client.delete("/api/assets/flashcards/fc-1")
        assert r.status_code == 204
        assert m.await_args.args[1] == "fc-1"
        assert m.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_delete_foreign_is_404_scoped(self, async_client, default_test_user):
        with patch(
            f"{SVC}.archive_flashcard", new_callable=AsyncMock, side_effect=ItemNotFoundError
        ) as m:
            r = await async_client.delete("/api/assets/flashcards/other")
        assert r.status_code == 404
        assert m.await_args.kwargs.get("user_id") == default_test_user.id


@pytest.mark.asyncio
class TestQuizItems:
    async def test_create_returns_201_scoped(self, async_client, default_test_user):
        with patch(
            f"{SVC}.create_quiz_question", new_callable=AsyncMock, return_value=_quiz()
        ) as m:
            r = await async_client.post("/api/assets/quiz", json=QZ_BODY)
        assert r.status_code == 201
        assert m.await_args.kwargs.get("user_id") == default_test_user.id
        assert m.await_args.kwargs["correct_answer"] == "B"

    @pytest.mark.parametrize(
        "patch_body",
        [
            {"question_type": "essay"},
            {"options": ["A. x"]},
            {"correct_answer": "Z"},
            {"options": None},
            {"question": ""},
        ],
    )
    async def test_create_validation_422(self, async_client, patch_body):
        r = await async_client.post("/api/assets/quiz", json={**QZ_BODY, **patch_body})
        assert r.status_code == 422

    async def test_short_answer_with_options_is_422(self, async_client):
        body = {**QZ_BODY, "question_type": "short_answer", "correct_answer": "x"}
        assert (await async_client.post("/api/assets/quiz", json=body)).status_code == 422

    async def test_short_answer_ok(self, async_client):
        body = {
            "course_code": "CSIT302",
            "week": 3,
            "question_type": "short_answer",
            "question": "Why?",
            "correct_answer": "Because",
        }
        with patch(f"{SVC}.create_quiz_question", new_callable=AsyncMock, return_value=_quiz()):
            assert (await async_client.post("/api/assets/quiz", json=body)).status_code == 201

    async def test_patch_scoped(self, async_client, default_test_user):
        with patch(
            f"{SVC}.update_quiz_question", new_callable=AsyncMock, return_value=_quiz()
        ) as m:
            r = await async_client.patch("/api/assets/quiz/q-1", json={"explanation": "e"})
        assert r.status_code == 200
        assert m.await_args.args[1] == "q-1"
        assert m.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_patch_foreign_404(self, async_client, default_test_user):
        with patch(
            f"{SVC}.update_quiz_question", new_callable=AsyncMock, side_effect=ItemNotFoundError
        ) as m:
            r = await async_client.patch("/api/assets/quiz/o", json={"question": "x"})
        assert r.status_code == 404
        assert m.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_patch_service_value_error_is_422(self, async_client):
        with patch(
            f"{SVC}.update_quiz_question", new_callable=AsyncMock, side_effect=ValueError("bad")
        ):
            r = await async_client.patch("/api/assets/quiz/q-1", json={"correct_answer": "Q"})
        assert r.status_code == 422

    async def test_delete_scoped(self, async_client, default_test_user):
        with patch(f"{SVC}.archive_quiz_question", new_callable=AsyncMock) as m:
            r = await async_client.delete("/api/assets/quiz/q-1")
        assert r.status_code == 204
        assert m.await_args.kwargs.get("user_id") == default_test_user.id

    async def test_delete_foreign_404(self, async_client, default_test_user):
        with patch(
            f"{SVC}.archive_quiz_question", new_callable=AsyncMock, side_effect=ItemNotFoundError
        ) as m:
            r = await async_client.delete("/api/assets/quiz/o")
        assert r.status_code == 404
        assert m.await_args.kwargs.get("user_id") == default_test_user.id
