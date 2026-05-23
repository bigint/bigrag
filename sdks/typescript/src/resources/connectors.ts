import type { RequestClient } from "../core.js";
import type {
  CreateS3SourceBody,
  S3Source,
  S3SourceListResponse,
  S3SyncJob,
  S3SyncJobListResponse,
  StatusResponse,
  UpdateS3SourceBody,
} from "../types/index.js";

export class ConnectorsResource {
  readonly s3: S3ConnectorResource;

  constructor(client: RequestClient) {
    this.s3 = new S3ConnectorResource(client);
  }
}

export class S3ConnectorResource {
  constructor(private readonly _client: RequestClient) {}

  sources(options: { collection?: string } = {}): Promise<S3SourceListResponse> {
    const params: Record<string, string> = {};
    if (options.collection !== undefined) params.collection = options.collection;
    return this._client._request("GET", "/v1/connectors/s3/sources", { params });
  }

  createSource(body: CreateS3SourceBody): Promise<S3Source> {
    return this._client._request("POST", "/v1/connectors/s3/sources", { json: body });
  }

  updateSource(sourceId: string, body: UpdateS3SourceBody): Promise<S3Source> {
    return this._client._request(
      "PATCH",
      `/v1/connectors/s3/sources/${encodeURIComponent(sourceId)}`,
      { json: body },
    );
  }

  deleteSource(sourceId: string): Promise<StatusResponse> {
    return this._client._request(
      "DELETE",
      `/v1/connectors/s3/sources/${encodeURIComponent(sourceId)}`,
    );
  }

  syncSource(sourceId: string): Promise<S3SyncJob> {
    return this._client._request(
      "POST",
      `/v1/connectors/s3/sources/${encodeURIComponent(sourceId)}/sync`,
    );
  }

  syncJobs(
    options: { collection?: string; sourceId?: string; limit?: number } = {},
  ): Promise<S3SyncJobListResponse> {
    const params: Record<string, string> = {};
    if (options.collection !== undefined) params.collection = options.collection;
    if (options.sourceId !== undefined) params.source_id = options.sourceId;
    if (options.limit !== undefined) params.limit = String(options.limit);
    return this._client._request("GET", "/v1/connectors/s3/sync-jobs", { params });
  }
}
