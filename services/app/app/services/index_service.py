"""Index service — chunking and embedding logic for the index pipeline stage."""

import hashlib

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.embeddings import EmbeddingProvider
from app.config import settings
from app.models.chunk import Chunk
from app.core.utils import generate_id

logger = structlog.get_logger()


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate (~4 chars per token for English).

    Args:
        text: Input text.

    Returns:
        Estimated token count.
    """
    return len(text) // 4


def _build_stable_id(sha256_prefix: str, page_ref: int, chunk_idx: int) -> str:
    """Build a deterministic chunk ID for idempotent upserts.

    Args:
        sha256_prefix: First 8 chars of the artifact's SHA-256 hash.
        page_ref: Page number the chunk starts on.
        chunk_idx: Sequential chunk index within the artifact.

    Returns:
        Stable ID string like "a1b2c3d4_p1_c0".
    """
    return f"{sha256_prefix}_p{page_ref}_c{chunk_idx}"


def chunk_pages(
    pages: list[dict],
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
) -> list[dict]:
    """Split extraction pages into overlapping text chunks.

    Uses page-aware fixed-token windows: processes page by page,
    accumulates text until chunk_size_tokens is reached, then starts
    a new chunk with overlap from the previous one.

    Args:
        pages: List of page dicts with "page_number", "text", optional "slide_title".
        chunk_size_tokens: Target tokens per chunk (default from settings).
        chunk_overlap_tokens: Overlap tokens between chunks (default from settings).

    Returns:
        List of chunk dicts with "text", "page_ref", "slide_title", "chunk_idx".
    """
    chunk_size = chunk_size_tokens or settings.chunk_size_tokens
    overlap = chunk_overlap_tokens or settings.chunk_overlap_tokens

    chunks: list[dict] = []
    current_text = ""
    current_page_ref = 1
    current_slide_title: str | None = None
    chunk_idx = 0

    for page in pages:
        page_num = page.get("page_number", 1)
        page_text = page.get("text", "")
        slide_title = page.get("slide_title") or page.get("title")

        if not page_text.strip():
            continue

        # If this is the first content, set page ref
        if not current_text:
            current_page_ref = page_num
            current_slide_title = slide_title

        # Split page text into words for token-approximate processing
        words = page_text.split()

        for word in words:
            candidate = f"{current_text} {word}".strip() if current_text else word

            if _estimate_tokens(candidate) >= chunk_size:
                # Emit current chunk
                if current_text.strip():
                    chunks.append({
                        "text": current_text.strip(),
                        "page_ref": current_page_ref,
                        "slide_title": current_slide_title,
                        "chunk_idx": chunk_idx,
                    })
                    chunk_idx += 1

                # Start new chunk with overlap
                overlap_chars = overlap * 4  # rough reverse estimate
                if len(current_text) > overlap_chars:
                    overlap_text = current_text[-overlap_chars:]
                    current_text = f"{overlap_text} {word}"
                else:
                    current_text = word

                current_page_ref = page_num
                current_slide_title = slide_title
            else:
                current_text = candidate

    # Emit final chunk
    if current_text.strip():
        chunks.append({
            "text": current_text.strip(),
            "page_ref": current_page_ref,
            "slide_title": current_slide_title,
            "chunk_idx": chunk_idx,
        })

    return chunks


async def index_artifact_chunks(
    session: AsyncSession,
    artifact_id: str,
    sha256: str,
    pages: list[dict],
    embedding_provider: EmbeddingProvider,
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
) -> list[Chunk]:
    """Chunk text, generate embeddings, and upsert into the database.

    Idempotent: deletes existing chunks for this artifact before inserting.

    Args:
        session: Async database session.
        artifact_id: UUID of the artifact being indexed.
        sha256: SHA-256 hash of the original file (for stable IDs).
        pages: Extraction manifest pages.
        embedding_provider: Provider for generating embeddings.
        chunk_size_tokens: Optional override for chunk size.
        chunk_overlap_tokens: Optional override for overlap.

    Returns:
        List of created Chunk records.
    """
    sha256_prefix = sha256[:8]

    # Chunk the text
    raw_chunks = chunk_pages(pages, chunk_size_tokens, chunk_overlap_tokens)
    if not raw_chunks:
        logger.warning("no_chunks_generated", artifact_id=artifact_id)
        return []

    logger.info(
        "chunking_complete",
        artifact_id=artifact_id,
        chunk_count=len(raw_chunks),
    )

    # Generate embeddings in one batch
    texts = [c["text"] for c in raw_chunks]
    embeddings = embedding_provider.embed_texts(texts)

    logger.info(
        "embeddings_generated",
        artifact_id=artifact_id,
        count=len(embeddings),
        dimensions=embedding_provider.dimensions,
    )

    # Delete existing chunks for this artifact (idempotent upsert)
    await session.execute(
        delete(Chunk).where(Chunk.artifact_id == artifact_id)
    )

    # Create chunk records
    chunk_records = []
    for raw_chunk, embedding in zip(raw_chunks, embeddings):
        stable_id = _build_stable_id(
            sha256_prefix, raw_chunk["page_ref"], raw_chunk["chunk_idx"]
        )

        chunk = Chunk(
            id=generate_id(),
            artifact_id=artifact_id,
            stable_id=stable_id,
            text=raw_chunk["text"],
            page_ref=raw_chunk["page_ref"],
            slide_title=raw_chunk.get("slide_title"),
            embedding=embedding,
        )
        session.add(chunk)
        chunk_records.append(chunk)

    await session.flush()

    logger.info(
        "chunks_stored",
        artifact_id=artifact_id,
        count=len(chunk_records),
    )

    return chunk_records
