/** Body for a single-collection query. */
export interface QueryBody {
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
  rerank?: boolean;
}

/** A single query result with score and metadata. */
export interface QueryResult {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  metadata: Record<string, unknown>;
}

/** Response for a single-collection query. */
export interface QueryResponse {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
}

/** Body for a multi-collection query. */
export interface MultiQueryBody {
  query: string;
  collections: string[];
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
}

/** A query result that includes its source collection. */
export interface MultiQueryResult {
  id: string;
  text: string;
  score: number;
  document_id: string | null;
  chunk_index: number | null;
  collection: string;
  metadata: Record<string, unknown>;
}

/** Response for a multi-collection query. */
export interface MultiQueryResponse {
  results: MultiQueryResult[];
  query: string;
  collections: string[];
  total: number;
}

/** A single item in a batch query request. */
export interface BatchQueryItem {
  collection: string;
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  min_score?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
  rerank?: boolean;
}

/** Body for a batch query request. */
export interface BatchQueryBody {
  queries: BatchQueryItem[];
}

/** A single result set in a batch query response. */
export interface BatchQueryResultItem {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
}

/** Response for a batch query request. */
export interface BatchQueryResponse {
  results: BatchQueryResultItem[];
}
