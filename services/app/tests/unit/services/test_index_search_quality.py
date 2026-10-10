"""Search-quality check for GL#17: a fact in the back half of a long chunk is found.

Runs the real all-MiniLM-L6-v2 weights offline; skipped when they are not in the
local HuggingFace cache (CI without the model), where the fake-window tests in
`test_index_chunk_fit.py` still pin the fit invariant.
"""

import os

import pytest

from app.agents.embeddings import SentenceTransformerProvider, input_window
from app.services.index_service import chunk_pages


@pytest.fixture(scope="module")
def provider():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    p = SentenceTransformerProvider()
    try:
        p.preload()
    except Exception as exc:  # model not cached
        pytest.skip(f"all-MiniLM-L6-v2 not available offline: {exc}")
    return p


FILLER = (
    "The Waterfall model proceeds through requirements, design, implementation, "
    "verification and maintenance in strict order, and each phase must finish "
    "before the next begins. "
)
FACT = (
    "Mitochondrial ATP synthase rotates about one hundred times per second "
    "producing adenosine triphosphate from proton gradients."
)
QUERY = "How fast does ATP synthase rotate to make adenosine triphosphate?"


def _cosine(a, b):
    num = sum(x * y for x, y in zip(a, b, strict=True))
    da = sum(x * x for x in a) ** 0.5
    db = sum(y * y for y in b) ** 0.5
    return num / (da * db)


def _doc():
    return [{"page_number": 1, "text": FILLER * 14 + FACT + " " + FILLER * 4}]


def _tok_len(provider, text):
    return len(provider._model.tokenizer(text)["input_ids"])


def test_measured_limit_is_256(provider):
    assert input_window(provider) == 256


def test_fact_in_back_half_of_an_old_sized_chunk_was_truncated_away(provider):
    """Baseline: the old chunker closed a chunk at len(text)//4 >= 500, i.e. 2000 chars.

    Such a chunk runs past the embedder's 256 word pieces, so a fact in its back
    half never reaches the vector.
    """
    text = _doc()[0]["text"]
    end = text.index(FACT) + len(FACT)
    old_chunk = text[end - 2000 : end]
    assert "ATP synthase" in old_chunk
    tok = provider._model.tokenizer
    assert len(tok(old_chunk)["input_ids"]) > input_window(provider)
    embedded = tok.decode(tok(old_chunk, truncation=True, max_length=256)["input_ids"])
    assert "ATP synthase" not in embedded


def test_fact_retrievable_after_rechunking(provider):
    chunks = chunk_pages(_doc(), 500, 50, provider=provider)
    for c in chunks:
        assert _tok_len(provider, c["text"]) <= input_window(provider)
    vecs = provider.embed_texts([c["text"] for c in chunks])
    q = provider.embed_texts([QUERY])[0]
    scores = [_cosine(q, v) for v in vecs]
    best = max(range(len(chunks)), key=scores.__getitem__)
    assert "one hundred times per second" in chunks[best]["text"]
