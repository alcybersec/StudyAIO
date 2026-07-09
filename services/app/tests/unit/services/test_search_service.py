"""Tests for search service — pgvector similarity search."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSearchChunks:
    """Tests for search_chunks function."""

    @pytest.mark.asyncio
    async def test_returns_results_with_metadata(self):
        """Search returns results with all expected fields."""
        from app.services.search_service import search_chunks

        mock_row = MagicMock()
        mock_row.id = "chunk-001"
        mock_row.text = "Firewall types and configurations"
        mock_row.page_ref = 1
        mock_row.slide_title = "Firewalls"
        mock_row.artifact_id = "art-001"
        mock_row.week = 5
        mock_row.artifact_title = "Network Security"
        mock_row.original_filename = "Week5.pdf"
        mock_row.course_code = "CSIT302"
        mock_row.course_id = "course-001"
        mock_row.distance = 0.15

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        results = await search_chunks(
            session=session,
            query_embedding=[0.1] * 384,
            top_k=10,
        )

        assert len(results) == 1
        r = results[0]
        assert r["chunk_id"] == "chunk-001"
        assert r["text"] == "Firewall types and configurations"
        assert r["page_ref"] == 1
        assert r["slide_title"] == "Firewalls"
        assert r["artifact_id"] == "art-001"
        assert r["week"] == 5
        assert r["course_code"] == "CSIT302"
        assert r["similarity"] == round(1.0 - 0.15, 4)

    @pytest.mark.asyncio
    async def test_empty_results(self):
        """No matching chunks returns empty list."""
        from app.services.search_service import search_chunks

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute.return_value = mock_result

        results = await search_chunks(
            session=session,
            query_embedding=[0.1] * 384,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_similarity_score_calculation(self):
        """Similarity = 1 - cosine distance."""
        from app.services.search_service import search_chunks

        mock_row = MagicMock()
        mock_row.id = "chunk-001"
        mock_row.text = "test"
        mock_row.page_ref = 1
        mock_row.slide_title = None
        mock_row.artifact_id = "art-001"
        mock_row.week = 1
        mock_row.artifact_title = "Title"
        mock_row.original_filename = "file.pdf"
        mock_row.course_code = "CS101"
        mock_row.course_id = "course-001"
        mock_row.distance = 0.0  # Perfect match

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute.return_value = mock_result

        results = await search_chunks(
            session=session,
            query_embedding=[0.1] * 384,
        )

        assert results[0]["similarity"] == 1.0

    @pytest.mark.asyncio
    async def test_default_top_k_from_settings(self):
        """When top_k is None, uses settings.search_top_k."""
        from app.services.search_service import search_chunks

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute.return_value = mock_result

        # Just verify it doesn't crash with default top_k
        results = await search_chunks(
            session=session,
            query_embedding=[0.1] * 384,
        )

        assert results == []
        session.execute.assert_called_once()


class TestEscapeLike:
    """Tests for LIKE wildcard escaping."""

    def test_escapes_percent_underscore_and_backslash(self):
        """Wildcard characters are escaped so they match literally."""
        from app.services.search_service import escape_like

        assert escape_like("%foo_") == "\\%foo\\_"
        assert escape_like("a\\b") == "a\\\\b"
        assert escape_like("plain") == "plain"


class TestSearchAll:
    """Tests for global search across entity kinds."""

    def _result_with_scalars(self, items):
        result = MagicMock()
        result.scalars.return_value.all.return_value = items
        return result

    def _result_with_rows(self, rows):
        result = MagicMock()
        result.all.return_value = rows
        return result

    @pytest.mark.asyncio
    async def test_search_returns_grouped_matches(self):
        """Matches across summaries, flashcards, and chat sessions are returned
        with their kind and stamped with the searching user's id."""
        from app.services.search_service import search_all

        user_id = "user-001"

        # Query order: courses, summaries, flashcards, chat sessions
        course_result = self._result_with_rows([])

        summary_row = MagicMock()
        summary_row.id = "sum-001"
        summary_row.week = 3
        summary_row.content_md = "# Week 3\n\nAll about forensics and evidence."
        summary_row.course_code = "CSIT302"
        summary_result = self._result_with_rows([summary_row])

        flashcard_row = MagicMock()
        flashcard_row.id = "fc-001"
        flashcard_row.front = "What is digital forensics?"
        flashcard_row.week = 3
        flashcard_row.course_code = "CSIT302"
        flashcard_result = self._result_with_rows([flashcard_row])

        chat_row = MagicMock()
        chat_row.id = "chat-001"
        chat_row.title = "forensics intro"
        chat_result = self._result_with_rows([chat_row])

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[course_result, summary_result, flashcard_result, chat_result]
        )

        results = await search_all(session, user_id, "forensics", limit=10)

        kinds = {r.kind for r in results}
        assert kinds == {"course_week", "flashcard", "chat_session"}
        assert all(r.user_id == user_id for r in results)

    @pytest.mark.asyncio
    async def test_search_includes_course_matches(self):
        """Courses matching by code are returned as kind='course'."""
        from app.services.search_service import search_all

        course_row = MagicMock()
        course_row.id = "course-001"
        course_row.code = "CSIT302"
        course_row.name = "Cybersecurity"
        course_result = self._result_with_rows([course_row])
        empty = self._result_with_rows([])

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[course_result, empty, empty, empty])

        results = await search_all(session, "user-001", "CSIT", limit=10)

        assert [r.kind for r in results] == ["course"]
        assert results[0].title == "CSIT302 — Cybersecurity"
        assert results[0].href_meta["course_code"] == "CSIT302"

    @pytest.mark.asyncio
    async def test_search_respects_limit(self):
        """No more than `limit` results are returned overall."""
        from app.services.search_service import search_all

        rows = []
        for i in range(8):
            row = MagicMock()
            row.id = f"chat-{i}"
            row.title = f"forensics session {i}"
            rows.append(row)
        empty = self._result_with_rows([])

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[empty, empty, empty, self._result_with_rows(rows)])

        results = await search_all(session, "user-001", "forensics", limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_builds_snippet_around_match(self):
        """Summary snippet contains the matched term, not just the head of content."""
        from app.services.search_service import search_all

        summary_row = MagicMock()
        summary_row.id = "sum-001"
        summary_row.week = 3
        summary_row.content_md = ("x" * 500) + " forensics appears deep in the content"
        summary_row.course_code = "CSIT302"
        empty = self._result_with_rows([])

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[empty, self._result_with_rows([summary_row]), empty, empty]
        )

        results = await search_all(session, "user-001", "forensics", limit=10)
        assert len(results) == 1
        assert "forensics" in results[0].snippet.lower()
