import type { RequestClient } from "../core.js";
import type {
  CreateGoogleSourceBody,
  GoogleAccount,
  GoogleDriveFileListResponse,
  GoogleOAuthStartUrlResponse,
  GoogleSource,
  GoogleSourceListResponse,
  GoogleSyncJob,
  GoogleSyncJobListResponse,
  StatusResponse,
  UpdateGoogleSourceBody,
} from "../types.js";

export class ConnectorsResource {
  readonly google: GoogleDriveResource;

  constructor(client: RequestClient) {
    this.google = new GoogleDriveResource(client);
  }
}

export class GoogleDriveResource {
  constructor(private readonly _client: RequestClient) {}

  account(): Promise<GoogleAccount> {
    return this._client._request("GET", "/v1/connectors/google/account");
  }

  files(
    options: { parentId?: string; query?: string; pageToken?: string; pageSize?: number } = {},
  ): Promise<GoogleDriveFileListResponse> {
    const params: Record<string, string> = { parent_id: options.parentId ?? "root" };
    if (options.query !== undefined) params.query = options.query;
    if (options.pageToken !== undefined) params.page_token = options.pageToken;
    if (options.pageSize !== undefined) params.page_size = String(options.pageSize);
    return this._client._request("GET", "/v1/connectors/google/files", { params });
  }

  oauthStartUrl(options: { redirectPath?: string } = {}): Promise<GoogleOAuthStartUrlResponse> {
    const params: Record<string, string> = {};
    if (options.redirectPath !== undefined) params.redirect_path = options.redirectPath;
    return this._client._request("GET", "/v1/connectors/google/oauth/start-url", { params });
  }

  disconnect(): Promise<StatusResponse> {
    return this._client._request("POST", "/v1/connectors/google/disconnect");
  }

  sources(options: { collection?: string } = {}): Promise<GoogleSourceListResponse> {
    const params: Record<string, string> = {};
    if (options.collection !== undefined) params.collection = options.collection;
    return this._client._request("GET", "/v1/connectors/google/sources", { params });
  }

  createSource(body: CreateGoogleSourceBody): Promise<GoogleSource> {
    return this._client._request("POST", "/v1/connectors/google/sources", { json: body });
  }

  updateSource(sourceId: string, body: UpdateGoogleSourceBody): Promise<GoogleSource> {
    return this._client._request(
      "PATCH",
      `/v1/connectors/google/sources/${encodeURIComponent(sourceId)}`,
      { json: body },
    );
  }

  deleteSource(sourceId: string): Promise<StatusResponse> {
    return this._client._request(
      "DELETE",
      `/v1/connectors/google/sources/${encodeURIComponent(sourceId)}`,
    );
  }

  syncSource(sourceId: string): Promise<GoogleSyncJob> {
    return this._client._request(
      "POST",
      `/v1/connectors/google/sources/${encodeURIComponent(sourceId)}/sync`,
    );
  }

  syncJobs(
    options: { collection?: string; sourceId?: string; limit?: number } = {},
  ): Promise<GoogleSyncJobListResponse> {
    const params: Record<string, string> = {};
    if (options.collection !== undefined) params.collection = options.collection;
    if (options.sourceId !== undefined) params.source_id = options.sourceId;
    if (options.limit !== undefined) params.limit = String(options.limit);
    return this._client._request("GET", "/v1/connectors/google/sync-jobs", { params });
  }
}
