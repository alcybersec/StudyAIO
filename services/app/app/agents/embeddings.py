"""Embedding provider abstraction for vector search.

This module defines the EmbeddingProvider ABC and implementations using
sentence-transformers (local), OpenAI API, and Ollama. The provider is
separate from AgentAdapter because embeddings are deterministic and
don't require generative AI.

Embeddings are AI calls under floor 3; see
docs/adr/0005-floor3-embedding-gateway.md for the gateway and its allowlist.
"""

import asyncio
import contextvars
import math
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

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

    @abstractmethod
    def preload(self) -> None:
        """Do the expensive one-time setup now instead of on first use.

        Called from the API's startup check (`app.main`) so that a provider
        which cannot work *at all* says so in the log at boot, rather than
        failing inside a request. Constructing a provider proves nothing on its
        own — see `SentenceTransformerProvider.preload` — so there has to be a
        second, explicit step, and this is it.

        Abstract with no default on purpose. A no-op is the right answer for the
        API-backed providers, but it is a *decision* — the only honest probe of
        a remote service is a real call to it, which is billable for OpenAI and
        a network dependency on the start path for both — and a new provider
        should have to make that decision rather than inherit it silently.

        Raises:
            Exception: Whatever the underlying model loader raises. Callers are
                expected to catch and report; this must never be the reason a
                process refuses to start.
        """
        ...


MINILM_MAX_SEQ_LENGTH = 256


class SentenceTransformerProvider(EmbeddingProvider):
    """Local embedding provider using sentence-transformers.

    Loads `all-MiniLM-L6-v2` (384 dimensions, ~90MB) on first call.
    The model is cached for reuse across calls within the same process.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._dimensions = 384
        # `embed_texts` runs on worker threads (see `aembed_texts`): one load, and one
        # encode at a time so concurrent callers queue instead of oversubscribing CPUs.
        self._load_lock = threading.Lock()
        self._encode_lock = threading.Lock()

    @property
    def dimensions(self) -> int:
        """Return embedding dimensionality (384 for MiniLM)."""
        return self._dimensions

    def _input_window(self) -> int:
        """MiniLM's `max_seq_length`: 256 word pieces, [CLS] and [SEP] included.

        Measured on all-MiniLM-L6-v2 (GL#17). Read from the loaded model when
        there is one, so a different `EMBEDDING_MODEL` is honoured.
        """
        if self._model is not None:
            return int(self._model.max_seq_length)
        return MINILM_MAX_SEQ_LENGTH

    def _word_tokens(self, words: list[str]) -> list[int]:
        """Count word pieces with the model's own tokenizer (loads the model)."""
        if not words:
            return []
        self._load_model()
        # The fast tokenizer is not safe to share across threads ("Already borrowed"),
        # and `encode` (which uses it) runs on worker threads: take the encode lock.
        with self._encode_lock:
            ids = self._model.tokenizer(words, add_special_tokens=False)["input_ids"]
        return [max(1, len(i)) for i in ids]

    def _load_model(self):
        """Lazy-load the sentence-transformers model (thread-safe, loads once)."""
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            from sentence_transformers import SentenceTransformer

            logger.info("loading_embedding_model", model=self._model_name)
            model = SentenceTransformer(self._model_name)
            self._dimensions = model.get_sentence_embedding_dimension()
            # Publish last: another thread seeing `_model` set must see a usable model.
            self._model = model
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
        with self._encode_lock:
            embeddings = self._model.encode(texts, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]

    def preload(self) -> None:
        """Load the model now, so a broken cache is a startup error.

        This is the whole point of the startup check. `__init__` only records a
        model name; nothing touches the filesystem until here, which is why the
        API could construct this provider happily for six months while every
        embedding call in the process failed (issue #44).
        """
        self._load_model()


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

    def preload(self) -> None:
        """Nothing to load — deliberately.

        Probing this backend means embedding something through OpenAI, which is
        a billed request. A startup check that costs money on every boot is
        worse than the failure it would find, so a broken key or an unreachable
        API surfaces at first use instead, in front of the caller.
        """

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

    def preload(self) -> None:
        """Nothing to load — deliberately.

        Ollama runs in its own container, on its own schedule. Reaching for it
        during API startup would couple this process's boot to another
        service's, and a check that has to wait on the network is a check that
        delays every restart.
        """

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


#: Bounded pool for blocking embedding calls made from async code. Two threads: the
#: local encode is serialised by the provider anyway, and the API backends are I/O.
_EMBED_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="embed")


async def aembed_texts(provider: EmbeddingProvider, texts: list[str]) -> list[list[float]]:
    """Embed `texts` on a worker thread so the event loop keeps running.

    `embed_texts` is synchronous (and CPU-bound for the local model: seconds for a
    lecture's chunks), and ADR 0005 pins the `EmbeddingProvider` surface, so async
    callers go through this module function rather than a new provider method. It
    is the same provider obtained from `get_embedding_provider`, called the same
    way, only not on the loop thread. The caller's contextvars (structlog bindings)
    are carried across.

    Args:
        provider: The embedding provider.
        texts: Texts to embed.

    Returns:
        One vector per text; `[]` for no texts (the provider is not touched).
    """
    if not texts:
        return []
    ctx = contextvars.copy_context()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_EMBED_EXECUTOR, ctx.run, provider.embed_texts, texts)


# Context windows of the non-local backends, in their own tokens.
_OPENAI_WINDOW = 8191  # text-embedding-3-small
_OLLAMA_WINDOW = 2048  # nomic-embed-text at Ollama's default context
_UNKNOWN_WINDOW = 512


def input_window(provider: EmbeddingProvider) -> int:
    """Longest input, in the provider's own tokens, that is embedded in full.

    Anything past this is silently truncated by the model, so text beyond it is
    unsearchable; the chunker sizes chunks from it (GL#17). A module function and
    not an `EmbeddingProvider` method on purpose: ADR 0005 pins that interface's
    public surface, and this reads a model property rather than embedding.

    Args:
        provider: The embedding provider.

    Returns:
        The window (256 for MiniLM, measured from the loaded model's
        `max_seq_length`).
    """
    hook = getattr(provider, "_input_window", None)
    if callable(hook):
        return int(hook())
    if isinstance(provider, OpenAIEmbeddingProvider):
        return _OPENAI_WINDOW
    if isinstance(provider, OllamaEmbeddingProvider):
        return _OLLAMA_WINDOW
    return _UNKNOWN_WINDOW


def count_word_tokens(provider: EmbeddingProvider, words: list[str]) -> list[int]:
    """Token count of each whitespace-delimited word in the provider's tokenizer.

    Word-piece and BPE tokenizers split on whitespace first, so a text's token
    count is the sum of its words' counts and the chunker can size windows in one
    pass. Providers without a local tokenizer fall back to ~4 chars/token.

    Args:
        provider: The embedding provider.
        words: Whitespace-free words.

    Returns:
        One count (>= 1) per word.
    """
    hook = getattr(provider, "_word_tokens", None)
    if callable(hook):
        return list(hook(words))
    return heuristic_word_tokens(words)


def heuristic_word_tokens(words: list[str]) -> list[int]:
    """~4 chars per token, for when no tokenizer is available."""
    return [max(1, math.ceil(len(w) / 4)) for w in words]


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
