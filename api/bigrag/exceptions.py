from __future__ import annotations


class BigRAGError(Exception):
    pass


class NotFoundError(BigRAGError):
    def __init__(self, resource: str, identifier: str) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")


class ValidationError(BigRAGError):
    pass


class ForbiddenError(BigRAGError):
    pass


class UpstreamError(BigRAGError):
    code = "upstream_error"
    default_public_message = "Upstream provider error"

    def __init__(self, message: str, *, public_message: str | None = None) -> None:
        super().__init__(message)
        self.public_message = (
            public_message if public_message is not None else self.default_public_message
        )


class ServerError(BigRAGError):
    code = "server_error"
    default_public_message = "Internal server error"

    def __init__(self, message: str, *, public_message: str | None = None) -> None:
        super().__init__(message)
        self.public_message = (
            public_message if public_message is not None else self.default_public_message
        )
