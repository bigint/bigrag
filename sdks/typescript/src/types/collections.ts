export interface Collection {
  id: string;
  name: string;
  description: string;
  embedding_provider: string;
  embedding_model: string;
  vector_store_provider: "qdrant" | "turbopuffer";
  dimension: number;
  chunk_size: number;
  chunk_overlap: number;
  chunk_strategy: string;
  index_type: string;
  tenant_field: string | null;
  has_metadata_schema: boolean;
  document_count: number;
  has_api_key: boolean;
  embedding_preset_id: string | null;
  reranking_enabled: boolean;
  reranking_model: string;
  has_reranking_api_key: boolean;
  multimodal_enabled: boolean;
  multimodal_enrichment_enabled: boolean;
  default_top_k: number;
  default_min_score: number | null;
  default_search_mode: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CollectionListOptions {
  name?: string;
  limit?: number;
  offset?: number;
  include_total?: boolean;
}

export interface CollectionListResponse {
  collections: Collection[];
  total: number | null;
}

export interface CollectionStatsResponse {
  collection: string;
  document_count: number;
  total_chunks: number;
  total_tokens: number;
  total_size_bytes: number;
  status_counts: Record<string, number>;
}

export interface CreateCollectionBody {
  name: string;
  description?: string;
  vector_store_provider?: "qdrant" | "turbopuffer";
  embedding_preset_id?: string;
  embedding_provider?: string;
  embedding_model?: string;
  embedding_api_key?: string;
  embedding_base_url?: string;
  dimension?: number;
  chunk_size?: number;
  chunk_overlap?: number;
  chunk_strategy?: "paragraph" | "recursive";
  index_type?: "HNSW";
  tenant_field?: string;
  metadata_schema?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  reranking_enabled?: boolean;
  reranking_model?: string;
  reranking_api_key?: string;
  multimodal_enabled?: boolean;
  multimodal_enrichment_enabled?: boolean;
  default_top_k?: number;
  default_min_score?: number;
  default_search_mode?: "semantic" | "keyword" | "hybrid";
}

export interface UpdateCollectionBody {
  description?: string;
  metadata?: Record<string, unknown>;
  embedding_api_key?: string | null;
  reranking_enabled?: boolean;
  reranking_model?: string;
  reranking_api_key?: string | null;
  multimodal_enabled?: boolean;
  multimodal_enrichment_enabled?: boolean;
  default_top_k?: number;
  default_min_score?: number;
  default_search_mode?: "semantic" | "keyword" | "hybrid";
  chunk_strategy?: "paragraph" | "recursive";
  metadata_schema?: Record<string, unknown>;
}
