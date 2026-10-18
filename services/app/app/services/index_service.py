"""Index service — chunking and embedding logic for the index pipeline stage."""

import asyncio
from dataclasses import dataclass

import structlog
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.embeddings import (
    MINILM_MAX_SEQ_LENGTH,
    EmbeddingProvider,
    aembed_texts,
    count_word_tokens,
    heuristic_word_tokens,
    input_window,
)
from app.config import settings
from app.core.utils import generate_id
from app.models.chunk import Chunk

logger = structlog.get_logger()


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate (~4 chars per token for English).

    Args:
        text: Input text.

    Returns:
        Estimated token count.
    """
    return len(text) // 4


def _build_stable_id(artifact_id: str, page_ref: int, chunk_idx: int) -> str:
    """Build a deterministic chunk ID, stable within one artifact.

    Scoped to the artifact, not to the file's content hash. `chunks.stable_id`
    is globally UNIQUE, so a hash-derived id made two users who uploaded the
    same file collide and the second one's index stage crash (#85). An
    artifact id is a UUID, so this shape is globally unique on its own and the
    existing constraint stops mattering.

    Args:
        artifact_id: UUID of the artifact the chunk belongs to.
        page_ref: Page number the chunk starts on.
        chunk_idx: Sequential chunk index within the artifact.

    Returns:
        Stable ID string like "<artifact-uuid>_p1_c0".
    """
    return f"{artifact_id}_p{page_ref}_c{chunk_idx}"


# [CLS] + [SEP] are added by the embedder around every input, plus a little
# headroom for tokenizer differences between counting and embedding.
_SPECIAL_TOKENS = 2
_HEADROOM_TOKENS = 6

# Window assumed when no provider is injected: MiniLM, the default backend.
_DEFAULT_WINDOW = MINILM_MAX_SEQ_LENGTH


def max_chunk_tokens(provider: EmbeddingProvider | None = None) -> int:
    """Largest chunk, in the embedder's own tokens, that is embedded in full.

    Anything beyond the model's context window is silently dropped by the
    embedder, so a bigger chunk is partly unsearchable (GL#17). The configured
    and user-set chunk sizes are both clamped to this.

    Args:
        provider: The embedding provider; MiniLM's window is assumed if omitted.

    Returns:
        The model's window less special tokens and headroom (248 for MiniLM).
    """
    window = input_window(provider) if provider is not None else _DEFAULT_WINDOW
    return max(8, window - _SPECIAL_TOKENS - _HEADROOM_TOKENS)


def chunk_pages(
    pages: list[dict],
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
    provider: EmbeddingProvider | None = None,
) -> list[dict]:
    """Split extraction pages into overlapping text chunks that fit the embedder.

    Page-aware windows measured in the embedder's own tokens (not whitespace
    words, not chars/4): each chunk is at most `max_chunk_tokens(provider)`
    tokens whatever size was requested, so nothing is truncated at embed time.
    A word that is longer than the window on its own gets a chunk to itself.

    Args:
        pages: List of page dicts with "page_number", "text", optional "slide_title".
        chunk_size_tokens: Requested tokens per chunk (default from settings),
            clamped to the embedder window.
        chunk_overlap_tokens: Requested overlap (default from settings), clamped
            to half the chunk so every chunk advances.
        provider: Embedding provider whose tokenizer and window to size against.

    Returns:
        List of chunk dicts with "text", "page_ref", "slide_title", "chunk_idx".
    """
    cap = min(chunk_size_tokens or settings.chunk_size_tokens, max_chunk_tokens(provider))
    overlap_req = (
        settings.chunk_overlap_tokens if chunk_overlap_tokens is None else chunk_overlap_tokens
    )
    overlap = max(0, min(overlap_req, cap // 2))

    def count(words: list[str]) -> list[int]:
        if provider is None:
            return heuristic_word_tokens(words)
        return count_word_tokens(provider, words)

    chunks: list[dict] = []
    cur: list[tuple[str, int]] = []
    cur_tokens = 0
    page_ref = 1
    slide: str | None = None

    def emit() -> None:
        chunks.append(
            {
                "text": " ".join(w for w, _ in cur),
                "page_ref": page_ref,
                "slide_title": slide,
                "chunk_idx": len(chunks),
            }
        )

    for page in pages:
        page_num = page.get("page_number", 1)
        words = (page.get("text") or "").split()
        if not words:
            continue
        slide_title = page.get("slide_title") or page.get("title")
        if not cur:
            page_ref, slide = page_num, slide_title

        for word, n in zip(words, count(words), strict=True):
            if cur and cur_tokens + n > cap:
                emit()
                tail: list[tuple[str, int]] = []
                acc = 0
                for item in reversed(cur):
                    if acc + item[1] > overlap:
                        break
                    tail.insert(0, item)
                    acc += item[1]
                while tail and acc + n > cap:
                    acc -= tail.pop(0)[1]
                cur, cur_tokens = tail, acc
                page_ref, slide = page_num, slide_title
            cur.append((word, n))
            cur_tokens += n

    if cur:
        emit()
    return chunks


@dataclass(frozen=True)
class EmbeddedChunks:
    """Chunks and their vectors, computed with no database session involved.

    Attributes:
        chunks: Chunk dicts as `chunk_pages` returns them.
        vectors: One embedding per chunk, in the same order.
    """

    chunks: list[dict]
    vectors: list[list[float]]

    def __post_init__(self) -> None:
        if len(self.chunks) != len(self.vectors):
            raise ValueError("EmbeddedChunks needs exactly one vector per chunk")


def embed_artifact_chunks(
    pages: list[dict],
    embedding_provider: EmbeddingProvider,
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
) -> EmbeddedChunks:
    """Chunk the pages and embed them in one batch. Pure: takes no session.

    Synchronous; async callers use `aembed_artifact_chunks` so the encoder does not
    run on the event loop.

    Args:
        pages: Extraction manifest pages.
        embedding_provider: Provider for generating embeddings.
        chunk_size_tokens: Optional override for chunk size.
        chunk_overlap_tokens: Optional override for overlap.

    Returns:
        The chunks with their vectors; empty when the pages hold no text (the
        provider is then not called).
    """
    raw_chunks = chunk_pages(
        pages, chunk_size_tokens, chunk_overlap_tokens, provider=embedding_provider
    )
    if not raw_chunks:
        return EmbeddedChunks(chunks=[], vectors=[])
    vectors = embedding_provider.embed_texts([c["text"] for c in raw_chunks])
    return EmbeddedChunks(chunks=raw_chunks, vectors=vectors)


async def aembed_artifact_chunks(
    pages: list[dict],
    embedding_provider: EmbeddingProvider,
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
) -> EmbeddedChunks:
    """`embed_artifact_chunks` with chunking and encoding off the event loop.

    Takes no session, so the caller can release its connection before awaiting
    this and hold no transaction across the provider call (GL#50).

    Args:
        pages: Extraction manifest pages.
        embedding_provider: Provider for generating embeddings.
        chunk_size_tokens: Optional override for chunk size.
        chunk_overlap_tokens: Optional override for overlap.

    Returns:
        The chunks with their vectors; empty when the pages hold no text.
    """
    raw_chunks = await asyncio.to_thread(
        chunk_pages, pages, chunk_size_tokens, chunk_overlap_tokens, embedding_provider
    )
    if not raw_chunks:
        return EmbeddedChunks(chunks=[], vectors=[])
    vectors = await aembed_texts(embedding_provider, [c["text"] for c in raw_chunks])
    return EmbeddedChunks(chunks=raw_chunks, vectors=vectors)


async def store_artifact_chunks(
    session: AsyncSession, artifact_id: str, embedded: EmbeddedChunks
) -> list[Chunk]:
    """Replace an artifact's chunks with already-embedded ones. Caller commits.

    Idempotent: deletes the artifact's existing chunks and inserts the new ones
    with stable ids. With nothing to store, existing chunks are left alone.
    Never calls the embedding provider.

    Args:
        session: Async database session.
        artifact_id: UUID of the artifact; also scopes stable IDs.
        embedded: Output of `embed_artifact_chunks` / `aembed_artifact_chunks`.

    Returns:
        The created Chunk records.
    """
    if not embedded.chunks:
        logger.warning("no_chunks_generated", artifact_id=artifact_id)
        return []

    await session.execute(delete(Chunk).where(Chunk.artifact_id == artifact_id))

    chunk_records = []
    for raw_chunk, embedding in zip(embedded.chunks, embedded.vectors, strict=True):
        chunk = Chunk(
            id=generate_id(),
            artifact_id=artifact_id,
            stable_id=_build_stable_id(artifact_id, raw_chunk["page_ref"], raw_chunk["chunk_idx"]),
            text=raw_chunk["text"],
            page_ref=raw_chunk["page_ref"],
            slide_title=raw_chunk.get("slide_title"),
            embedding=embedding,
        )
        session.add(chunk)
        chunk_records.append(chunk)

    await session.flush()
    logger.info("chunks_stored", artifact_id=artifact_id, count=len(chunk_records))
    return chunk_records


async def index_artifact_chunks(
    session: AsyncSession,
    artifact_id: str,
    pages: list[dict],
    embedding_provider: EmbeddingProvider,
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
) -> list[Chunk]:
    """Chunk, embed and store in one call (embeds on the loop, session open).

    Kept for callers that have not moved to the split steps; the pipeline stage
    should use `aembed_artifact_chunks` then `store_artifact_chunks`.

    Args:
        session: Async database session.
        artifact_id: UUID of the artifact being indexed. Also scopes stable IDs.
        pages: Extraction manifest pages.
        embedding_provider: Provider for generating embeddings.
        chunk_size_tokens: Optional override for chunk size.
        chunk_overlap_tokens: Optional override for overlap.

    Returns:
        List of created Chunk records.
    """
    embedded = embed_artifact_chunks(
        pages, embedding_provider, chunk_size_tokens, chunk_overlap_tokens
    )
    return await store_artifact_chunks(session, artifact_id, embedded)


def chunk_exceeds_window(provider: EmbeddingProvider, text: str) -> bool:
    """True when a stored chunk is longer than the embedder embeds in full.

    Used by the re-embed task (GL#17) to find chunks written before chunks were
    sized to the embedder's window.

    Args:
        provider: The embedding provider.
        text: The stored chunk text.

    Returns:
        Whether the chunk's tail was being truncated away at embed time.
    """
    return sum(count_word_tokens(provider, text.split())) > input_window(provider) - _SPECIAL_TOKENS
