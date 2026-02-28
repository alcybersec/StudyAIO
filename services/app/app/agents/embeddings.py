"""Embedding provider abstraction for vector search.

This module defines the EmbeddingProvider ABC and a local implementation
using sentence-transformers. The provider is separate from AgentAdapter
because embeddings are deterministic and don't require generative AI.
"""

from abc import ABC, abstractmethod

import structlog

logger = structlog.get_logger()


class EmbeddingProvider(ABC):
    """Abstract interface for generating text embeddings.

    Implementations may use local models (sentence-transformers),
    cloud APIs (OpenAI, Voyage AI), or other backends. Swappable
    without changing pipeline or search code.
    """

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Number of dimensions in the output embeddings."""
        ...

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of float vectors, one per input text.
        """
        ...


class SentenceTransformerProvider(EmbeddingProvider):
    """Local embedding provider using sentence-transformers.

    Loads `all-MiniLM-L6-v2` (384 dimensions, ~90MB) on first call.
    The model is cached for reuse across calls within the same process.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._dimensions = 384

    @property
    def dimensions(self) -> int:
        """Return embedding dimensionality (384 for MiniLM)."""
        return self._dimensions

    def _load_model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("loading_embedding_model", model=self._model_name)
            self._model = SentenceTransformer(self._model_name)
            self._dimensions = self._model.get_sentence_embedding_dimension()
            logger.info(
                "embedding_model_loaded",
                model=self._model_name,
                dimensions=self._dimensions,
            )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using sentence-transformers.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of float vectors (384-dim each).
        """
        if not texts:
            return []

        self._load_model()
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]


# Singleton instance — reuse across calls to avoid reloading the model.
_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Get the configured embedding provider singleton.

    Returns:
        An EmbeddingProvider implementation.
    """
    global _provider
    if _provider is None:
        from app.config import settings

        _provider = SentenceTransformerProvider(
            model_name=settings.embedding_model,
        )
    return _provider
