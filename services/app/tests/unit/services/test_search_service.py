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
