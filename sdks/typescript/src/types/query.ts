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
