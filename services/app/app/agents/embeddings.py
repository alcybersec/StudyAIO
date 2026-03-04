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

    Reads embedding_backend from settings:
    - "sentence_transformers": local SentenceTransformerProvider (default)
    - "openai": OpenAI text-embedding-3-small
    - "ollama": Ollama nomic-embed-text

    Returns:
        An EmbeddingProvider implementation.
    """
    global _provider
    if _provider is None:
        from app.config import settings
        from app.services.settings_service import get_effective_setting

        backend = get_effective_setting("embedding_backend")

        if backend == "openai":
            api_key = settings.openai_api_key.get_secret_value()
            _provider = OpenAIEmbeddingProvider(api_key=api_key)
        elif backend == "ollama":
            _provider = OllamaEmbeddingProvider(
                base_url=settings.ollama_base_url,
            )
        else:
            _provider = SentenceTransformerProvider(
                model_name=settings.embedding_model,
            )

    return _provider


def reset_embedding_provider() -> None:
    """Reset the singleton provider (for testing or config change)."""
    global _provider
    _provider = None
