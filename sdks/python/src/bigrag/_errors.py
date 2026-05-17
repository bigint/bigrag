"""Error hierarchy for the bigRAG Python SDK."""

from __future__ import annotations


class BigRAGError(Exception):
    """Base exception for all bigRAG SDK errors."""


class APIError(BigRAGError):
    """An error response from the bigRAG API."""

    status: int
    code: str | None

    def __init__(self, status: int, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class BadRequestError(APIError):
    """HTTP 400 Bad Request."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(400, message, code)


class AuthenticationError(APIError):
    """HTTP 401 Unauthorized."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(401, message, code)


class PermissionDeniedError(APIError):
    """HTTP 403 Forbidden."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(403, message, code)


class NotFoundError(APIError):
    """HTTP 404 Not Found."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(404, message, code)


class RateLimitError(APIError):
    """HTTP 429 Too Many Requests."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(429, message, code)


class InternalServerError(APIError):
    """HTTP 500 Internal Server Error."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(500, message, code)


class APIConnectionError(BigRAGError):
    """A connection error occurred while communicating with the API."""

    def __init__(self, message: str = "Connection error") -> None:
        super().__init__(message)


class APITimeoutError(BigRAGError):
    """The request timed out."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message)


_STATUS_MAP: dict[int, type[APIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    429: RateLimitError,
    500: InternalServerError,
}


def error_for_status(status: int, message: str, code: str | None = None) -> APIError:
    """Return the appropriate :class:`APIError` subclass for *status*."""
    cls = _STATUS_MAP.get(status)
    if cls is not None:
        return cls(message, code)
    return APIError(status, message, code)
