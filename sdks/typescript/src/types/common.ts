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
  milvus: boolean;
  redis: boolean;
  embedding?: boolean;
  embedding_error?: string;
}

export interface QueueStatsResponse {
  queued: number;
  completed: number;
  failed: number;
  pending: number;
  processing: number;
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
}
