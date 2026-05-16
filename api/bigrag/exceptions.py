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
    pass


class ServerError(BigRAGError):
    pass
