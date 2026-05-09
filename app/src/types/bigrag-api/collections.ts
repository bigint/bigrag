export type Collection = {
  id: string;
  name: string;
  description: string;
  embedding_provider: string;
  embedding_model: string;
  dimension: number;
  tenant_field: string | null;
  chunk_size: number;
  chunk_overlap: number;
  document_count: number;
  has_api_key: boolean;
  embedding_preset_id: string | null;
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
