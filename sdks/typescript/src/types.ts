// --- Common ---

export interface StatusResponse {
  status: string;
  message?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
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
}

export interface UpdateCollectionBody {
  description?: string;
  metadata?: Record<string, unknown>;
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

// --- Query ---

export interface QueryBody {
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
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

// --- Auth ---

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface SetupBody {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginBody {
  email: string;
  password: string;
}

export interface ChangePasswordBody {
  current_password: string;
  new_password: string;
}

export interface SetupStatusResponse {
  needs_setup: boolean;
}

export interface MeResponse {
  user: User;
}

// --- Admin ---

export interface ApiKeyPermissions {
  collections: string[];
  operations: string[];
  admin: boolean;
}

export interface ApiKeySummary {
  id: string;
  name: string;
  prefix: string;
  permissions: ApiKeyPermissions;
  created_at: string;
  last_used_at?: string;
  expires_at?: string;
}

export interface CreateApiKeyBody {
  name: string;
  collections?: string[];
  operations?: string[];
  admin?: boolean;
  expires_at?: string;
}

export interface CreateApiKeyResponse {
  key: string;
  id: string;
  name: string;
  prefix: string;
  permissions: ApiKeyPermissions;
  created_at: string;
  expires_at?: string;
}

export interface ApiKeyListResponse {
  keys: ApiKeySummary[];
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

// --- File input ---

export type FileInput =
  | File
  | Blob
  | Buffer
  | Uint8Array
  | { path: string; name?: string };
