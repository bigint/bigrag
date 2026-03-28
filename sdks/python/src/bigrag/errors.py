"""Error types for the bigRAG Python SDK."""

from __future__ import annotations


class BigRAGError(Exception):
    """Base exception for all bigRAG errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class APIError(BigRAGError):
    """Error returned by the bigRAG API."""

    def __init__(
        self,
        status_code: int,
        message: str,
        code: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(status_code={self.status_code}, "
            f"message={self.message!r}, code={self.code!r})"
        )


class BadRequestError(APIError):
    """400 Bad Request."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(400, message, code)


class AuthenticationError(APIError):
    """401 Unauthorized."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(401, message, code)


class NotFoundError(APIError):
    """404 Not Found."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(404, message, code)


class RateLimitError(APIError):
    """429 Too Many Requests."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(429, message, code)


class InternalServerError(APIError):
    """500 Internal Server Error."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(500, message, code)


class APIConnectionError(BigRAGError):
    """Raised when the client cannot connect to the API."""

    def __init__(self, message: str = "Connection error") -> None:
        super().__init__(message)


class APITimeoutError(BigRAGError):
    """Raised when a request times out."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message)


_STATUS_MAP: dict[int, type[APIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    404: NotFoundError,
    429: RateLimitError,
    500: InternalServerError,
}


def raise_for_status(status_code: int, body: dict | str) -> None:
    """Raise an appropriate APIError for a non-2xx status code."""
    if isinstance(body, dict):
        message = body.get("error", body.get("message", str(body)))
        code = body.get("code")
    else:
        message = body
        code = None

    exc_class = _STATUS_MAP.get(status_code, APIError)
    if exc_class is APIError:
        raise APIError(status_code, message, code)
    raise exc_class(message, code)
