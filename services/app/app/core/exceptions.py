"""Custom exception classes for StudyAIO."""


class StudyAIOError(Exception):
    """Base exception for all StudyAIO errors."""

    pass


class DuplicateFileError(StudyAIOError):
    """Raised when an uploaded file already exists (same SHA-256)."""

    def __init__(self, sha256: str, existing_artifact_id: str):
        self.sha256 = sha256
        self.existing_artifact_id = existing_artifact_id
        super().__init__(
            f"File with SHA-256 {sha256[:16]}... already exists as artifact {existing_artifact_id}"
        )


class ExtractionError(StudyAIOError):
    """Raised when file content extraction fails."""

    pass


class AgentError(StudyAIOError):
    """Raised when an AI agent call fails."""

    pass


class PipelineError(StudyAIOError):
    """Raised when a pipeline stage fails."""

    pass


class ClassificationError(StudyAIOError):
    """Raised when lecture classification fails."""

    pass


class SummarizationError(StudyAIOError):
    """Raised when summary generation fails."""

    pass


class IndexingError(StudyAIOError):
    """Raised when chunk indexing or embedding generation fails."""

    pass


class AssetGenerationError(StudyAIOError):
    """Raised when flashcard or quiz generation fails."""

    pass


class CourseOpsError(StudyAIOError):
    """Raised when a CourseOps operation fails."""

    pass


class AuthenticationError(StudyAIOError):
    """Raised when authentication fails (invalid credentials, expired token, etc.)."""

    pass


class AuthorizationError(StudyAIOError):
    """Raised when a user lacks permission for an action."""

    pass


class UserExistsError(StudyAIOError):
    """Raised when registration fails because email or username already exists."""

    def __init__(self, field: str):
        self.field = field
        super().__init__(f"A user with this {field} already exists")


class QuotaExceededError(StudyAIOError):
    """Raised when a user exceeds their tier's usage quota."""

    def __init__(self, resource: str, limit: int, period: str):
        self.resource = resource
        self.limit = limit
        self.period = period
        super().__init__(
            f"Quota exceeded: {resource} limit is {limit} per {period}. "
            "Upgrade to Pro for unlimited access."
        )


class NotificationError(StudyAIOError):
    """Raised when a notification delivery fails."""

    pass


class TelegramLinkError(StudyAIOError):
    """Raised when Telegram account linking fails."""

    pass


class DemoRestrictionError(StudyAIOError):
    """Raised when a demo user attempts a write operation."""

    def __init__(self, message: str = "Demo account — read-only access"):
        self.message = message
        super().__init__(message)


class ReviewRequiredError(StudyAIOError):
    """Raised when a pipeline stage needs human review to proceed."""

    def __init__(self, review_type: str, entity_type: str, entity_id: str, reason: str):
        self.review_type = review_type
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.reason = reason
        super().__init__(f"Review required ({review_type}): {reason}")
