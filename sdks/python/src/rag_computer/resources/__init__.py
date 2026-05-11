from __future__ import annotations

from rag_computer.resources.admin import (
    AdminAccessResource,
    AdminApiKeysResource,
    AdminAuditResource,
    AdminConnectorsResource,
    AdminEmbeddingPresetsResource,
    AdminGoogleConnectorResource,
    AdminMcpServersResource,
    AdminResource,
    AdminUsersResource,
)
from rag_computer.resources.auth import AuthResource
from rag_computer.resources.chat import ChatResource
from rag_computer.resources.collections import CollectionsResource
from rag_computer.resources.connectors import ConnectorsResource, GoogleDriveResource
from rag_computer.resources.documents import DocumentsResource
from rag_computer.resources.evaluations import EvaluationsResource
from rag_computer.resources.query import QueryResource
from rag_computer.resources.vectors import VectorsResource
from rag_computer.resources.webhooks import WebhooksResource

__all__ = [
    "AdminAccessResource",
    "AdminApiKeysResource",
    "AdminAuditResource",
    "AdminConnectorsResource",
    "AdminGoogleConnectorResource",
    "AdminEmbeddingPresetsResource",
    "AdminMcpServersResource",
    "AdminResource",
    "AdminUsersResource",
    "AuthResource",
    "ChatResource",
    "CollectionsResource",
    "ConnectorsResource",
    "DocumentsResource",
    "EvaluationsResource",
    "GoogleDriveResource",
    "QueryResource",
    "VectorsResource",
    "WebhooksResource",
]
