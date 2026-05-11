from __future__ import annotations


class RagComputerError(Exception):
    pass


class NotFoundError(RagComputerError):
    def __init__(self, resource: str, identifier: str) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")


class ValidationError(RagComputerError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ForbiddenError(RagComputerError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class UpstreamError(RagComputerError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ServerError(RagComputerError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
