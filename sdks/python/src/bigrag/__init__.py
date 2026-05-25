from __future__ import annotations

from bigrag import types as _types
from bigrag._client import BigRAG, CollectionClient
from bigrag._core import BigRAGCore
from bigrag._errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadGatewayError,
    BadRequestError,
    BigRAGError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PayloadTooLargeError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    UnprocessableEntityError,
    error_for_status,
)
from bigrag._files import FileInput, normalize_file_input
from bigrag._sse import parse_sse_frames
from bigrag._version import __version__
from bigrag.resources import (
    AdminResource,
    AuthResource,
    ChatResource,
    CollectionsResource,
    ConnectorsResource,
    DocumentsResource,
    EvaluationsResource,
    QueryResource,
    S3ConnectorResource,
    VectorsResource,
    WebhooksResource,
)

for _name in _types.__all__:
    globals()[_name] = getattr(_types, _name)

__all__ = [
    "BigRAG",
    "BigRAGCore",
    "CollectionClient",
    "__version__",
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "BadGatewayError",
    "BadRequestError",
    "BigRAGError",
    "ConflictError",
    "InternalServerError",
    "NotFoundError",
    "PayloadTooLargeError",
    "PermissionDeniedError",
    "RateLimitError",
    "ServiceUnavailableError",
    "UnprocessableEntityError",
    "error_for_status",
    "FileInput",
    "normalize_file_input",
    "parse_sse_frames",
    "AdminResource",
    "AuthResource",
    "ChatResource",
    "CollectionsResource",
    "ConnectorsResource",
    "DocumentsResource",
    "EvaluationsResource",
    "QueryResource",
    "S3ConnectorResource",
    "VectorsResource",
    "WebhooksResource",
] + list(_types.__all__)
