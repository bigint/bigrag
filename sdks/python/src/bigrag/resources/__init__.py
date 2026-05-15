from __future__ import annotations

from bigrag.resources.admin import (
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
)
from bigrag.resources.auth import AuthResource
from bigrag.resources.chat import ChatResource
from bigrag.resources.collections import CollectionsResource
from bigrag.resources.connectors import ConnectorsResource, GoogleDriveResource
from bigrag.resources.documents import DocumentsResource
from bigrag.resources.evaluations import EvaluationsResource
from bigrag.resources.query import QueryResource
from bigrag.resources.vectors import VectorsResource
from bigrag.resources.webhooks import WebhooksResource

__all__ = [
    "AdminAccessResource",
    "AdminApiKeysResource",
    "AdminAuditResource",
    "AdminBackupsResource",
    "AdminConnectorsResource",
    "AdminGoogleConnectorResource",
    "AdminEmbeddingPresetsResource",
    "AdminMcpServersResource",
    "AdminRealtimeResource",
    "AdminResource",
    "AdminSettingsResource",
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
