from __future__ import annotations


class BigRAGError(Exception):
    pass


class APIError(BigRAGError):
    status: int
    code: str | None

    def __init__(self, status: int, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class BadRequestError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(400, message, code)


class AuthenticationError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(401, message, code)


class PermissionDeniedError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(403, message, code)


class NotFoundError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(404, message, code)


class ConflictError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(409, message, code)


class PayloadTooLargeError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(413, message, code)


class UnprocessableEntityError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(422, message, code)


class RateLimitError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(429, message, code)


class InternalServerError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(500, message, code)


class BadGatewayError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(502, message, code)


class ServiceUnavailableError(APIError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(503, message, code)


class APIConnectionError(BigRAGError):
    def __init__(self, message: str = "Connection error") -> None:
        super().__init__(message)


class APITimeoutError(BigRAGError):
    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message)


_STATUS_MAP: dict[int, type[APIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    413: PayloadTooLargeError,
    422: UnprocessableEntityError,
    429: RateLimitError,
    500: InternalServerError,
    502: BadGatewayError,
    503: ServiceUnavailableError,
}


def error_for_status(status: int, message: str, code: str | None = None) -> APIError:
    cls = _STATUS_MAP.get(status)
    if cls is not None:
        return cls(message, code)
    return APIError(status, message, code)
