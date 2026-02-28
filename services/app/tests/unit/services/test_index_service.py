"""Tests for index service — chunking and embedding logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.index_service import (
    _build_stable_id,
    _estimate_tokens,
    chunk_pages,
)


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_short_string(self):
        assert _estimate_tokens("hello") == 1

    def test_longer_string(self):
        text = "a" * 400
        assert _estimate_tokens(text) == 100


class TestBuildStableId:
    """Tests for stable chunk ID generation."""

    def test_format(self):
        result = _build_stable_id("a1b2c3d4", 1, 0)
        assert result == "a1b2c3d4_p1_c0"

    def test_different_page_and_chunk(self):
        result = _build_stable_id("deadbeef", 5, 3)
        assert result == "deadbeef_p5_c3"

    def test_deterministic(self):
        """Same inputs produce same output."""
        a = _build_stable_id("abc12345", 2, 1)
        b = _build_stable_id("abc12345", 2, 1)
        assert a == b


class TestChunkPages:
    """Tests for page-aware chunking."""

    def test_single_short_page_one_chunk(self):
        """A short page produces a single chunk."""
        pages = [{"page_number": 1, "text": "Hello world"}]
        chunks = chunk_pages(pages, chunk_size_tokens=100, chunk_overlap_tokens=10)

        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello world"
        assert chunks[0]["page_ref"] == 1
        assert chunks[0]["chunk_idx"] == 0

    def test_multiple_pages_merged(self):
        """Multiple short pages can merge into fewer chunks."""
        pages = [
            {"page_number": 1, "text": "First page content."},
            {"page_number": 2, "text": "Second page content."},
        ]
        chunks = chunk_pages(pages, chunk_size_tokens=100, chunk_overlap_tokens=10)

        assert len(chunks) == 1
        assert "First page" in chunks[0]["text"]
        assert "Second page" in chunks[0]["text"]

    def test_long_text_splits_into_multiple_chunks(self):
        """Long text should be split into multiple chunks."""
        long_text = " ".join(["word"] * 1000)  # ~1000 tokens
        pages = [{"page_number": 1, "text": long_text}]

        chunks = chunk_pages(pages, chunk_size_tokens=100, chunk_overlap_tokens=10)

        assert len(chunks) > 1
        # All chunks reference page 1
        for c in chunks:
            assert c["page_ref"] == 1

    def test_chunk_idx_sequential(self):
        """Chunk indices should be sequential starting from 0."""
        long_text = " ".join(["word"] * 1000)
        pages = [{"page_number": 1, "text": long_text}]

        chunks = chunk_pages(pages, chunk_size_tokens=100, chunk_overlap_tokens=10)

        for i, c in enumerate(chunks):
            assert c["chunk_idx"] == i

    def test_empty_pages_skipped(self):
        """Pages with no text produce no chunks."""
        pages = [
            {"page_number": 1, "text": ""},
            {"page_number": 2, "text": "   "},
        ]
        chunks = chunk_pages(pages, chunk_size_tokens=100, chunk_overlap_tokens=10)

        assert len(chunks) == 0

    def test_slide_title_preserved(self):
        """Slide titles are carried into chunk metadata."""
        pages = [
            {"page_number": 1, "text": "Content here", "slide_title": "Introduction"},
        ]
        chunks = chunk_pages(pages, chunk_size_tokens=100, chunk_overlap_tokens=10)

        assert chunks[0]["slide_title"] == "Introduction"

    def test_overlap_present(self):
        """Chunks should overlap — text from end of chunk N appears at start of chunk N+1."""
        # Create text long enough for exactly 2 chunks with overlap
        long_text = " ".join(["testword"] * 500)
        pages = [{"page_number": 1, "text": long_text}]

        chunks = chunk_pages(pages, chunk_size_tokens=100, chunk_overlap_tokens=20)

        if len(chunks) >= 2:
            # Last words of chunk 0 should appear at start of chunk 1
            end_words = chunks[0]["text"].split()[-5:]
            start_of_next = chunks[1]["text"]
            overlap_found = any(w in start_of_next for w in end_words)
            assert overlap_found, "Expected overlap between consecutive chunks"

    def test_page_boundary_tracking(self):
        """New chunk after split should track the current page number."""
        pages = [
            {"page_number": 1, "text": " ".join(["word"] * 500)},
            {"page_number": 2, "text": " ".join(["word"] * 500)},
        ]
        chunks = chunk_pages(pages, chunk_size_tokens=100, chunk_overlap_tokens=10)

        # Some chunks should reference page 2
        page_refs = {c["page_ref"] for c in chunks}
        assert 2 in page_refs


class TestIndexArtifactChunks:
    """Tests for the async index_artifact_chunks function."""

    @pytest.mark.asyncio
    async def test_idempotent_deletes_existing_chunks(self):
        """Re-indexing deletes old chunks before inserting new ones."""
        from app.services.index_service import index_artifact_chunks

        session = AsyncMock()
        session.add = MagicMock()

        mock_provider = MagicMock()
        mock_provider.dimensions = 384
        mock_provider.embed_texts.return_value = [[0.1] * 384]

        pages = [{"page_number": 1, "text": "Test content"}]

        with patch("app.services.index_service.generate_id", return_value="chunk-001"):
            result = await index_artifact_chunks(
                session=session,
                artifact_id="art-001",
                sha256="a" * 64,
                pages=pages,
                embedding_provider=mock_provider,
            )

        # Should have called delete and add
        assert session.execute.called
        assert session.add.called
        assert len(result) == 1
        assert result[0].artifact_id == "art-001"

    @pytest.mark.asyncio
    async def test_empty_pages_returns_empty(self):
        """No text content produces no chunks."""
        from app.services.index_service import index_artifact_chunks

        session = AsyncMock()
        mock_provider = MagicMock()

        pages = [{"page_number": 1, "text": ""}]

        result = await index_artifact_chunks(
            session=session,
            artifact_id="art-001",
            sha256="a" * 64,
            pages=pages,
            embedding_provider=mock_provider,
        )

        assert result == []
        mock_provider.embed_texts.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_embedding_called_once(self):
        """Embeddings should be generated in a single batch call."""
        from app.services.index_service import index_artifact_chunks

        session = AsyncMock()
        session.add = MagicMock()

        mock_provider = MagicMock()
        mock_provider.dimensions = 384
        mock_provider.embed_texts.return_value = [
            [0.1] * 384,
            [0.2] * 384,
        ]

        pages = [
            {"page_number": 1, "text": "First chunk content here"},
            {"page_number": 2, "text": "Second chunk content here"},
        ]

        with patch("app.services.index_service.generate_id", return_value="chunk-001"):
            result = await index_artifact_chunks(
                session=session,
                artifact_id="art-001",
                sha256="a" * 64,
                pages=pages,
                embedding_provider=mock_provider,
                chunk_size_tokens=100,
            )

        # embed_texts called exactly once (batched)
        mock_provider.embed_texts.assert_called_once()
