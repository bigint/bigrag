from __future__ import annotations

from typing import TYPE_CHECKING

from bigrag.resources.admin.access import AdminAccessResource
from bigrag.resources.admin.api_keys import AdminApiKeysResource
from bigrag.resources.admin.audit import AdminAuditResource
from bigrag.resources.admin.embedding_presets import AdminEmbeddingPresetsResource
from bigrag.resources.admin.mcp_servers import AdminMcpServersResource
from bigrag.resources.admin.settings import AdminSettingsResource
from bigrag.resources.admin.users import AdminUsersResource
from bigrag.resources.admin.vector_storage import AdminVectorStorageResource

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminResource:
    users: AdminUsersResource
    api_keys: AdminApiKeysResource
    access: AdminAccessResource
    audit: AdminAuditResource
    embedding_presets: AdminEmbeddingPresetsResource
    mcp_servers: AdminMcpServersResource
    settings: AdminSettingsResource
    vector_storage: AdminVectorStorageResource

    def __init__(self, client: BigRAGCore) -> None:
        self.users = AdminUsersResource(client)
        self.api_keys = AdminApiKeysResource(client)
        self.access = AdminAccessResource(client)
        self.audit = AdminAuditResource(client)
        self.embedding_presets = AdminEmbeddingPresetsResource(client)
        self.mcp_servers = AdminMcpServersResource(client)
        self.settings = AdminSettingsResource(client)
        self.vector_storage = AdminVectorStorageResource(client)


__all__ = [
    "AdminAccessResource",
    "AdminApiKeysResource",
    "AdminAuditResource",
    "AdminEmbeddingPresetsResource",
    "AdminMcpServersResource",
    "AdminResource",
    "AdminSettingsResource",
    "AdminUsersResource",
    "AdminVectorStorageResource",
]
