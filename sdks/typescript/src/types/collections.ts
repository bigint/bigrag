/** A collection of documents with embedding and search configuration. */
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
  default_top_k: number;
  default_min_score: number | null;
  default_search_mode: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** Options for listing collections. */
export interface CollectionListOptions {
  name?: string;
  limit?: number;
  offset?: number;
}

/** Paginated list of collections. */
export interface CollectionListResponse {
  collections: Collection[];
  total: number;
}

/** Statistics for a single collection. */
export interface CollectionStatsResponse {
  collection: string;
  document_count: number;
  total_chunks: number;
  total_tokens: number;
  total_size_bytes: number;
  status_counts: Record<string, number>;
}

/** Body for creating a new collection. */
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
  default_top_k?: number;
  default_min_score?: number;
  default_search_mode?: "semantic" | "keyword" | "hybrid";
}

/** Body for updating an existing collection. */
export interface UpdateCollectionBody {
  description?: string;
  metadata?: Record<string, unknown>;
  reranking_enabled?: boolean;
  reranking_model?: string;
  reranking_api_key?: string;
  default_top_k?: number;
  default_min_score?: number;
  default_search_mode?: "semantic" | "keyword" | "hybrid";
}
