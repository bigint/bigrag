import { type RequestClient, USER_AGENT } from "../core.js";
import { errorForStatus } from "../errors.js";
import { parseSSEFrames } from "../sse.js";
import type {
  AccessLogListResponse,
  AccessLogOverviewResponse,
  AdminRealtimeEvent,
  ApiKey,
  ApiKeyListResponse,
  AuditLogListResponse,
  BackupCreateBody,
  BackupJob,
  BackupJobListResponse,
  BatchStatusResponse,
  CollectionStatsResponse,
  CreateApiKeyBody,
  CreateApiKeyResponse,
  CreateEmbeddingPresetBody,
  CreateMcpServerBody,
  CreateMcpServerResponse,
  CreateUserBody,
  Document,
  DocumentListResponse,
  EmbeddingPreset,
  EmbeddingPresetListResponse,
  GoogleConnectorConfig,
  GoogleSourceListResponse,
  GoogleSyncJobListResponse,
  InstanceSettingsResponse,
  InstanceSettingsTestResponse,
  McpServer,
  McpServerListResponse,
  PlatformStatsResponse,
  ReadinessResponse,
  ResetInstanceSettingsBody,
  StatusResponse,
  TestInstanceSettingsBody,
  UpdateApiKeyBody,
  UpdateEmbeddingPresetBody,
  UpdateGoogleConnectorConfigBody,
  UpdateInstanceSettingsBody,
  UpdateMcpServerBody,
  UpdateUserBody,
  UploadSession,
  UsageResponse,
  User,
  UserListResponse,
} from "../types/index.js";

export class AdminResource {
  readonly users: AdminUsersResource;
  readonly apiKeys: AdminApiKeysResource;
  readonly access: AdminAccessResource;
  readonly audit: AdminAuditResource;
  readonly backups: AdminBackupsResource;
  readonly connectors: AdminConnectorsResource;
  readonly embeddingPresets: AdminEmbeddingPresetsResource;
  readonly mcpServers: AdminMcpServersResource;
  readonly realtime: AdminRealtimeResource;
  readonly settings: AdminSettingsResource;

  constructor(client: RequestClient) {
    this.users = new AdminUsersResource(client);
    this.apiKeys = new AdminApiKeysResource(client);
    this.access = new AdminAccessResource(client);
    this.audit = new AdminAuditResource(client);
    this.backups = new AdminBackupsResource(client);
    this.connectors = new AdminConnectorsResource(client);
    this.embeddingPresets = new AdminEmbeddingPresetsResource(client);
    this.mcpServers = new AdminMcpServersResource(client);
    this.realtime = new AdminRealtimeResource(client);
    this.settings = new AdminSettingsResource(client);
  }
}

export class AdminSettingsResource {
  constructor(private readonly _client: RequestClient) {}

  list(): Promise<InstanceSettingsResponse> {
    return this._client._request("GET", "/v1/admin/settings");
  }

  update(body: UpdateInstanceSettingsBody): Promise<InstanceSettingsResponse> {
    return this._client._request("PUT", "/v1/admin/settings", { json: body });
  }

  test(body: TestInstanceSettingsBody = {}): Promise<InstanceSettingsTestResponse> {
    return this._client._request("POST", "/v1/admin/settings/test", {
      json: { values: body.values ?? {} },
    });
  }

  reset(body: ResetInstanceSettingsBody = { keys: [] }): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/admin/settings/reset", { json: body });
  }

  purgeEmbeddingCache(): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/admin/settings/embedding-cache/purge");
  }
}

export class AdminBackupsResource {
  constructor(private readonly _client: RequestClient) {}

  list(options: { limit?: number; offset?: number } = {}): Promise<BackupJobListResponse> {
    return this._client._request("GET", "/v1/admin/backups", { params: pagination(options) });
  }

  get(backupId: string): Promise<BackupJob> {
    return this._client._request("GET", `/v1/admin/backups/${encodeURIComponent(backupId)}`);
  }

  create(body: BackupCreateBody = {}): Promise<BackupJob> {
    return this._client._request("POST", "/v1/admin/backups", {
      json: { label: body.label ?? "" },
    });
  }
}

export class AdminRealtimeResource {
  constructor(private readonly _client: RequestClient) {}

  documents(
    collection: string,
    options: {
      limit?: number;
      offset?: number;
      order?: "asc" | "desc";
      q?: string;
      sort?: "created_at" | "updated_at" | "filename" | "file_size" | "chunk_count" | "status";
      status?: string;
    } = {},
  ): AsyncGenerator<AdminRealtimeEvent<DocumentListResponse>> {
    return this._stream(
      `/v1/admin/realtime/collections/${encodeURIComponent(collection)}/documents`,
      {
        limit: options.limit,
        offset: options.offset,
        order: options.order,
        q: options.q,
        sort: options.sort,
        status: options.status,
      },
    );
  }

  documentBatchStatus(
    collection: string,
    documentIds: string[],
  ): AsyncGenerator<AdminRealtimeEvent<BatchStatusResponse>> {
    return this._stream(
      `/v1/admin/realtime/collections/${encodeURIComponent(collection)}/documents/batch-status`,
      { document_ids: documentIds.join(",") },
    );
  }

