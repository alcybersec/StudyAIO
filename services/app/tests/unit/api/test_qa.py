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
