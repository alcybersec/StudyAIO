"""Application configuration loaded from environment variables."""

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """StudyAIO application settings."""

    # Database
    database_url: str = "postgresql+asyncpg://studyaio:studyaio@db:5432/studyaio"
    database_url_sync: str = "postgresql://studyaio:studyaio@db:5432/studyaio"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800  # 30 minutes

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Public origin of the frontend. Used to build links that are emailed to
    # users (password reset, and any future magic link), so it must be the URL
    # the user's browser can reach — not the container hostname.
    app_base_url: str = "http://localhost:3001"

    # File storage
    data_dir: str = "/app/data"
    storage_backend: str = "local"  # "local" or "s3"

    # S3-compatible storage (used when storage_backend = "s3")
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: SecretStr = SecretStr("")
    s3_endpoint_url: str = ""  # For MinIO/LocalStack
    s3_prefix: str = ""  # Optional key prefix inside the bucket
    cdn_base_url: str = ""  # CDN URL for serving S3 files

    # Logging
    log_level: str = "INFO"
    log_format: str = "auto"  # "auto", "json", or "console"

    # Claude Code
    claude_code_path: str = "claude"
    claude_model: str = "opus"

    # Agent backend
    agent_backend: str = "claude_code"
    anthropic_api_key: SecretStr = SecretStr("")

    # OpenAI
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4o"

    # Z.ai (GLM) — OpenAI-compatible endpoint
    zai_api_key: SecretStr = SecretStr("")
    zai_model: str = "glm-5.3"
    zai_base_url: str = "https://api.z.ai/api/paas/v4/"
    # "disabled" by default: GLM's thinking mode roughly doubles output verbosity,
    # which blows the summarize stage's token cap before the response structure
    # completes (measured: 2/8 required sections, truncated mid-sentence, no
    # footer). Disabling it produces a complete, on-length response within the
    # existing cap. Set to "enabled" to restore GLM's default reasoning behavior.
    zai_thinking: str = "disabled"

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
    cookie_secure: bool = False
    max_upload_size_mb: int = 100
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # Rate limiting
    rate_limit_uploads: str = "10/minute"
    rate_limit_qa: str = "20/minute"

    # OpenAPI
    openapi_enabled: bool = True

    # Observability
    prometheus_enabled: bool = False

    # Backup
    backup_enabled: bool = False
    backup_schedule_hour: int = 2  # Hour of day (UTC) for daily backup
    backup_retention: int = 7

    # Demo mode
    demo_enabled: bool = False

    # Authentication
    jwt_secret_key: SecretStr = SecretStr("changeme-in-production-use-a-real-secret")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    self_hosted: bool = True
    # "open" | "invite" | "closed" — gates POST /api/auth/register
    registration_mode: str = "open"

    # Redis socket timeouts (seconds). Cache/event/OAuth-state writes are all
    # best-effort, so a slow or unreachable Redis must fail fast and degrade
    # rather than block the request. Without these the client waits forever.
    redis_socket_timeout: float = 2.0

    # Error monitoring (Sentry). Inert when sentry_dsn is empty.
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.0
    sentry_release: str = ""

    # Tier limits. 0 means unlimited. Pipeline AI calls count toward
    # *_max_ai_calls_per_day, and one upload costs about
    # PIPELINE_AI_CALLS_PER_UPLOAD calls (classify + summarize + flashcards + quiz).
    free_max_courses: int = 1
    free_max_uploads_per_month: int = 5
    free_max_ai_calls_per_day: int = 100
    pro_max_courses: int = 0
    pro_max_uploads_per_month: int = 0
    pro_max_ai_calls_per_day: int = 0

    # Instance-wide daily ceiling. 0 disables it. This is an operator cost
    # guard, so unlike the per-tier limits it applies to every tier and in
    # self-hosted mode too.
    global_max_ai_calls_per_day: int = 0
    global_max_ai_tokens_per_day: int = 0

    # Stripe billing
    stripe_api_key: SecretStr = SecretStr("")
    stripe_webhook_secret: SecretStr = SecretStr("")
    stripe_pro_price_id: str = ""
    stripe_portal_return_url: str = "http://localhost:3001/settings"

    # Notifications
    notifications_enabled: bool = False
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from_email: str = ""
    smtp_from_name: str = "StudyAIO"
    smtp_use_tls: bool = True

    # Web Push (VAPID)
    vapid_public_key: str = ""
    vapid_private_key: SecretStr = SecretStr("")
    vapid_admin_email: str = "admin@studyaio.local"

    # OAuth providers
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_calendar_scopes: str = "https://www.googleapis.com/auth/calendar"
    github_client_id: str = ""
    github_client_secret: SecretStr = SecretStr("")
    oauth_redirect_base_url: str = (
        ""  # e.g. "https://app.studyaio.com" — defaults to http://localhost:8000
    )

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

    @field_validator("registration_mode")
    @classmethod
    def _validate_registration_mode(cls, value: str) -> str:
        """Reject an unrecognized registration mode at startup.

        Without this, `REGISTRATION_MODE=invit` would fall through every check
        and silently behave as `open` — a typo would throw a closed beta open.
        """
        allowed = {"open", "invite", "closed"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"REGISTRATION_MODE must be one of {sorted(allowed)}, got {value!r}")
        return normalized


settings = Settings()
