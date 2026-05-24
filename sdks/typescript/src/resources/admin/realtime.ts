import type { RequestClient } from "../../core.js";
import { BigRAGRealtimeConnection } from "../../realtime.js";
import type {
  AccessLogListResponse,
  AccessLogOverviewResponse,
  AdminRealtimeEvent,
  AuditLogListResponse,
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
    return this._stream("admin.collections.documents", {
      collection,
      limit: options.limit,
      offset: options.offset,
      order: options.order,
      q: options.q,
      sort: options.sort,
      status: options.status,
    });
  }

  documentBatchStatus(
    collection: string,
    documentIds: string[],
  ): AsyncGenerator<AdminRealtimeEvent<BatchStatusResponse>> {
    return this._stream("admin.collections.documents.batch_status", {
      collection,
      document_ids: documentIds,
    });
  }

  document(collection: string, documentId: string): AsyncGenerator<AdminRealtimeEvent<Document>> {
    return this._stream("admin.collections.documents.detail", {
      collection,
      document_id: documentId,
    });
  }

  uploadSession(
    collection: string,
    sessionId: string,
  ): AsyncGenerator<AdminRealtimeEvent<UploadSession>> {
    return this._stream("admin.collections.upload_session", { collection, session_id: sessionId });
  }

  collectionStats(collection: string): AsyncGenerator<AdminRealtimeEvent<CollectionStatsResponse>> {
    return this._stream("admin.collections.stats", { collection });
  }

  connectorSources(
    provider: string,
    options: { collection?: string } = {},
  ): AsyncGenerator<AdminRealtimeEvent<S3SourceListResponse>> {
    return this._stream("admin.connectors.sources", {
      provider,
      collection: options.collection,
    });
  }

  connectorSyncJobs(
    provider: string,
    options: { collection?: string; sourceId?: string; limit?: number } = {},
  ): AsyncGenerator<AdminRealtimeEvent<S3SyncJobListResponse>> {
    return this._stream("admin.connectors.sync_jobs", {
      provider,
      collection: options.collection,
      source_id: options.sourceId,
      limit: options.limit,
    });
  }

  accessOverview(
    options: { windowDays?: number } = {},
  ): AsyncGenerator<AdminRealtimeEvent<AccessLogOverviewResponse>> {
    return this._stream("admin.access.overview", {
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
    return this._stream("admin.access.logs", {
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
    return this._stream("admin.audit", {
      action: options.action,
      actor_id: options.actorId,
      resource_type: options.resourceType,
      limit: options.limit,
      offset: options.offset,
    });
  }

  usage(options: { windowDays?: number } = {}): AsyncGenerator<AdminRealtimeEvent<UsageResponse>> {
    return this._stream("admin.usage", {
      window_days: options.windowDays,
    });
  }

  platformStats(): AsyncGenerator<AdminRealtimeEvent<PlatformStatsResponse>> {
    return this._stream("admin.platform.stats");
  }

  platformReadiness(): AsyncGenerator<AdminRealtimeEvent<ReadinessResponse>> {
    return this._stream("admin.platform.readiness");
  }

  custom<T = unknown>(
    topic: string,
    params: Record<string, string | number | boolean | string[] | undefined> = {},
  ): AsyncGenerator<AdminRealtimeEvent<T>> {
    if (!topic.startsWith("admin.")) {
      throw new Error("admin.realtime.custom topic must start with admin.");
    }
    return this._stream(topic, params);
  }

  private async *_stream<T>(
    topic: string,
    params: Record<string, string | number | boolean | string[] | undefined> = {},
  ): AsyncGenerator<AdminRealtimeEvent<T>> {
    const connection = new BigRAGRealtimeConnection(this._client);
    try {
      for await (const message of connection.subscribe<T>(topic, params)) {
        yield message as AdminRealtimeEvent<T>;
        if (message.type === "complete") return;
      }
    } finally {
      await connection.close();
    }
  }
}
