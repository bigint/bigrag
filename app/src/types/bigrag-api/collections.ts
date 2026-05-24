import type { CollectionStatsResponse, Collection as SdkCollection } from "@bigrag/client/browser";

export type Collection = Omit<SdkCollection, "default_search_mode"> & {
  embedding_preset_id: string | null;
  default_search_mode: "semantic" | "keyword" | "hybrid";
};

export type CollectionStats = CollectionStatsResponse;

export type CreateCollectionBody = {
  name: string;
  description?: string;
  embedding_preset_id?: string | null;
  embedding_provider?: "openai" | "openai_compatible" | "cohere" | "voyage";
  embedding_model?: string;
  embedding_api_key?: string | null;
  embedding_base_url?: string | null;
  dimension?: number;
  chunk_size?: number;
  chunk_overlap?: number;
  reranking_enabled?: boolean;
  reranking_model?: string;
  reranking_api_key?: string | null;
  multimodal_enabled?: boolean;
  multimodal_enrichment_enabled?: boolean;
  default_top_k?: number;
  default_search_mode?: "semantic" | "keyword" | "hybrid";
  metadata?: Record<string, unknown>;
};
