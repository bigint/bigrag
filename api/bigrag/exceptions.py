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


class IngestionError(BigRAGError):
    """Document ingestion failed."""

    def __init__(self, message: str, *, permanent: bool = False) -> None:
        self.permanent = permanent
        super().__init__(message)


class EncryptionError(BigRAGError):
    """Encryption/decryption operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class QueueFullError(BigRAGError):
    """Ingestion queue is at capacity."""

    def __init__(self) -> None:
        super().__init__("Ingestion queue is full. Try again later.")
