"""Application configuration loaded from environment variables."""

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
