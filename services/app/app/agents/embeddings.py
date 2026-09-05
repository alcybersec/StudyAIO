"""Embedding provider abstraction for vector search.

This module defines the EmbeddingProvider ABC and implementations using
sentence-transformers (local), OpenAI API, and Ollama. The provider is
separate from AgentAdapter because embeddings are deterministic and
don't require generative AI.
"""

from abc import ABC, abstractmethod

import structlog

logger = structlog.get_logger()


class EmbeddingProvider(ABC):
    """Abstract interface for generating text embeddings.

    Implementations may use local models (sentence-transformers),
    cloud APIs (OpenAI), or local inference servers (Ollama).
    Swappable without changing pipeline or search code.
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


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using OpenAI's text-embedding API.

    Uses text-embedding-3-small by default (1536 dimensions).
    """

    def __init__(self, api_key: str = "", model: str = "text-embedding-3-small"):
        self._api_key = api_key
        self._model = model
        self._dimensions = 1536

    @property
    def dimensions(self) -> int:
        """Return embedding dimensionality (1536 for text-embedding-3-small)."""
        return self._dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI API.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of float vectors (1536-dim each).
        """
        if not texts:
            return []

        from openai import OpenAI

        client = OpenAI(api_key=self._api_key)
        logger.info(
            "openai_embedding_call",
            model=self._model,
            num_texts=len(texts),
        )

        response = client.embeddings.create(
            model=self._model,
            input=texts,
        )

        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using Ollama's embed API.

    Uses nomic-embed-text by default (768 dimensions).
    """

    def __init__(self, base_url: str = "http://ollama:11434", model: str = "nomic-embed-text"):
        self._base_url = base_url
        self._model = model
        self._dimensions = 768

    @property
    def dimensions(self) -> int:
        """Return embedding dimensionality (768 for nomic-embed-text)."""
        return self._dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Ollama embed API.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of float vectors (768-dim each).
        """
        if not texts:
            return []

        from ollama import Client

        client = Client(host=self._base_url)
        logger.info(
            "ollama_embedding_call",
            model=self._model,
            num_texts=len(texts),
        )

        response = client.embed(
            model=self._model,
            input=texts,
        )

        return response.embeddings


# Singleton instance — reuse across calls to avoid reloading the model.
_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Get the configured embedding provider singleton.

    The backend is instance-wide, read straight from `EMBEDDING_BACKEND`. It is
    deliberately **not** a per-user setting, and this is not a gap waiting to be
    filled — see the note below.

    Backends:
    - "sentence_transformers": local SentenceTransformerProvider (default, 384)
    - "openai": OpenAI text-embedding-3-small (1536)
    - "ollama": Ollama nomic-embed-text (768)

    The constructed provider's dimensionality must match
    `EMBEDDING_DIMENSIONS`, which in turn must match the `vector(N)` column the
    rows land in. A mismatch is refused here, before the provider is ever
    called.

    Returns:
        An EmbeddingProvider implementation.

    Raises:
        ConfigurationError: If the backend's output dimensionality does not
            match `EMBEDDING_DIMENSIONS`.
    """
    # Why the embedding backend is operator-only, and must stay that way
    # (issue #32):
    #
    # A per-user embedding provider is incoherent, not merely unimplemented.
    # Vectors from different models are not comparable and do not share a
    # column: `chunks.embedding` is a single `vector(384)`, and a query vector
    # is compared against every row in it. A user switching provider would need
    # their entire corpus re-indexed, and every query embedded by the same model
    # that embedded their documents — which in turn needs a provenance column
    # recording the producing model, a model-scoped filter on every similarity
    # query, and a re-index pipeline. That is a feature with a schema change
    # behind it, not a settings toggle.
    #
    # So: no dropdown. Offering one promises a per-user choice that cannot be
    # honoured, and before this guard existed, selecting `openai` meant OpenAI
    # was called and billed, the INSERT was rejected by pgvector, and Celery
    # retried it twice — three paid runs, zero rows stored.
    global _provider
    if _provider is None:
        from app.config import settings

        backend = settings.embedding_backend

        if backend == "openai":
            api_key = settings.openai_api_key.get_secret_value()
            provider: EmbeddingProvider = OpenAIEmbeddingProvider(api_key=api_key)
        elif backend == "ollama":
            provider = OllamaEmbeddingProvider(
                base_url=settings.ollama_base_url,
            )
        else:
            provider = SentenceTransformerProvider(
                model_name=settings.embedding_model,
            )

        _check_dimensions(backend, provider, settings.embedding_dimensions)
        _provider = provider

    return _provider


def _check_dimensions(backend: str, provider: EmbeddingProvider, expected: int) -> None:
    """Refuse a provider whose vectors cannot fit the configured column.

    Checked at construction rather than at insert time because the insert is
    downstream of a paid API call: OpenAI bills for the embeddings, pgvector
    then rejects the row for its dimensionality, and the index task retries.
    Failing here costs nothing and names what to change.

    Note this checks the provider's *declared* dimensionality.
    `SentenceTransformerProvider` re-reads its true value once the model
    loads, so pointing `EMBEDDING_MODEL` at a non-384 local model is still
    caught only at insert time — no money is at stake on that path.

    Args:
        backend: The configured `EMBEDDING_BACKEND` value, for the message.
        provider: The freshly constructed provider.
        expected: `EMBEDDING_DIMENSIONS`, which must match the pgvector column.

    Raises:
        ConfigurationError: If the two disagree.
    """
    from app.core.exceptions import ConfigurationError

    if provider.dimensions == expected:
        return

    raise ConfigurationError(
        f"EMBEDDING_BACKEND={backend!r} produces {provider.dimensions}-dimensional "
        f"vectors, but EMBEDDING_DIMENSIONS is {expected}. They must agree, and "
        f"both must match the vector(N) column embeddings are stored in. Either "
        f"set EMBEDDING_BACKEND back to a {expected}-dimensional backend, or "
        f"migrate the chunks.embedding and concepts.embedding columns to "
        f"{provider.dimensions} dimensions, set EMBEDDING_DIMENSIONS to match, "
        f"and re-index every artifact."
    )


def reset_embedding_provider() -> None:
    """Reset the singleton provider (for testing or config change)."""
    global _provider
    _provider = None
