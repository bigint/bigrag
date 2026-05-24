import type {
  AccessLogEntry,
  AccessLogOverviewResponse,
  ApiKey,
  McpServer,
  EmbeddingPreset as SdkEmbeddingPreset,
  Webhook,
} from "@bigrag/client";
import type { Paginated } from "@/types/pagination";

export type { AccessLogEntry, ApiKey, McpServer, Webhook };

export type EmbeddingProvider = "openai" | "openai_compatible" | "cohere" | "voyage";

export type EmbeddingPreset = Omit<SdkEmbeddingPreset, "provider"> & {
  provider: EmbeddingProvider;
};

export type EmbeddingPresetBody = {
  name: string;
  provider: EmbeddingProvider;
  model: string;
  api_key: string;
  base_url?: string | null;
  dimension: number;
};

export type CreatedApiKey = ApiKey & { key: string };

export type CreatedMcpServer = McpServer & { api_key: string };

export type WorkerStats = {
  online: boolean;
  status?: "online" | "offline";
  heartbeat_at: string | null;
  heartbeat_age_seconds: number | null;
};

type HealthStatus = "ok" | "degraded" | "down";

type QueueHealth = {
  status: HealthStatus;
  reasons: string[];
};

type QueueStats = {
  queued: number;
  completed: number;
  failed: number;
  pending: number;
  processing: number;
  retrying?: number;
  dead_lettered?: number;
  leased_processing?: number;
  stale_processing?: number;
};

type DocumentStats = {
  total: number;
  ready: number;
  pending: number;
  processing: number;
  failed: number;
  total_chunks: number;
  total_tokens: number;
  total_size_bytes: number;
};

export type PlatformStats = {
  status?: HealthStatus;
  collections: number;
  documents: DocumentStats;
  webhooks: number;
  queue: QueueStats;
  queue_health?: QueueHealth;
  workers?: WorkerStats;
};

export type ReadinessReport = {
  version: string;
  postgres: boolean;
  postgres_error?: string;
  vector_store: boolean;
  vector_store_error?: string;
  redis: boolean;
  redis_error?: string;
  embedding: boolean;
  embedding_error?: string;
  embedding_source?: "settings" | "preset" | "collection";
  status: "ok" | "degraded";
};

export type AccessLogOverview = AccessLogOverviewResponse;

export type AccessLogListResponse = Paginated<"entries", AccessLogEntry>;

export type AccessLogFilters = {
  action?: string;
  actor_id?: string;
  collection?: string;
  method?: string;
  path?: string;
  status_family?: "2xx" | "3xx" | "4xx" | "5xx";
  success?: boolean;
  limit?: number;
  offset?: number;
};
