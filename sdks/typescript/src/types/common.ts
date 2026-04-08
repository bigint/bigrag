/** Response indicating an operation's status. */
export interface StatusResponse {
  status: string;
  message?: string;
}

/** Health-check response from the platform. */
export interface HealthResponse {
  status: string;
  version: string;
}

/** Readiness probe showing connectivity to all backing services. */
export interface ReadinessResponse {
  status: string;
  version: string;
  postgres: boolean;
  milvus: boolean;
  redis: boolean;
}

/** Aggregated queue statistics. */
export interface QueueStatsResponse {
  queued: number;
  completed: number;
  failed: number;
  pending: number;
  processing: number;
}

/** Aggregate counts and sizes for documents. */
export interface DocumentStats {
  total: number;
  ready: number;
  pending: number;
  processing: number;
  failed: number;
  total_chunks: number;
  total_tokens: number;
  total_size_bytes: number;
}

/** Platform-wide statistics encompassing collections, documents, webhooks and queues. */
export interface PlatformStatsResponse {
  collections: number;
  documents: DocumentStats;
  webhooks: number;
  queue: QueueStatsResponse;
}
