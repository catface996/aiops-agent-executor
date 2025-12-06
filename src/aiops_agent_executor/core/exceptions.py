"""Custom exception classes for the application.

This module defines a hierarchical exception system for consistent error handling
across the application. All custom exceptions inherit from AppException.
"""

from typing import Any


class AppException(Exception):
    """Base exception class for all application errors.

    Attributes:
        message: Human-readable error message
        code: Machine-readable error code for client handling
        status_code: HTTP status code for API responses
        details: Additional error context
    """

    status_code: int = 500
    default_message: str = "An unexpected error occurred"
    default_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API response."""
        result = {
            "detail": self.message,
            "code": self.code,
        }
        if self.details:
            result["details"] = self.details
        return result


class NotFoundError(AppException):
    """Resource not found error (404)."""

    status_code = 404
    default_message = "Resource not found"
    default_code = "NOT_FOUND"

    def __init__(
        self,
        resource: str = "Resource",
        resource_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        super().__init__(message=message, **kwargs)


class BadRequestError(AppException):
    """Bad request error (400)."""

    status_code = 400
    default_message = "Invalid request"
    default_code = "BAD_REQUEST"


class ConflictError(AppException):
    """Resource conflict error (409)."""

    status_code = 409
    default_message = "Resource conflict"
    default_code = "CONFLICT"

    def __init__(
        self,
        resource: str = "Resource",
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        message = f"{resource} conflict"
        if reason:
            message = f"{resource} conflict: {reason}"
        super().__init__(message=message, **kwargs)


class ServiceUnavailableError(AppException):
    """Service unavailable error (503)."""

    status_code = 503
    default_message = "Service temporarily unavailable"
    default_code = "SERVICE_UNAVAILABLE"

    def __init__(
        self,
        service: str = "Service",
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        message = f"{service} is temporarily unavailable"
        if reason:
            message = f"{service} is temporarily unavailable: {reason}"
        super().__init__(message=message, **kwargs)


class InternalError(AppException):
    """Internal server error (500)."""

    status_code = 500
    default_message = "Internal server error"
    default_code = "INTERNAL_ERROR"


class ValidationError(BadRequestError):
    """Validation error for input data."""

    default_message = "Validation error"
    default_code = "VALIDATION_ERROR"


class EncryptionError(InternalError):
    """Encryption/decryption operation error."""

    default_message = "Encryption operation failed"
    default_code = "ENCRYPTION_ERROR"


class ProviderError(ServiceUnavailableError):
    """Base error for provider-related issues."""

    default_message = "Provider operation failed"
    default_code = "PROVIDER_ERROR"


class ProviderConnectionError(ProviderError):
    """Provider connection error."""

    default_code = "PROVIDER_CONNECTION_ERROR"

    def __init__(self, provider: str, reason: str | None = None, **kwargs: Any) -> None:
        message = f"Cannot connect to {provider}"
        if reason:
            message = f"Cannot connect to {provider}: {reason}"
        super().__init__(service=provider, reason=reason, **kwargs)
        self.message = message


class ProviderAuthError(ProviderError):
    """Provider authentication error."""

    status_code = 401
    default_code = "PROVIDER_AUTH_ERROR"

    def __init__(self, provider: str, **kwargs: Any) -> None:
        message = f"Authentication failed for {provider}"
        super().__init__(service=provider, **kwargs)
        self.message = message


class ProviderRateLimitError(ProviderError):
    """Provider rate limit error."""

    status_code = 429
    default_code = "PROVIDER_RATE_LIMIT"

    def __init__(self, provider: str, retry_after: int | None = None, **kwargs: Any) -> None:
        message = f"Rate limit exceeded for {provider}"
        if retry_after:
            message = f"Rate limit exceeded for {provider}. Retry after {retry_after} seconds"
        details = kwargs.pop("details", {})
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(service=provider, details=details, **kwargs)
        self.message = message
