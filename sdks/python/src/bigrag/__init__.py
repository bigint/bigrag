"""bigRAG - Python client for the bigRAG RAG platform."""

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
from bigrag.types import (
    Collection,
    CollectionListResponse,
    Document,
    DocumentListResponse,
    QueryResponse,
    QueryResult,
)

__all__ = [
    "BigRAG",
    "AsyncBigRAG",
    "BigRAGError",
    "APIError",
    "BadRequestError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "InternalServerError",
    "APIConnectionError",
    "APITimeoutError",
    "Collection",
    "CollectionListResponse",
    "Document",
    "DocumentListResponse",
    "QueryResponse",
    "QueryResult",
]

__version__ = "0.2.0"
