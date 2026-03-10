"""Tests for embedding providers."""

from unittest.mock import MagicMock, patch

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
        with (
            patch(
                "app.services.settings_service.get_effective_setting",
                return_value="sentence_transformers",
            ),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.embedding_model = "all-MiniLM-L6-v2"
            provider = get_embedding_provider()

        assert isinstance(provider, SentenceTransformerProvider)

    def test_openai_returns_openai_provider(self):
        """openai backend returns OpenAIEmbeddingProvider."""
        from pydantic import SecretStr

        with (
            patch(
                "app.services.settings_service.get_effective_setting",
                return_value="openai",
            ),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.openai_api_key = SecretStr("test-key")
            provider = get_embedding_provider()

        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_ollama_returns_ollama_provider(self):
        """ollama backend returns OllamaEmbeddingProvider."""
        with (
            patch(
                "app.services.settings_service.get_effective_setting",
                return_value="ollama",
            ),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.ollama_base_url = "http://test:11434"
            provider = get_embedding_provider()

        assert isinstance(provider, OllamaEmbeddingProvider)
