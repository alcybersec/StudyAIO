"""Application configuration loaded from environment variables."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """StudyAIO application settings."""

    # Database
    database_url: str = "postgresql+asyncpg://studyaio:studyaio@db:5432/studyaio"
    database_url_sync: str = "postgresql://studyaio:studyaio@db:5432/studyaio"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # File storage
    data_dir: str = "/app/data"

    # Logging
    log_level: str = "INFO"

    # Claude Code
    claude_code_path: str = "claude"
    claude_model: str = "opus"

    # Agent backend
    agent_backend: str = "claude_code"
    anthropic_api_key: SecretStr = SecretStr("")

    # OpenAI
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4o"

    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"

    # Embedding backend
    embedding_backend: str = "sentence_transformers"

    # Pipeline tuning
    classification_confidence_threshold: float = 0.7
    flashcard_count_per_week: int = 15
    quiz_question_count_per_week: int = 8
    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    search_top_k: int = 10

    # Security
    max_upload_size_mb: int = 100
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Rate limiting
    rate_limit_uploads: str = "10/minute"
    rate_limit_qa: str = "20/minute"

    # Authentication
    jwt_secret_key: SecretStr = SecretStr("changeme-in-production-use-a-real-secret")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    self_hosted: bool = True

    # OAuth providers
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    github_client_id: str = ""
    github_client_secret: SecretStr = SecretStr("")

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def uploads_dir(self) -> str:
        return f"{self.data_dir}/uploads"

    @property
    def extractions_dir(self) -> str:
        return f"{self.data_dir}/extractions"

    @property
    def summaries_dir(self) -> str:
        return f"{self.data_dir}/summaries"


settings = Settings()
