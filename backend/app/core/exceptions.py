from __future__ import annotations


class CeleriusError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class WorkflowError(CeleriusError):
    """Raised when an artifact status transition is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="WORKFLOW_ERROR")


class ArtifactLockedError(CeleriusError):
    """Raised when attempting to modify a LOCKED artifact."""

    def __init__(self) -> None:
        super().__init__(
            "This artifact is locked and cannot be modified. Create an amendment instead.",
            code="ARTIFACT_LOCKED",
        )


class TenantMismatchError(CeleriusError):
    """Raised when a resource belongs to a different organization."""

    def __init__(self) -> None:
        super().__init__("Resource not found.", code="NOT_FOUND")


class ValidationError(CeleriusError):
    """Raised on business-level validation failures (not Pydantic)."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR")


class AuthenticationError(CeleriusError):
    """Raised on authentication failures."""

    def __init__(self, message: str = "Authentication failed.") -> None:
        super().__init__(message, code="AUTHENTICATION_ERROR")


class RateLimitError(CeleriusError):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after_seconds: int = 900) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Too many attempts. Try again in {retry_after_seconds} seconds.",
            code="RATE_LIMIT_EXCEEDED",
        )
