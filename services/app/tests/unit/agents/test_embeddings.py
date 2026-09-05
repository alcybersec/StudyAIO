"""Tests for embedding providers."""

from unittest.mock import MagicMock, patch

import pytest

from app.agents.embeddings import (
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
    SentenceTransformerProvider,
    get_embedding_provider,
    reset_embedding_provider,
)


class TestSentenceTransformerProvider:
    """Tests for SentenceTransformerProvider."""

    def test_dimensions_default(self):
        """Default dimensions is 384."""
        provider = SentenceTransformerProvider()
        assert provider.dimensions == 384

    def test_empty_texts_returns_empty(self):
        """Empty input returns empty output."""
        provider = SentenceTransformerProvider()
        assert provider.embed_texts([]) == []


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider."""

    def test_dimensions_default(self):
        """Default dimensions is 1536."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        assert provider.dimensions == 1536

    def test_empty_texts_returns_empty(self):
        """Empty input returns empty output."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        assert provider.embed_texts([]) == []

    def test_calls_openai_api(self):
        """embed_texts calls OpenAI embeddings API."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")

        mock_item = MagicMock()
        mock_item.index = 0
        mock_item.embedding = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.data = [mock_item]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            result = provider.embed_texts(["hello"])

        assert result == [[0.1, 0.2, 0.3]]
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["hello"],
        )

    def test_sorts_by_index(self):
        """Results are sorted by index."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")

        item0 = MagicMock()
        item0.index = 1
        item0.embedding = [0.4, 0.5]
        item1 = MagicMock()
        item1.index = 0
        item1.embedding = [0.1, 0.2]
        mock_response = MagicMock()
        mock_response.data = [item0, item1]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            result = provider.embed_texts(["a", "b"])

        assert result == [[0.1, 0.2], [0.4, 0.5]]


class TestOllamaEmbeddingProvider:
    """Tests for OllamaEmbeddingProvider."""

    def test_dimensions_default(self):
        """Default dimensions is 768."""
        provider = OllamaEmbeddingProvider()
        assert provider.dimensions == 768

    def test_empty_texts_returns_empty(self):
        """Empty input returns empty output."""
        provider = OllamaEmbeddingProvider()
        assert provider.embed_texts([]) == []

    def test_calls_ollama_api(self):
        """embed_texts calls Ollama embed API."""
        provider = OllamaEmbeddingProvider(base_url="http://test:11434")

        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3]]
        mock_client = MagicMock()
        mock_client.embed.return_value = mock_response

        with patch("ollama.Client", return_value=mock_client):
            result = provider.embed_texts(["hello"])

        assert result == [[0.1, 0.2, 0.3]]
        mock_client.embed.assert_called_once_with(
            model="nomic-embed-text",
            input=["hello"],
        )


class TestGetEmbeddingProvider:
    """Tests for get_embedding_provider() factory."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_embedding_provider()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_embedding_provider()

    def test_default_returns_sentence_transformers(self):
        """Default backend returns SentenceTransformerProvider."""
        with patch("app.config.settings") as mock_settings:
            mock_settings.embedding_backend = "sentence_transformers"
            mock_settings.embedding_model = "all-MiniLM-L6-v2"
            mock_settings.embedding_dimensions = 384
            provider = get_embedding_provider()

        assert isinstance(provider, SentenceTransformerProvider)

    def test_openai_returns_openai_provider(self):
        """openai backend returns OpenAIEmbeddingProvider when dimensions agree."""
        from pydantic import SecretStr

        with patch("app.config.settings") as mock_settings:
            mock_settings.embedding_backend = "openai"
            mock_settings.openai_api_key = SecretStr("<test-placeholder>")
            mock_settings.embedding_dimensions = 1536
            provider = get_embedding_provider()

        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_ollama_returns_ollama_provider(self):
        """ollama backend returns OllamaEmbeddingProvider when dimensions agree."""
        with patch("app.config.settings") as mock_settings:
            mock_settings.embedding_backend = "ollama"
            mock_settings.ollama_base_url = "http://test:11434"
            mock_settings.embedding_dimensions = 768
            provider = get_embedding_provider()

        assert isinstance(provider, OllamaEmbeddingProvider)

    def test_backend_is_read_from_config_not_user_settings(self):
        """The backend is instance-wide — a per-user override cannot reach it.

        Issue #32: `embedding_backend` used to be resolved through
        `get_effective_setting`, which named a per-user layer that never
        applied to it. Nothing in this path may consult user settings.
        """
        with (
            patch("app.config.settings") as mock_settings,
            patch("app.services.settings_service.get_effective_setting") as mock_effective,
        ):
            mock_settings.embedding_backend = "sentence_transformers"
            mock_settings.embedding_model = "all-MiniLM-L6-v2"
            mock_settings.embedding_dimensions = 384
            get_embedding_provider()

        mock_effective.assert_not_called()


class TestDimensionGuard:
    """A provider whose vectors cannot fit the column is refused up front.

    Before this guard, `EMBEDDING_BACKEND=openai` on the shipped `vector(384)`
    schema meant OpenAI was called and billed, pgvector rejected the INSERT,
    and Celery retried twice — three paid runs, zero rows stored (issue #32).
    """

    def setup_method(self):
        reset_embedding_provider()

    def teardown_method(self):
        reset_embedding_provider()

    def test_openai_against_384_column_raises_before_any_call(self):
        """The documented failure: 1536-dim backend, 384-dim column."""
        from pydantic import SecretStr

        from app.core.exceptions import ConfigurationError

        with (
            patch("app.config.settings") as mock_settings,
            patch("openai.OpenAI") as mock_openai,
        ):
            mock_settings.embedding_backend = "openai"
            mock_settings.openai_api_key = SecretStr("<test-placeholder>")
            mock_settings.embedding_dimensions = 384

            with pytest.raises(ConfigurationError) as exc_info:
                get_embedding_provider()

        # No client was constructed, so nothing was sent and nothing was billed.
        mock_openai.assert_not_called()

        message = str(exc_info.value)
        assert "1536" in message
        assert "384" in message
        assert "EMBEDDING_BACKEND" in message
        assert "EMBEDDING_DIMENSIONS" in message

    def test_ollama_against_384_column_raises(self):
        """768-dim backend against the shipped 384-dim column."""
        from app.core.exceptions import ConfigurationError

        with patch("app.config.settings") as mock_settings:
            mock_settings.embedding_backend = "ollama"
            mock_settings.ollama_base_url = "http://test:11434"
            mock_settings.embedding_dimensions = 384

            with pytest.raises(ConfigurationError, match="768"):
                get_embedding_provider()

    def test_failed_construction_does_not_poison_the_singleton(self):
        """A refused provider is not cached, so a fixed config recovers."""
        from app.core.exceptions import ConfigurationError

        with patch("app.config.settings") as mock_settings:
            mock_settings.embedding_backend = "ollama"
            mock_settings.ollama_base_url = "http://test:11434"
            mock_settings.embedding_dimensions = 384
            with pytest.raises(ConfigurationError):
                get_embedding_provider()

        with patch("app.config.settings") as mock_settings:
            mock_settings.embedding_backend = "sentence_transformers"
            mock_settings.embedding_model = "all-MiniLM-L6-v2"
            mock_settings.embedding_dimensions = 384
            provider = get_embedding_provider()

        assert isinstance(provider, SentenceTransformerProvider)
