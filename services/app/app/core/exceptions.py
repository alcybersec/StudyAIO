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


class SessionRevokedError(AuthenticationError):
    """Raised when a token predates the user's session cutoff.

    A distinct subclass so that callers which deliberately tolerate a failed
    login (self-hosted's default-admin fallback) can still refuse a session
    the user explicitly revoked by resetting or changing their password.
    """

    pass


class AuthorizationError(StudyAIOError):
    """Raised when a user lacks permission for an action."""

    pass


class UserExistsError(StudyAIOError):
    """Raised when registration fails because email or username already exists."""

    def __init__(self, field: str):
        self.field = field
        super().__init__(f"A user with this {field} already exists")


class LastAdminError(StudyAIOError):
    """Raised when a change would leave the instance with no active admin.

    Covers deletion, demotion and deactivation alike: any of them applied to the
    last active admin locks everyone out with no recovery short of SQL.
    """

    def __init__(self, action: str = "change"):
        self.action = action
        super().__init__(
            f"Cannot {action} the last active admin — the instance would have "
            "no one able to administer it."
        )


class ProviderCredentialError(StudyAIOError):
    """Raised when a user's chosen AI provider has no credential of their own.

    Selecting a provider explicitly means "bill my account". Falling back to
    the instance credential would hand the operator's key to whoever asked,
    which is exactly the leak this refuses to reintroduce.
    """

    def __init__(self, backend: str, credential_key: str):
        self.backend = backend
        self.credential_key = credential_key
        super().__init__(
            f"No credential stored for provider '{backend}'. Add your "
            f"{credential_key} under Settings > AI Providers, or switch back to "
            f"StudyAIO provided."
        )


class GlobalCeilingError(StudyAIOError):
    """Raised when the instance-wide daily AI ceiling is reached.

    Unlike per-user quotas this is an operator cost guard, so it applies to
    every tier and in self-hosted mode too.
    """

    def __init__(self, resource: str, limit: int, retry_after_seconds: int):
        self.resource = resource
        self.limit = limit
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"This instance has reached its daily {resource} ceiling of {limit}. "
            "Service resumes at 00:00 UTC."
        )


class InviteError(StudyAIOError):
    """Raised when an invite code is missing, unknown, expired, or used up."""

    pass


class RegistrationClosedError(StudyAIOError):
    """Raised when registration is disabled entirely (REGISTRATION_MODE=closed)."""

    def __init__(self, message: str = "Registration is currently closed"):
        super().__init__(message)


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


class CalendarSyncError(StudyAIOError):
    """Raised when Google Calendar sync fails."""

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


class ArtifactBusyError(StudyAIOError):
    """Raised when an operation requires an artifact that is not mid-pipeline."""
