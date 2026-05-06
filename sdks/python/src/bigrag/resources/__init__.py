from __future__ import annotations

from bigrag.resources.admin import (
    AdminApiKeysResource,
    AdminAuditResource,
    AdminEmbeddingPresetsResource,
    AdminMcpServersResource,
    AdminResource,
    AdminUsersResource,
)
from bigrag.resources.auth import AuthResource
from bigrag.resources.chat import ChatResource
from bigrag.resources.collections import CollectionsResource
from bigrag.resources.documents import DocumentsResource
from bigrag.resources.evaluations import EvaluationsResource
from bigrag.resources.query import QueryResource
from bigrag.resources.vectors import VectorsResource
from bigrag.resources.webhooks import WebhooksResource

__all__ = [
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
]
