import { type RequestClient, USER_AGENT } from "../../core.js";
import { errorForStatus } from "../../errors.js";
import { parseSSEFrames } from "../../sse.js";
import type {
  AccessLogListResponse,
  AccessLogOverviewResponse,
  AdminRealtimeEvent,
  AuditLogListResponse,
  BackupJobListResponse,
  BatchStatusResponse,
  CollectionStatsResponse,
  Document,
  DocumentListResponse,
  PlatformStatsResponse,
  ReadinessResponse,
  S3SourceListResponse,
  S3SyncJobListResponse,
  UploadSession,
  UsageResponse,
} from "../../types/index.js";

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
  ): AsyncGenerator<AdminRealtimeEvent<S3SourceListResponse>> {
    return this._stream(`/v1/admin/realtime/${encodeURIComponent(provider)}/sources`, {
      collection: options.collection,
    });
  }

  connectorSyncJobs(
    provider: string,
    options: { collection?: string; sourceId?: string; limit?: number } = {},
  ): AsyncGenerator<AdminRealtimeEvent<S3SyncJobListResponse>> {
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
    if (!path.startsWith("/v1/admin/realtime/")) {
      throw new Error("admin.realtime.custom path must start with /v1/admin/realtime/");
    }
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
