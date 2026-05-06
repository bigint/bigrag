import type { RequestClient } from "../core.js";
import type {
  AccessLogListResponse,
  AccessLogOverviewResponse,
  ApiKey,
  ApiKeyListResponse,
  AuditLogListResponse,
  CreateApiKeyBody,
  CreateApiKeyResponse,
  CreateEmbeddingPresetBody,
  CreateMcpServerBody,
  CreateMcpServerResponse,
  CreateUserBody,
  EmbeddingPreset,
  EmbeddingPresetListResponse,
  GoogleConnectorConfig,
  McpServer,
  McpServerListResponse,
  StatusResponse,
  UpdateApiKeyBody,
  UpdateEmbeddingPresetBody,
  UpdateGoogleConnectorConfigBody,
  UpdateMcpServerBody,
  UpdateUserBody,
  User,
  UserListResponse,
} from "../types.js";

export class AdminResource {
  readonly users: AdminUsersResource;
  readonly apiKeys: AdminApiKeysResource;
  readonly access: AdminAccessResource;
  readonly audit: AdminAuditResource;
  readonly connectors: AdminConnectorsResource;
  readonly embeddingPresets: AdminEmbeddingPresetsResource;
  readonly mcpServers: AdminMcpServersResource;

  constructor(client: RequestClient) {
    this.users = new AdminUsersResource(client);
    this.apiKeys = new AdminApiKeysResource(client);
    this.access = new AdminAccessResource(client);
    this.audit = new AdminAuditResource(client);
    this.connectors = new AdminConnectorsResource(client);
    this.embeddingPresets = new AdminEmbeddingPresetsResource(client);
    this.mcpServers = new AdminMcpServersResource(client);
  }
}

export class AdminUsersResource {
  constructor(private readonly _client: RequestClient) {}

  list(options: { limit?: number; offset?: number } = {}): Promise<UserListResponse> {
    return this._client._request("GET", "/v1/admin/users", { params: pagination(options) });
  }

  create(body: CreateUserBody): Promise<User> {
    return this._client._request("POST", "/v1/admin/users", { json: body });
  }

  update(userId: string, body: UpdateUserBody): Promise<User> {
    return this._client._request("PATCH", `/v1/admin/users/${encodeURIComponent(userId)}`, {
      json: body,
    });
  }

  delete(userId: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/admin/users/${encodeURIComponent(userId)}`);
  }
}

export class AdminApiKeysResource {
  constructor(private readonly _client: RequestClient) {}

  list(options: { limit?: number; offset?: number } = {}): Promise<ApiKeyListResponse> {
    return this._client._request("GET", "/v1/admin/api-keys", { params: pagination(options) });
  }

  create(body: CreateApiKeyBody): Promise<CreateApiKeyResponse> {
    return this._client._request("POST", "/v1/admin/api-keys", { json: body });
  }

  update(keyId: string, body: UpdateApiKeyBody): Promise<ApiKey> {
    return this._client._request("PATCH", `/v1/admin/api-keys/${encodeURIComponent(keyId)}`, {
      json: body,
    });
  }

  delete(keyId: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/admin/api-keys/${encodeURIComponent(keyId)}`);
  }
}

export class AdminAccessResource {
  constructor(private readonly _client: RequestClient) {}

  logs(
    options: {
      action?: string;
      actorId?: string;
      collection?: string;
      method?: string;
      path?: string;
      statusFamily?: string;
      success?: boolean;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<AccessLogListResponse> {
    const params = pagination(options);
    if (options.action !== undefined) params.action = options.action;
    if (options.actorId !== undefined) params.actor_id = options.actorId;
    if (options.collection !== undefined) params.collection = options.collection;
    if (options.method !== undefined) params.method = options.method;
    if (options.path !== undefined) params.path = options.path;
    if (options.statusFamily !== undefined) params.status_family = options.statusFamily;
    if (options.success !== undefined) params.success = String(options.success);
    return this._client._request("GET", "/v1/admin/access/logs", { params });
  }

  overview(options: { windowDays?: number } = {}): Promise<AccessLogOverviewResponse> {
    const params: Record<string, string> = {};
    if (options.windowDays !== undefined) params.window_days = String(options.windowDays);
    return this._client._request("GET", "/v1/admin/access/overview", { params });
  }
}

export class AdminAuditResource {
  constructor(private readonly _client: RequestClient) {}

  list(
    options: {
      action?: string;
      actorId?: string;
      resourceType?: string;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<AuditLogListResponse> {
    const params = pagination(options);
    if (options.action !== undefined) params.action = options.action;
    if (options.actorId !== undefined) params.actor_id = options.actorId;
    if (options.resourceType !== undefined) params.resource_type = options.resourceType;
    return this._client._request("GET", "/v1/admin/audit", { params });
  }
}

export class AdminConnectorsResource {
  readonly google: AdminGoogleConnectorResource;

  constructor(client: RequestClient) {
    this.google = new AdminGoogleConnectorResource(client);
  }
}

export class AdminGoogleConnectorResource {
  constructor(private readonly _client: RequestClient) {}

  get(): Promise<GoogleConnectorConfig> {
    return this._client._request("GET", "/v1/admin/connectors/google");
  }

  update(body: UpdateGoogleConnectorConfigBody): Promise<GoogleConnectorConfig> {
    return this._client._request("PUT", "/v1/admin/connectors/google", { json: body });
  }
}

export class AdminEmbeddingPresetsResource {
  constructor(private readonly _client: RequestClient) {}

  list(options: { limit?: number; offset?: number } = {}): Promise<EmbeddingPresetListResponse> {
    return this._client._request("GET", "/v1/admin/embedding-presets", {
      params: pagination(options),
    });
  }

  create(body: CreateEmbeddingPresetBody): Promise<EmbeddingPreset> {
    return this._client._request("POST", "/v1/admin/embedding-presets", { json: body });
  }

  update(presetId: string, body: UpdateEmbeddingPresetBody): Promise<EmbeddingPreset> {
    return this._client._request(
      "PATCH",
      `/v1/admin/embedding-presets/${encodeURIComponent(presetId)}`,
      { json: body },
    );
  }

  delete(presetId: string): Promise<StatusResponse> {
    return this._client._request(
      "DELETE",
      `/v1/admin/embedding-presets/${encodeURIComponent(presetId)}`,
    );
  }
}

export class AdminMcpServersResource {
  constructor(private readonly _client: RequestClient) {}

  list(): Promise<McpServerListResponse> {
    return this._client._request("GET", "/v1/admin/mcp-servers");
  }

  create(body: CreateMcpServerBody): Promise<CreateMcpServerResponse> {
    return this._client._request("POST", "/v1/admin/mcp-servers", { json: body });
  }

  update(serverId: string, body: UpdateMcpServerBody): Promise<McpServer> {
    return this._client._request("PATCH", `/v1/admin/mcp-servers/${encodeURIComponent(serverId)}`, {
      json: body,
    });
  }

  rotate(serverId: string): Promise<CreateMcpServerResponse> {
    return this._client._request(
      "POST",
      `/v1/admin/mcp-servers/${encodeURIComponent(serverId)}/rotate`,
    );
  }

  delete(serverId: string): Promise<StatusResponse> {
    return this._client._request("DELETE", `/v1/admin/mcp-servers/${encodeURIComponent(serverId)}`);
  }
}

function pagination(options: { limit?: number; offset?: number }): Record<string, string> {
  const params: Record<string, string> = {};
  if (options.limit !== undefined) params.limit = String(options.limit);
  if (options.offset !== undefined) params.offset = String(options.offset);
  return params;
}
