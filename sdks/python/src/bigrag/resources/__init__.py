from __future__ import annotations

from bigrag._realtime import RealtimeResource
from bigrag.resources.admin import (
    AdminAccessResource,
    AdminApiKeysResource,
    AdminAuditResource,
    AdminBackupsResource,
    AdminEmbeddingPresetsResource,
    AdminMcpServersResource,
    AdminRealtimeResource,
    AdminResource,
    AdminSettingsResource,
    AdminUsersResource,
    AdminVectorStorageResource,
)
from bigrag.resources.auth import AuthResource
from bigrag.resources.chat import ChatResource
from bigrag.resources.collections import CollectionsResource
from bigrag.resources.connectors import ConnectorsResource, S3ConnectorResource
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
    "AdminEmbeddingPresetsResource",
    "AdminMcpServersResource",
    "AdminRealtimeResource",
    "AdminResource",
    "AdminSettingsResource",
    "AdminUsersResource",
    "AdminVectorStorageResource",
    "AuthResource",
    "ChatResource",
    "CollectionsResource",
    "ConnectorsResource",
    "DocumentsResource",
    "EvaluationsResource",
    "QueryResource",
    "RealtimeResource",
    "S3ConnectorResource",
    "VectorsResource",
    "WebhooksResource",
]
