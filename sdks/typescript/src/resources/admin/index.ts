import type { RequestClient } from "../../core.js";
import { AdminAccessResource } from "./access.js";
import { AdminApiKeysResource } from "./api_keys.js";
import { AdminAuditResource } from "./audit.js";
import { AdminEmbeddingPresetsResource } from "./embedding_presets.js";
import { AdminMcpServersResource } from "./mcp_servers.js";
import { AdminSettingsResource } from "./settings.js";
import { AdminUsersResource } from "./users.js";
import { AdminVectorStorageResource } from "./vector_storage.js";

export class AdminResource {
  readonly users: AdminUsersResource;
  readonly apiKeys: AdminApiKeysResource;
  readonly access: AdminAccessResource;
  readonly audit: AdminAuditResource;
  readonly embeddingPresets: AdminEmbeddingPresetsResource;
  readonly mcpServers: AdminMcpServersResource;
  readonly settings: AdminSettingsResource;
  readonly vectorStorage: AdminVectorStorageResource;

  constructor(client: RequestClient) {
    this.users = new AdminUsersResource(client);
    this.apiKeys = new AdminApiKeysResource(client);
    this.access = new AdminAccessResource(client);
    this.audit = new AdminAuditResource(client);
    this.embeddingPresets = new AdminEmbeddingPresetsResource(client);
    this.mcpServers = new AdminMcpServersResource(client);
    this.settings = new AdminSettingsResource(client);
    this.vectorStorage = new AdminVectorStorageResource(client);
  }
}
