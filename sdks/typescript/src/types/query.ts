export interface QueryBody {
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
  hybrid_strategy?: "rrf" | "weighted" | "normalized";
  rerank?: boolean;
  diversity?: number;
  hyde?: boolean;
  facets?: string[];
  use_semantic_cache?: boolean;
}

export interface QueryResult {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  metadata: Record<string, unknown>;
}

export interface QueryTimings {
  embed_ms?: number;
  search_ms?: number;
  rerank_ms?: number;
  hyde_ms?: number;
  mmr_ms?: number;
  total_ms?: number;
}

export interface QueryResponse {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
  timings?: QueryTimings;
  facets?: Record<string, Record<string, number>>;
  cached?: boolean;
}

export interface MultiQueryBody {
  query: string;
  collections: string[];
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
  rerank?: boolean;
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
