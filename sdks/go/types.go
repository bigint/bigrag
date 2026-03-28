package bigrag

// UpsertRow represents a single row to upsert into a namespace.
type UpsertRow struct {
	// ID is the unique identifier for the row. Must be a string, int, or uint.
	ID interface{} `json:"id"`
	// Vector is the embedding vector for the row. May be nil if upserting metadata only.
	Vector []float64 `json:"vector,omitempty"`
	// Attributes holds arbitrary key-value metadata associated with the row.
	Attributes map[string]interface{} `json:"attributes,omitempty"`
}

// PatchRow represents a partial update to an existing row.
type PatchRow struct {
	// ID is the unique identifier for the row to patch.
	ID interface{} `json:"id"`
	// Attributes holds the attributes to update. Unspecified attributes are preserved.
	// Setting an attribute value to nil removes it.
	Attributes map[string]interface{} `json:"attributes,omitempty"`
}

// QueryOptions configures a query request.
type QueryOptions struct {
	// RankBy specifies the ranking strategy as a nested slice structure.
	// Examples:
	//   ["vector", "ANN", [0.1, 0.2, ...]]
	//   ["content", "BM25", "search query"]
	//   ["published_at", "Desc"]
	//   ["Sum", [clause1, clause2]]
	RankBy interface{} `json:"rank_by,omitempty"`

	// TopK is the maximum number of results to return.
	TopK int `json:"top_k,omitempty"`

	// Filters is the filter expression for the query.
	// Uses the bigRAG filter DSL: ["field", "Operator", value]
	Filters interface{} `json:"filters,omitempty"`

	// IncludeAttributes controls which attributes to return.
	// Set to true for all, false for none, or a []string for specific attributes.
	IncludeAttributes interface{} `json:"include_attributes,omitempty"`

	// IncludeVectors controls whether vectors are included in results.
	IncludeVectors *bool `json:"include_vectors,omitempty"`

	// DistanceCutoff excludes results with distance above this threshold.
	DistanceCutoff *float64 `json:"distance_cutoff,omitempty"`

	// RecallTarget sets the desired recall level (0.0 to 1.0).
	RecallTarget *float64 `json:"recall_target,omitempty"`

	// Cursor is used for paginated queries.
	Cursor string `json:"cursor,omitempty"`

	// Consistency sets the query consistency level ("strong" or "eventual").
	Consistency string `json:"consistency,omitempty"`

	// Queries is used for multi-query (hybrid search) requests.
	// Each element should be a map with "rank_by" and optionally "limit".
	Queries []map[string]interface{} `json:"queries,omitempty"`

	// Fusion configures the fusion method for multi-query requests.
	Fusion *FusionOptions `json:"fusion,omitempty"`

	// Aggregations specifies aggregations to compute alongside results.
	Aggregations []map[string]interface{} `json:"aggregations,omitempty"`
}

// FusionOptions configures the fusion method for multi-query requests.
type FusionOptions struct {
	// Method is the fusion algorithm: "rrf", "linear", or "dbsf".
	Method string `json:"method"`
	// K is the RRF constant (default 60). Only used with "rrf".
	K *int `json:"k,omitempty"`
	// Weights are the per-query weights. Only used with "linear".
	Weights []float64 `json:"weights,omitempty"`
}

// QueryResponse is the response from a query operation.
type QueryResponse struct {
	// Rows contains the matched rows.
	Rows []QueryRow `json:"rows"`
	// NextCursor is the pagination cursor for the next page, or empty if no more results.
	NextCursor string `json:"next_cursor,omitempty"`
	// Performance contains query performance metrics.
	Performance *QueryPerformance `json:"performance,omitempty"`
	// Billing contains query billing information.
	Billing map[string]interface{} `json:"billing,omitempty"`
}

// QueryRow is a single row in query results.
type QueryRow struct {
	// ID is the row identifier.
	ID interface{} `json:"id"`
	// Dist is the distance or score for this result.
	Dist *float64 `json:"dist,omitempty"`
	// Vector is the row vector, if requested.
	Vector []float64 `json:"vector,omitempty"`
	// Attributes holds row metadata, if requested.
	Attributes map[string]interface{} `json:"attributes,omitempty"`
}

