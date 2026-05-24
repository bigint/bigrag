import type { RequestClient } from "../../core.js";
import { AdminAccessResource } from "./access.js";
import { AdminApiKeysResource } from "./api_keys.js";
import { AdminAuditResource } from "./audit.js";
import { AdminEmbeddingPresetsResource } from "./embedding_presets.js";
import { AdminMcpServersResource } from "./mcp_servers.js";
import { AdminRealtimeResource } from "./realtime.js";
import { AdminSettingsResource } from "./settings.js";
import { AdminUsersResource } from "./users.js";
import { AdminVectorStorageResource } from "./vector_storage.js";

export { AdminAccessResource } from "./access.js";
export { AdminApiKeysResource } from "./api_keys.js";
export { AdminAuditResource } from "./audit.js";
export { AdminEmbeddingPresetsResource } from "./embedding_presets.js";
export { AdminMcpServersResource } from "./mcp_servers.js";
export { AdminRealtimeResource } from "./realtime.js";
export { AdminSettingsResource } from "./settings.js";
export { AdminUsersResource } from "./users.js";
export { AdminVectorStorageResource } from "./vector_storage.js";

export class AdminResource {
  readonly users: AdminUsersResource;
  readonly apiKeys: AdminApiKeysResource;
  readonly access: AdminAccessResource;
  readonly audit: AdminAuditResource;
  readonly embeddingPresets: AdminEmbeddingPresetsResource;
  readonly mcpServers: AdminMcpServersResource;
  readonly realtime: AdminRealtimeResource;
  readonly settings: AdminSettingsResource;
  readonly vectorStorage: AdminVectorStorageResource;

  constructor(client: RequestClient) {
    this.users = new AdminUsersResource(client);
    this.apiKeys = new AdminApiKeysResource(client);
    this.access = new AdminAccessResource(client);
    this.audit = new AdminAuditResource(client);
    this.embeddingPresets = new AdminEmbeddingPresetsResource(client);
    this.mcpServers = new AdminMcpServersResource(client);
    this.realtime = new AdminRealtimeResource(client);
    this.settings = new AdminSettingsResource(client);
    this.vectorStorage = new AdminVectorStorageResource(client);
  }
}
