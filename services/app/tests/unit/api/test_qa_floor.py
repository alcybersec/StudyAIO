"""M33-S1-AI-014 / GL#35: Q&A answers 'not in your materials' below the floor."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AnswerResult
from app.config import settings


def _chunk(sim: float) -> dict:
    return {
        "chunk_id": "chunk-001",
        "text": "Firewalls are security systems.",
        "page_ref": 1,
        "artifact_id": "art-001",
        "week": 5,
        "course_code": "CSIT302",
        "similarity": sim,
    }


def _provider() -> MagicMock:
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.1] * 384]
    return provider


@pytest.mark.asyncio
class TestQAFloor:
    async def test_below_floor_returns_fixed_message_without_agent_or_usage(
        self, async_client, mock_session, default_test_user
    ):
        search = AsyncMock(return_value=[_chunk(settings.retrieval_min_similarity - 0.1)])
        with (
            patch("app.api.qa.get_embedding_provider", return_value=_provider()),
            patch("app.api.qa.search_service.search_chunks", search),
            patch("app.api.qa.get_agent") as get_agent,
            patch("app.api.qa.billing_service.record_ai_call", AsyncMock()) as usage,
        ):
            response = await async_client.post(
                "/api/qa/ask", json={"question": "What is quantum computing?"}
            )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "I couldn't find this in your materials for your courses."
        assert data["citations"] == []
        get_agent.assert_not_called()
        usage.assert_not_awaited()
        assert search.await_args.kwargs["user_id"] == default_test_user.id  # load-bearing

    async def test_above_floor_is_answered(self, async_client, mock_session):
        agent = AsyncMock()
        agent.answer_question.return_value = AnswerResult(answer="Firewalls [1].", citations=[])
        with (
            patch("app.api.qa.get_embedding_provider", return_value=_provider()),
            patch(
                "app.api.qa.search_service.search_chunks",
                AsyncMock(return_value=[_chunk(0.8), _chunk(0.01)]),
            ),
            patch("app.api.qa.get_agent", return_value=agent),
            patch("app.api.qa.billing_service.record_ai_call", AsyncMock()),
        ):
            response = await async_client.post("/api/qa/ask", json={"question": "firewalls?"})
        data = response.json()
        assert data["answer"] == "Firewalls [1]."
        assert data["chunks_searched"] == 1
        assert len(agent.answer_question.await_args.args[1]) == 1
