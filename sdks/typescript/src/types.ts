// --- Common ---

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

// --- Collections ---

export interface Collection {
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
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CollectionListResponse {
  collections: Collection[];
}

export interface CreateCollectionBody {
  name: string;
  description?: string;
  embedding_provider?: string;
  embedding_model?: string;
  embedding_api_key?: string;
  dimension?: number;
  chunk_size?: number;
  chunk_overlap?: number;
  reranking_enabled?: boolean;
  reranking_model?: string;
  reranking_api_key?: string;
}

export interface UpdateCollectionBody {
  description?: string;
  metadata?: Record<string, unknown>;
  reranking_enabled?: boolean;
  reranking_model?: string;
  reranking_api_key?: string;
}

// --- Documents ---

export interface Document {
  id: string;
  collection_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: string;
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface DocumentListOptions {
  status?: string;
  limit?: number;
  offset?: number;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  metadata: Record<string, unknown>;
}

export interface DocumentChunkListResponse {
  chunks: DocumentChunk[];
  total: number;
}

export interface BatchStatusBody {
  document_ids: string[];
}

export interface DocumentStatus {
  id: string;
  status: string;
  error_message: string | null;
  chunk_count: number;
}

export interface BatchStatusResponse {
  documents: DocumentStatus[];
  total: number;
}

export interface BatchDeleteBody {
  document_ids: string[];
}

export interface BatchDeleteDocumentsResponse {
  status: string;
  deleted: number;
  errors: Array<{ document_id: string; error: string }>;
}

// --- Query ---

export interface QueryBody {
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
  rerank?: boolean;
}

export interface QueryResult {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  metadata: Record<string, unknown>;
}

export interface QueryResponse {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
}

// --- Vectors ---

export interface VectorEntry {
  id: string;
  embedding: number[];
  text?: string;
  metadata?: Record<string, unknown>;
}

export interface UpsertResponse {
  status: string;
  upserted: number;
}

export interface DeleteResponse {
  status: string;
  deleted: number;
}

// --- Embeddings ---

export interface EmbeddingModelInfo {
  provider: string;
  model: string;
  dimension: number;
  description: string;
}

export interface EmbeddingModelListResponse {
  models: EmbeddingModelInfo[];
}

// --- SSE ---

export interface ProgressEvent {
  step: string;
  message: string;
  progress: number;
  status?: string;
  detail?: Record<string, unknown>;
}

// --- Multi-Collection Query ---

export interface MultiQueryBody {
  query: string;
  collections: string[];
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
}

export interface MultiQueryResult {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  collection: string;
  metadata: Record<string, unknown>;
}

export interface MultiQueryResponse {
  results: MultiQueryResult[];
  query: string;
  collections: string[];
  total: number;
}

// --- Batch Query ---

export interface BatchQueryItem {
  collection: string;
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
  rerank?: boolean;
}

export interface BatchQueryBody {
  queries: BatchQueryItem[];
}

export interface BatchQueryResultItem {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
}

export interface BatchQueryResponse {
  results: BatchQueryResultItem[];
}

// --- Analytics ---

export interface PeriodStats {
  query_count: number;
  avg_latency_ms: number;
  avg_score: number;
  avg_result_count: number;
}

export interface TopQuery {
  query: string;
  count: number;
}

export interface AnalyticsResponse {
  collection: string;
  period_24h: PeriodStats;
  period_7d: PeriodStats;
  period_30d: PeriodStats;
  top_queries: TopQuery[];
}

// --- Webhooks ---

export interface Webhook {
  id: string;
  url: string;
  events: string[];
  collections: string[] | null;
  description: string;
  active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateWebhookBody {
  url: string;
  events: string[];
  collections?: string[];
  description?: string;
}

export interface CreateWebhookResponse extends Webhook {
  secret: string;
}

export interface UpdateWebhookBody {
  url?: string;
  events?: string[];
  collections?: string[] | null;
  description?: string;
  active?: boolean;
}

export interface WebhookListResponse {
  webhooks: Webhook[];
}

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event: string;
  payload: Record<string, unknown>;
  status: string;
  attempts: number;
  last_status_code: number | null;
  last_error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface WebhookDeliveryListResponse {
  deliveries: WebhookDelivery[];
  total: number;
}

export interface WebhookTestResponse {
  status: string;
  status_code: number | null;
  error: string | null;
}

// --- File input ---

export type FileInput =
  | File
  | Blob
  | Buffer
  | Uint8Array
  | { path: string; name?: string };