// QueryPerformance contains query execution metrics.
type QueryPerformance struct {
	CacheHitRatio        *float64 `json:"cache_hit_ratio,omitempty"`
	CacheTemperature     string   `json:"cache_temperature,omitempty"`
	ServerTotalMs        *float64 `json:"server_total_ms,omitempty"`
	QueryExecutionMs     *float64 `json:"query_execution_ms,omitempty"`
	ExhaustiveSearchCount *int    `json:"exhaustive_search_count,omitempty"`
	ApproxNamespaceSize  *int     `json:"approx_namespace_size,omitempty"`
}

// WriteResponse is the response from a write operation (upsert, delete, patch).
type WriteResponse struct {
	Status       string `json:"status,omitempty"`
	RowsAffected int    `json:"rows_affected,omitempty"`
	RowsUpserted int    `json:"rows_upserted,omitempty"`
	RowsPatched  int    `json:"rows_patched,omitempty"`
	RowsDeleted  int    `json:"rows_deleted,omitempty"`
	RowsRemaining *bool `json:"rows_remaining,omitempty"`
}

// NamespaceMetadata contains metadata about a namespace.
type NamespaceMetadata struct {
	ID              string                 `json:"id,omitempty"`
	Schema          map[string]interface{} `json:"schema,omitempty"`
	ApproxRowCount  int                    `json:"approx_row_count,omitempty"`
	DocCount        int                    `json:"doc_count,omitempty"`
	VectorCount     int                    `json:"vector_count,omitempty"`
	IndexState      map[string]interface{} `json:"index_state,omitempty"`
	Storage         map[string]interface{} `json:"storage,omitempty"`
	CreatedAt       string                 `json:"created_at,omitempty"`
	UpdatedAt       string                 `json:"updated_at,omitempty"`
}

// NamespaceListResponse is the response from listing namespaces.
type NamespaceListResponse struct {
	// Namespaces is the list of namespace summaries.
	Namespaces []NamespaceSummary `json:"namespaces"`
	// NextCursor is the pagination cursor for the next page, or empty if done.
	NextCursor string `json:"next_cursor,omitempty"`
}

// NamespaceSummary is summary info for a namespace in a list response.
type NamespaceSummary struct {
	// ID is the namespace identifier.
	ID string `json:"id"`
	// DocCount is the number of documents in the namespace.
	DocCount int `json:"doc_count,omitempty"`
}

// NamespaceListOptions configures a namespace list request.
type NamespaceListOptions struct {
	// Prefix filters namespaces by name prefix.
	Prefix string `json:"prefix,omitempty"`
	// Cursor is the pagination cursor from a previous response.
	Cursor string `json:"cursor,omitempty"`
	// PageSize is the number of results per page (default 100, max 1000).
	PageSize int `json:"page_size,omitempty"`
}

// HealthResponse is the response from the health check endpoint.
type HealthResponse struct {
	Status  string `json:"status"`
	Version string `json:"version,omitempty"`
}

// RecallOptions configures a recall evaluation request.
type RecallOptions struct {
	// NumQueries is the number of random queries to run.
	NumQueries int `json:"num,omitempty"`
	// TopK is the number of results per query.
	TopK int `json:"top_k,omitempty"`
}

// RecallResult is the response from a recall evaluation.
type RecallResult struct {
	AvgRecall      float64 `json:"avg_recall"`
	AvgExhaustive  float64 `json:"avg_exhaustive"`
	AvgANN         float64 `json:"avg_ann"`
	NumQueries     int     `json:"num_queries"`
	TopK           int     `json:"top_k"`
}

// UpsertOptions configures an upsert request.
type UpsertOptions struct {
	// DistanceMetric sets the distance metric for the namespace.
	// Only used on the first upsert: "cosine_distance" or "euclidean_squared".
	DistanceMetric string `json:"distance_metric,omitempty"`
	// Schema sets explicit schema on write.
	Schema map[string]interface{} `json:"schema,omitempty"`
	// Condition is a filter expression for conditional writes.
	Condition interface{} `json:"upsert_condition,omitempty"`
	// DisableBackpressure disables 429 backpressure for bulk imports.
	DisableBackpressure bool `json:"-"`
}

// DeleteByFilterOptions configures a delete-by-filter request.
type DeleteByFilterOptions struct {
	// MaxAffected is the maximum number of documents to delete (max 5,000,000).
	MaxAffected int `json:"max_affected,omitempty"`
	// AllowPartial allows partial completion if more documents match.
	AllowPartial bool `json:"allow_partial,omitempty"`
}
