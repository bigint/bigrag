"""bigRAG - Python client for the bigRAG vector database."""

from bigrag.client import AsyncBigRAG, BigRAG
from bigrag.errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    BigRAGError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)
from bigrag.namespace import AsyncNamespace, Namespace
from bigrag.types import (
    Document,
    NamespaceListResponse,
    NamespaceMetadata,
    NamespaceSummary,
    QueryResponse,
    QueryRow,
    WriteResponse,
)

__all__ = [
    "BigRAG",
    "AsyncBigRAG",
    "Namespace",
    "AsyncNamespace",
    "BigRAGError",
    "APIError",
    "BadRequestError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "InternalServerError",
    "APIConnectionError",
    "APITimeoutError",
    "Document",
    "WriteResponse",
    "QueryResponse",
    "QueryRow",
    "NamespaceMetadata",
    "NamespaceListResponse",
    "NamespaceSummary",
]

__version__ = "0.1.0"