  document(collection: string, documentId: string): AsyncGenerator<AdminRealtimeEvent<Document>> {
    return this._stream(
      `/v1/admin/realtime/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}`,
    );
  }

  uploadSession(
    collection: string,
    sessionId: string,
  ): AsyncGenerator<AdminRealtimeEvent<UploadSession>> {
    return this._stream(
      `/v1/admin/realtime/collections/${encodeURIComponent(collection)}/upload-sessions/${encodeURIComponent(sessionId)}`,
    );
  }

  collectionStats(collection: string): AsyncGenerator<AdminRealtimeEvent<CollectionStatsResponse>> {
    return this._stream(`/v1/admin/realtime/collections/${encodeURIComponent(collection)}/stats`);
  }

  connectorSources(
    provider: string,
    options: { collection?: string } = {},
  ): AsyncGenerator<AdminRealtimeEvent<GoogleSourceListResponse>> {
    return this._stream(`/v1/admin/realtime/${encodeURIComponent(provider)}/sources`, {
      collection: options.collection,
    });
  }

  connectorSyncJobs(
    provider: string,
    options: { collection?: string; sourceId?: string; limit?: number } = {},
  ): AsyncGenerator<AdminRealtimeEvent<GoogleSyncJobListResponse>> {
    return this._stream(`/v1/admin/realtime/${encodeURIComponent(provider)}/sync-jobs`, {
      collection: options.collection,
      source_id: options.sourceId,
      limit: options.limit,
    });
  }

  backups(
    options: { limit?: number; offset?: number } = {},
  ): AsyncGenerator<AdminRealtimeEvent<BackupJobListResponse>> {
    return this._stream("/v1/admin/realtime/backups", options);
  }

  accessOverview(
    options: { windowDays?: number } = {},
  ): AsyncGenerator<AdminRealtimeEvent<AccessLogOverviewResponse>> {
    return this._stream("/v1/admin/realtime/access/overview", {
      window_days: options.windowDays,
    });
  }

  accessLogs(
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
  ): AsyncGenerator<AdminRealtimeEvent<AccessLogListResponse>> {
    return this._stream("/v1/admin/realtime/access/logs", {
      action: options.action,
      actor_id: options.actorId,
      collection: options.collection,
      method: options.method,
      path: options.path,
      status_family: options.statusFamily,
      success: options.success,
      limit: options.limit,
      offset: options.offset,
    });
  }

  audit(
    options: {
      action?: string;
      actorId?: string;
      resourceType?: string;
      limit?: number;
      offset?: number;
    } = {},
  ): AsyncGenerator<AdminRealtimeEvent<AuditLogListResponse>> {
    return this._stream("/v1/admin/realtime/audit", {
      action: options.action,
      actor_id: options.actorId,
      resource_type: options.resourceType,
      limit: options.limit,
      offset: options.offset,
    });
  }

  usage(options: { windowDays?: number } = {}): AsyncGenerator<AdminRealtimeEvent<UsageResponse>> {
    return this._stream("/v1/admin/realtime/usage", {
      window_days: options.windowDays,
    });
  }

  platformStats(): AsyncGenerator<AdminRealtimeEvent<PlatformStatsResponse>> {
    return this._stream("/v1/admin/realtime/platform/stats");
  }

  platformReadiness(): AsyncGenerator<AdminRealtimeEvent<ReadinessResponse>> {
    return this._stream("/v1/admin/realtime/platform/readiness");
  }

  custom<T = unknown>(
    path: string,
    params: Record<string, string | number | boolean | undefined> = {},
  ): AsyncGenerator<AdminRealtimeEvent<T>> {
    return this._stream(path, params);
  }

  private async *_stream<T>(
    path: string,
    params: Record<string, string | number | boolean | undefined> = {},
  ): AsyncGenerator<AdminRealtimeEvent<T>> {
    const url = new URL(`${this._client.baseUrl}${path}`);
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
    const headers: Record<string, string> = { "User-Agent": USER_AGENT };
    if (this._client.apiKey) headers.Authorization = `Bearer ${this._client.apiKey}`;
    const response = await this._client._fetch(url.toString(), {
      method: "GET",
      headers,
      credentials: "include",
      signal: AbortSignal.timeout(this._client.timeout),
    });
    if (!response.ok || !response.body) {
      const message = await response.text().catch(() => response.statusText);
      throw errorForStatus(response.status, message);
    }

    for await (const frame of parseSSEFrames(response)) {
      yield { event: frame.event, data: JSON.parse(frame.data) } as AdminRealtimeEvent<T>;
    }
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

  rotate(keyId: string): Promise<CreateApiKeyResponse> {
    return this._client._request("POST", `/v1/admin/api-keys/${encodeURIComponent(keyId)}/rotate`);
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

  test(body: {
    provider: string;
    model: string;
    api_key?: string | null;
    base_url?: string | null;
  }): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/admin/embedding-presets/test", { json: body });
  }

  testSaved(presetId: string): Promise<StatusResponse> {
    return this._client._request(
      "POST",
      `/v1/admin/embedding-presets/${encodeURIComponent(presetId)}/test`,
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
