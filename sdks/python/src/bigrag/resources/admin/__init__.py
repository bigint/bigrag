from __future__ import annotations

from typing import TYPE_CHECKING

from bigrag.resources.admin.access import AdminAccessResource
from bigrag.resources.admin.api_keys import AdminApiKeysResource
from bigrag.resources.admin.audit import AdminAuditResource
from bigrag.resources.admin.backups import AdminBackupsResource
from bigrag.resources.admin.connectors import (
    AdminConnectorsResource,
    AdminGoogleConnectorResource,
)
from bigrag.resources.admin.embedding_presets import AdminEmbeddingPresetsResource
from bigrag.resources.admin.mcp_servers import AdminMcpServersResource
from bigrag.resources.admin.realtime import AdminRealtimeResource
from bigrag.resources.admin.settings import AdminSettingsResource
from bigrag.resources.admin.users import AdminUsersResource
from bigrag.resources.admin.vector_migrations import AdminVectorMigrationsResource

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminResource:
    users: AdminUsersResource
    api_keys: AdminApiKeysResource
    access: AdminAccessResource
    audit: AdminAuditResource
    backups: AdminBackupsResource
    connectors: AdminConnectorsResource
    embedding_presets: AdminEmbeddingPresetsResource
    mcp_servers: AdminMcpServersResource
    realtime: AdminRealtimeResource
    settings: AdminSettingsResource
    vector_migrations: AdminVectorMigrationsResource

    def __init__(self, client: BigRAGCore) -> None:
        self.users = AdminUsersResource(client)
        self.api_keys = AdminApiKeysResource(client)
        self.access = AdminAccessResource(client)
        self.audit = AdminAuditResource(client)
        self.backups = AdminBackupsResource(client)
        self.connectors = AdminConnectorsResource(client)
        self.embedding_presets = AdminEmbeddingPresetsResource(client)
        self.mcp_servers = AdminMcpServersResource(client)
        self.realtime = AdminRealtimeResource(client)
        self.settings = AdminSettingsResource(client)
        self.vector_migrations = AdminVectorMigrationsResource(client)


__all__ = [
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
    "AdminVectorMigrationsResource",
]
