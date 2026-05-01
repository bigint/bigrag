export type Collection = {
  id: string;
  name: string;
  description: string;
  embedding_provider: string;
  embedding_model: string;
  dimension: number;
  chunk_size: number;
  chunk_overlap: number;
  document_count: number;
  has_api_key: boolean;
  reranking_enabled: boolean;
  reranking_model: string;
  has_reranking_api_key: boolean;
  default_top_k: number;
  default_min_score: number | null;
  default_search_mode: "semantic" | "keyword" | "hybrid";
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CollectionStats = {
  collection: string;
  document_count: number;
  total_chunks: number;
  total_tokens: number;
  total_size_bytes: number;
  status_counts: Record<string, number>;
};

export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export type Document = {
  id: string;
  collection_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: DocumentStatus;
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Chunk = {
  id: string;
  text: string;
  document_id: string;
  chunk_index: number;
  metadata: Record<string, unknown>;
};

export type QueryResult = {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  page_no?: number | null;
  char_start?: number | null;
  char_end?: number | null;
  metadata: Record<string, unknown>;
};

export type QueryTimings = {
  embed_ms: number;
  search_ms: number;
  rerank_ms: number;
  hyde_ms: number;
  mmr_ms: number;
  total_ms: number;
};

export type QueryResponse = {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
  timings?: QueryTimings;
  facets?: Record<string, Record<string, number>>;
  cached?: boolean;
};

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

export type ProgressEvent = {
  document_id: string;
  step: string;
  status: string;
  message: string;
  progress: number;
  detail?: Record<string, unknown>;
};

export type ReadinessReport = {
  version: string;
  postgres: boolean;
  qdrant: boolean;
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

export type AccessLogBucket = {
  label: string;
  count: number;
  avg_latency_ms?: number | null;
};

export type AccessLogTimelinePoint = {
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
