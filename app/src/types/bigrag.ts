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
  provider: "openai" | "cohere";
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
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CreatedApiKey = ApiKey & { key: string };

export type User = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
};

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
  milvus: boolean;
  redis: boolean;
  embedding: boolean;
  embedding_error?: string;
  status: "ok" | "degraded";
};
