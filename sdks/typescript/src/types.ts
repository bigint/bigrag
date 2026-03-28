/**
 * A row to upsert into a namespace.
 */
export interface UpsertRow {
  /** Unique identifier for the row. */
  id: string | number;
  /** The vector embedding. */
  vector?: number[];
  /** Additional attributes stored alongside the vector. */
  [key: string]: unknown;
}

/**
 * A row to patch (partial update) in a namespace.
 */
export interface PatchRow {
  /** Unique identifier for the row to patch. */
  id: string | number;
  /** Attributes to update. */
  [key: string]: unknown;
}

/**
 * Filter expressions for queries and deletes.
 *
 * Filters are recursive tuple structures:
 * - Comparison: `[field, operator, value]` e.g. `["status", "Eq", "active"]`
 * - Logical: `["And", [...filters]]` or `["Or", [...filters]]`
 */
export type Filter =
  | [string, FilterOperator, FilterValue]
  | ["And", Filter[]]
  | ["Or", Filter[]]
  | ["Not", Filter];

export type FilterOperator =
  | "Eq"
  | "NotEq"
  | "In"
  | "NotIn"
  | "Lt"
  | "Lte"
  | "Gt"
  | "Gte"
  | "Glob"
  | "NotGlob";

export type FilterValue = string | number | boolean | (string | number | boolean)[];

/**
 * Ranking strategies for queries.
 *
 * - ANN vector search: `["vector", "ANN", number[]]`
 * - BM25 full-text search: `["bm25", "field_name", "query string"]`
 * - Sum combination: `["Sum", RankBy[]]`
 */
export type RankBy =
  | ["vector", "ANN", number[]]
  | ["bm25", string, string]
  | ["Sum", RankBy[]];

/**
 * Options for a query request.
 */
export interface QueryOptions {
  /** The ranking strategy. */
  rankBy: RankBy;
  /** Maximum number of results to return. */
  topK: number;
  /** Optional filter expression. */
  filters?: Filter;
  /** Whether to include row attributes in results. */
  includeAttributes?: boolean | string[];
  /** Whether to include vectors in results. */
  includeVectors?: boolean;
}

/**
 * A single row in query results.
 */
export interface QueryRow {
  /** Row identifier. */
  id: string | number;
  /** Distance/score from the query. */
  dist: number;
  /** Row vector, if requested. */
  vector?: number[];
  /** Row attributes, if requested. */
  attributes?: Record<string, unknown>;
}

/**
 * Response from a query request.
 */
export interface QueryResponse {
  /** Matched rows. */
  rows: QueryRow[];
}

/**
 * Response from a write operation (upsert, delete, patch).
 */
export interface WriteResponse {
  /** Number of rows affected. */
  affected_rows: number;
}

/**
 * Metadata about a namespace.
 */
export interface NamespaceMetadata {
  /** Schema definition. */
  schema: Record<string, unknown>;
  /** Approximate number of rows. */
  approx_row_count: number;
  /** Additional metadata fields. */
  [key: string]: unknown;
}

/**
 * Summary info for a namespace in a list response.
 */
export interface NamespaceSummary {
  /** Namespace identifier. */
  id: string;
}

/**
 * Response from listing namespaces.
 */
export interface NamespaceListResponse {
  /** List of namespace summaries. */
  namespaces: NamespaceSummary[];
  /** Cursor for the next page, or null if no more pages. */
  next_cursor: string | null;
}

/**
 * Result of a recall debug operation.
 */
export interface RecallResult {
  /** Average recall score. */
  avg_recall: number;
  /** Average exhaustive count. */
  avg_exhaustive: number;
  /** Average ANN count. */
  avg_ann: number;
  /** Number of queries run. */
  num_queries: number;
  /** Top-K used. */
  top_k: number;
}
