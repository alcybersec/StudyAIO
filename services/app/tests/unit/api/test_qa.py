"""Tests for the Q&A API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AnswerResult


@pytest.mark.asyncio
class TestAskQuestion:
    """Tests for POST /api/qa/ask."""

    async def test_ask_question_success(self, async_client, mock_session):
        """Successful Q&A returns answer with citations."""
        mock_chunks = [
            {
                "chunk_id": "chunk-001",
                "text": "Firewalls are security systems.",
                "page_ref": 1,
                "slide_title": "Firewalls",
                "artifact_id": "art-001",
                "week": 5,
                "artifact_title": "Network Security",
                "original_filename": "Week5.pdf",
                "course_code": "CSIT302",
                "course_id": "course-001",
                "similarity": 0.85,
            }
        ]

        mock_answer = AnswerResult(
            answer="Firewalls are security systems that monitor traffic [1].",
            citations=[
                {
                    "ref": 1,
                    "chunk_id": "chunk-001",
                    "text_snippet": "Firewalls are security systems.",
                    "course_code": "CSIT302",
                    "week": 5,
                    "page_ref": 1,
                }
            ],
        )

        mock_provider = MagicMock()
        mock_provider.embed_texts.return_value = [[0.1] * 384]

        mock_agent = AsyncMock()
        mock_agent.answer_question.return_value = mock_answer

        with (
            patch("app.api.qa.get_embedding_provider", return_value=mock_provider),
            patch(
                "app.api.qa.search_service.search_chunks",
                new_callable=AsyncMock,
                return_value=mock_chunks,
            ),
            patch("app.api.qa.get_agent", return_value=mock_agent),
        ):
            response = await async_client.post(
                "/api/qa/ask",
                json={"question": "What is a firewall?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "Firewalls" in data["answer"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["course_code"] == "CSIT302"
        assert data["chunks_searched"] == 1

    async def test_ask_question_no_chunks_returns_empty(self, async_client, mock_session):
        """No matching chunks returns helpful message."""
        mock_provider = MagicMock()
        mock_provider.embed_texts.return_value = [[0.1] * 384]

        with (
            patch("app.api.qa.get_embedding_provider", return_value=mock_provider),
            patch(
                "app.api.qa.search_service.search_chunks",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            response = await async_client.post(
                "/api/qa/ask",
                json={"question": "What is quantum computing?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "couldn't find" in data["answer"].lower()
        assert data["citations"] == []
        assert data["chunks_searched"] == 0

    async def test_ask_question_with_course_filter(self, async_client, mock_session):
        """Course code filter resolves to course_id."""
        mock_course = MagicMock()
        mock_course.id = "course-001"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_course
        mock_session.execute.return_value = mock_result

        mock_provider = MagicMock()
        mock_provider.embed_texts.return_value = [[0.1] * 384]

        with (
            patch("app.api.qa.get_embedding_provider", return_value=mock_provider),
            patch(
                "app.api.qa.search_service.search_chunks",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            response = await async_client.post(
                "/api/qa/ask",
                json={
                    "question": "What is a firewall?",
                    "course_code": "CSIT302",
                },
            )

        assert response.status_code == 200

    async def test_ask_question_unknown_course_returns_404(self, async_client, mock_session):
        """Unknown course code returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        response = await async_client.post(
            "/api/qa/ask",
            json={
                "question": "What is a firewall?",
                "course_code": "INVALID999",
            },
        )

        assert response.status_code == 404

    async def test_ask_question_missing_question_returns_422(self, async_client):
        """Missing question field returns validation error."""
        response = await async_client.post(
            "/api/qa/ask",
            json={},
        )

        assert response.status_code == 422


def _chunk(n: int) -> dict:
    return {
        "chunk_id": f"chunk-{n}",
        "text": f"Real text of chunk {n}.",
        "page_ref": n,
        "artifact_id": f"art-{n}",
        "week": n,
        "course_code": "CSIT302",
    }


async def _ask(async_client, answer: str, adapter_citations: list[dict], n_chunks: int = 3):
    provider = MagicMock()
    provider.embed_texts.return_value = [[0.1] * 384]
    agent = AsyncMock()
    agent.answer_question.return_value = AnswerResult(answer=answer, citations=adapter_citations)
    chunks = [_chunk(i) for i in range(1, n_chunks + 1)]
    with (
        patch("app.api.qa.get_embedding_provider", return_value=provider),
        patch(
            "app.api.qa.search_service.search_chunks",
            new_callable=AsyncMock,
            return_value=chunks,
        ),
        patch("app.api.qa.get_agent", return_value=agent),
    ):
        return await async_client.post("/api/qa/ask", json={"question": "q?"})


@pytest.mark.asyncio
class TestQACitationsDerived:
    """Citations come from the retrieved chunks, never from the adapter (GL#13)."""

    async def test_adapter_citations_with_wrong_ids_are_ignored(self, async_client, mock_session):
        bogus = [
            {
                "ref": 1,
                "chunk_id": "FAKE",
                "artifact_id": "FAKE",
                "text_snippet": "invented",
                "course_code": "XXX999",
                "week": 99,
                "page_ref": 99,
            }
        ]
        response = await _ask(async_client, "Answer [1].", bogus)
        cites = response.json()["citations"]
        assert len(cites) == 1
        assert cites[0]["chunk_id"] == "chunk-1"
        assert cites[0]["artifact_id"] == "art-1"
        assert cites[0]["text_snippet"] == "Real text of chunk 1."
        assert cites[0]["course_code"] == "CSIT302"

    async def test_markers_map_to_chunk_at_position(self, async_client, mock_session):
        response = await _ask(async_client, "A [3] and B [2].", [])
        cites = response.json()["citations"]
        assert [(c["ref"], c["chunk_id"]) for c in cites] == [(2, "chunk-2"), (3, "chunk-3")]

    async def test_out_of_range_marker_ignored(self, async_client, mock_session):
        response = await _ask(async_client, "A [1] and [9] and [0].", [])
        assert [c["ref"] for c in response.json()["citations"]] == [1]

    async def test_grouped_markers(self, async_client, mock_session):
        response = await _ask(async_client, "Both [1, 3].", [])
        assert [c["chunk_id"] for c in response.json()["citations"]] == ["chunk-1", "chunk-3"]

    async def test_no_markers_means_no_citations(self, async_client, mock_session):
        bogus = [{"ref": 1, "chunk_id": "FAKE", "text_snippet": "x"}]
        response = await _ask(async_client, "No markers here.", bogus)
        assert response.json()["citations"] == []
