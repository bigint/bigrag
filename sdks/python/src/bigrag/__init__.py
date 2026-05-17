"""bigRAG Python SDK."""

from __future__ import annotations

from bigrag import types as _types
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
    PermissionDeniedError,
    RateLimitError,
    error_for_status,
)
from bigrag._files import FileInput, normalize_file_input
from bigrag._sse import parse_sse_stream
from bigrag._version import __version__
from bigrag.resources import (
    AdminAccessResource,
    AdminApiKeysResource,
    AdminAuditResource,
    AdminBackupsResource,
    AdminConnectorsResource,
    AdminEmbeddingPresetsResource,
    AdminGoogleConnectorResource,
    AdminMcpServersResource,
    AdminRealtimeResource,
    AdminResource,
    AdminSettingsResource,
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
    "PermissionDeniedError",
    "RateLimitError",
    "error_for_status",
    # Files
    "FileInput",
    "normalize_file_input",
    # SSE
    "parse_sse_stream",
    # Resources
    "AdminAccessResource",
    "AdminApiKeysResource",
    "AdminAuditResource",
    "AdminBackupsResource",
    "AdminConnectorsResource",
    "AdminEmbeddingPresetsResource",
    "AdminGoogleConnectorResource",
    "AdminMcpServersResource",
    "AdminRealtimeResource",
    "AdminResource",
    "AdminSettingsResource",
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
