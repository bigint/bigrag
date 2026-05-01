"""bigRAG Python SDK."""

from __future__ import annotations

from bigrag._client import BigRAG, CollectionClient
from bigrag._core import BigRAGCore
from bigrag._errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    BigRAGError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
    error_for_status,
)
from bigrag._files import FileInput, normalize_file_input
from bigrag._sse import parse_sse_stream
from bigrag._version import __version__
from bigrag.resources import (
    AdminApiKeysResource,
    AdminAuditResource,
    AdminEmbeddingPresetsResource,
    AdminMcpServersResource,
    AdminResource,
    AdminUsersResource,
    AuthResource,
    CollectionsResource,
    DocumentsResource,
    EvaluationsResource,
    QueryResource,
    VectorsResource,
    WebhooksResource,
)
from bigrag.types import *  # noqa: F401, F403

__all__ = [
    # Client
    "BigRAG",
    "BigRAGCore",
    "CollectionClient",
    "__version__",
    # Errors
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "BadRequestError",
    "BigRAGError",
    "InternalServerError",
    "NotFoundError",
    "RateLimitError",
    "error_for_status",
    # Files
    "FileInput",
    "normalize_file_input",
    # SSE
    "parse_sse_stream",
    # Resources
    "AdminApiKeysResource",
    "AdminAuditResource",
    "AdminEmbeddingPresetsResource",
    "AdminMcpServersResource",
    "AdminResource",
    "AdminUsersResource",
    "AuthResource",
    "CollectionsResource",
    "DocumentsResource",
    "EvaluationsResource",
    "QueryResource",
    "VectorsResource",
    "WebhooksResource",
]
