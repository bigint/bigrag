"""rag.computer Python SDK."""

from __future__ import annotations

from rag_computer import types as _types
from rag_computer._client import RagComputer, CollectionClient
from rag_computer._core import RagComputerCore
from rag_computer._errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RagComputerError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
    error_for_status,
)
from rag_computer._files import FileInput, normalize_file_input
from rag_computer._sse import parse_sse_stream
from rag_computer._version import __version__
from rag_computer.resources import (
    AdminApiKeysResource,
    AdminAuditResource,
    AdminEmbeddingPresetsResource,
    AdminMcpServersResource,
    AdminResource,
    AdminUsersResource,
    AuthResource,
    ChatResource,
    CollectionsResource,
    DocumentsResource,
    EvaluationsResource,
    QueryResource,
    VectorsResource,
    WebhooksResource,
)

for _name in _types.__all__:
    globals()[_name] = getattr(_types, _name)

__all__ = [
    # Client
    "RagComputer",
    "RagComputerCore",
    "CollectionClient",
    "__version__",
    # Errors
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "BadRequestError",
    "RagComputerError",
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
    "ChatResource",
    "CollectionsResource",
    "DocumentsResource",
    "EvaluationsResource",
    "QueryResource",
    "VectorsResource",
    "WebhooksResource",
] + list(_types.__all__)
