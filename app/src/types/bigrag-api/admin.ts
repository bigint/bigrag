export type EmbeddingPreset = {
  id: string;
  name: string;
  provider: "openai" | "cohere" | "voyage";
  model: string;
  base_url: string | null;
  dimension: number;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
};

export type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  active: boolean;
  scopes: string[];
  collection: string | null;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreatedApiKey = ApiKey & { key: string };

export type McpServer = {
  id: string;
  title: string;
  server_name: string;
  collection: string | null;
  key_prefix: string;
  key_active: boolean;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreatedMcpServer = McpServer & { api_key: string };

export type Webhook = {
  id: string;
  url: string;
  events: string[];
  collections: string[] | null;
  description: string;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type PlatformStats = {
  collections: number;
  documents: {
    total: number;
    ready: number;
    pending: number;
    processing: number;
    failed: number;
    total_chunks: number;
    total_tokens: number;
    total_size_bytes: number;
  };
  webhooks: number;
  queue: Record<string, number>;
};

export type ReadinessReport = {
  version: string;
  postgres: boolean;
  qdrant: boolean | null;
  vector_store: boolean;
  vector_store_provider: "qdrant" | "s3_vectors" | "turbopuffer";
  redis: boolean;
  embedding: boolean;
  embedding_error?: string;
  embedding_source?: "env" | "preset" | "collection";
  status: "ok" | "degraded";
};

export type AccessLogEntry = {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  api_key_id: string | null;
  api_key_name: string | null;
  auth_method: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  collection_name: string | null;
  method: string;
  path: string;
  route: string | null;
  status_code: number;
  success: boolean;
  latency_ms: number;
  request_id: string | null;
  metadata: Record<string, unknown>;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
};

type AccessLogBucket = {
  label: string;
  count: number;
  avg_latency_ms?: number | null;
};

type AccessLogTimelinePoint = {
  bucket: string;
  events: number;
  errors: number;
  avg_latency_ms: number;
};

export type AccessLogOverview = {
  window_days: number;
  total_events: number;
  success_rate: number;
  error_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  unique_users: number;
  query_events: number;
  by_action: AccessLogBucket[];
  latency_by_action: AccessLogBucket[];
  timeline: AccessLogTimelinePoint[];
  recent: AccessLogEntry[];
};

export type AccessLogListResponse = {
  entries: AccessLogEntry[];
  total: number;
};
