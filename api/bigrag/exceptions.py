"""Business logic exceptions for bigRAG.

These replace raw HTTPException usage in services and provide
structured error information that routers translate to HTTP responses.
"""

from __future__ import annotations


class BigRAGError(Exception):
    """Base exception for all bigRAG errors."""


class NotFoundError(BigRAGError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")


class ConflictError(BigRAGError):
    """Resource already exists or conflicts with existing state."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ValidationError(BigRAGError):
    """Input validation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
