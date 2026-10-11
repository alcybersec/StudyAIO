"""Chunks must fit the embedder's context window (GL#17, audit AI-03).

all-MiniLM-L6-v2 embeds at most 256 word pieces and silently truncates the rest,
so the tail of a ~500-token chunk was unsearchable. These tests pin that every
chunk the chunker emits is embedded in full, whatever the (user-settable) size.
"""

import math

import pytest

from app.agents.embeddings import EmbeddingProvider
from app.services.index_service import chunk_pages


class FakeProvider(EmbeddingProvider):
    """Provider with a tiny window and a fixed tokens-per-word tokenizer."""

    def __init__(self, limit: int = 64, per_word: int = 3):
        self._limit = limit
        self._per_word = per_word

    @property
    def dimensions(self) -> int:
        return 4

    def _input_window(self) -> int:
        return self._limit

    def _word_tokens(self, words):
        return [self._per_word for _ in words]

    def embed_texts(self, texts):
        return [[0.0] * 4 for _ in texts]

    def preload(self) -> None:
        pass


def _tokens(provider: FakeProvider, text: str) -> int:
    return sum(provider._word_tokens(text.split()))


def _pages(n_words: int) -> list[dict]:
    return [{"page_number": 1, "text": " ".join(f"w{i}" for i in range(n_words))}]


class TestChunksFitTheEmbedder:
    @pytest.mark.parametrize("requested", [50, 500, 5000])
    def test_every_chunk_fits_whatever_size_was_requested(self, requested):
        provider = FakeProvider(limit=64)
        chunks = chunk_pages(_pages(600), requested, 10, provider=provider)

        assert len(chunks) > 1
        for c in chunks:
            # +2 for [CLS]/[SEP]
            assert _tokens(provider, c["text"]) + 2 <= provider._input_window()

    def test_every_word_is_in_some_chunk(self):
        provider = FakeProvider(limit=64)
        chunks = chunk_pages(_pages(300), 5000, 10, provider=provider)
        seen = set(" ".join(c["text"] for c in chunks).split())
        assert seen == {f"w{i}" for i in range(300)}

    def test_overlap_is_bounded_so_chunks_still_advance(self):
        provider = FakeProvider(limit=64)
        # overlap >= size would never advance; it must be clamped
        chunks = chunk_pages(_pages(200), 5000, 5000, provider=provider)
        assert len(chunks) < 200
        for c in chunks:
            assert _tokens(provider, c["text"]) + 2 <= 64

    def test_overlap_carries_tail_words_into_next_chunk(self):
        provider = FakeProvider(limit=64)
        chunks = chunk_pages(_pages(300), 5000, 12, provider=provider)
        tail = chunks[0]["text"].split()[-1]
        assert tail in chunks[1]["text"].split()[:6]

    def test_oversize_single_word_does_not_loop_forever(self):
        provider = FakeProvider(limit=64, per_word=100)
        chunks = chunk_pages(_pages(5), 5000, 10, provider=provider)
        assert len(chunks) == 5

    def test_default_size_without_provider_is_capped_to_minilm_window(self):
        """No provider injected: the chunker still never exceeds MiniLM's window."""
        words = [f"w{i}" for i in range(2000)]
        chunks = chunk_pages([{"page_number": 1, "text": " ".join(words)}], 5000, 50)
        for c in chunks:
            est = sum(max(1, math.ceil(len(w) / 4)) for w in c["text"].split())
            assert est <= 254
