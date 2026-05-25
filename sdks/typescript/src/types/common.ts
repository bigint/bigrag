export interface StatusResponse {
  status: string;
  message?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface ReadinessResponse {
  status: string;
  version: string;
  postgres: boolean;
  vector_store: boolean;
  redis: boolean;
  embedding?: boolean;
  embedding_source?: string;
  embedding_error?: string;
}

export interface QueueStatsResponse {
  queued: number;
  completed: number;
  failed: number;
  pending: number;
  processing: number;
  retrying?: number;
  dead_lettered?: number;
  leased_processing?: number;
  stale_processing?: number;
}

export interface WorkerStatsResponse {
  online: boolean;
  heartbeat_at: string | null;
  heartbeat_age_seconds: number | null;
}

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

export interface PlatformStatsResponse {
  collections: number;
  documents: DocumentStats;
  webhooks: number;
  queue: QueueStatsResponse;
  workers?: WorkerStatsResponse;
}

export interface OverviewStatusResponse {
  platform: PlatformStatsResponse;
  readiness: ReadinessResponse;
}

export interface CollectionsStatusResponse {
  collections_total: number;
  documents_total: number;
  documents_ready: number;
  documents_pending: number;
  documents_processing: number;
  documents_failed: number;
  total_chunks: number;
  total_tokens: number;
  total_size_bytes: number;
}
