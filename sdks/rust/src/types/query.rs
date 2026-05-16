use serde::{Deserialize, Serialize};

/// Search mode for query operations.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SearchMode {
    /// Vector similarity search.
    Semantic,
    /// Keyword/BM25 search.
    Keyword,
    /// Combined semantic + keyword search.
    Hybrid,
}

/// Body for a single-collection query.
#[derive(Debug, Clone, Default, Serialize)]
pub struct QueryBody {
    /// Search query text (required).
    pub query: String,
    /// Maximum number of results.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
    /// Metadata filters.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub filters: Option<serde_json::Value>,
    /// Minimum similarity score.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_score: Option<f64>,
    /// Search mode.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub search_mode: Option<SearchMode>,
    /// Whether to apply reranking.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rerank: Option<bool>,
}

/// A single query result.
#[derive(Debug, Clone, Deserialize)]
pub struct QueryResult {
    /// Result ID.
    pub id: String,
    /// Matched text content.
    pub text: String,
    /// Similarity score (0–1).
    pub score: f64,
    /// Source document ID.
    pub document_id: Option<String>,
    /// Source document filename.
    pub document_filename: Option<String>,
    /// Chunk index within the source document.
    pub chunk_index: Option<u32>,
    /// Source page number when available.
    pub page_no: Option<u32>,
    /// Source character start when available.
    pub char_start: Option<u32>,
    /// Source character end when available.
    pub char_end: Option<u32>,
    /// Result metadata.
    pub metadata: serde_json::Value,
}

/// Retrieval timings.
#[derive(Debug, Clone, Deserialize)]
pub struct QueryTimings {
    /// Embedding latency in milliseconds.
    pub embed_ms: f64,
    /// Search latency in milliseconds.
    pub search_ms: f64,
    /// Reranking latency in milliseconds.
    pub rerank_ms: f64,
    /// Cache lookup latency in milliseconds.
    pub cache_ms: f64,
    /// Total retrieval latency in milliseconds.
    pub total_ms: f64,
    /// Whether the retrieval results came from cache.
    pub cache_hit: bool,
}

/// Response from a single-collection query.
#[derive(Debug, Clone, Deserialize)]
pub struct QueryResponse {
    /// Matched results.
    pub results: Vec<QueryResult>,
    /// The query that was executed.
    pub query: String,
    /// Collection that was searched.
    pub collection: String,
    /// Total number of results.
    pub total: u32,
    /// Retrieval timings.
    pub timings: Option<QueryTimings>,
}

/// Body for a multi-collection query.
#[derive(Debug, Clone, Serialize)]
pub struct MultiQueryBody {
    /// Search query text (required).
    pub query: String,
    /// Collections to search across (required).
    pub collections: Vec<String>,
    /// Maximum number of results.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
    /// Metadata filters.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub filters: Option<serde_json::Value>,
    /// Minimum similarity score.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_score: Option<f64>,
    /// Search mode.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub search_mode: Option<SearchMode>,
    /// Whether to apply reranking.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rerank: Option<bool>,
}

/// A single result from a multi-collection query, includes source collection.
#[derive(Debug, Clone, Deserialize)]
pub struct MultiQueryResult {
    /// Result ID.
    pub id: String,
    /// Matched text content.
    pub text: String,
    /// Similarity score.
    pub score: f64,
    /// Source document ID.
    pub document_id: Option<String>,
    /// Source document filename.
    pub document_filename: Option<String>,
    /// Chunk index within the source document.
    pub chunk_index: Option<u32>,
    /// Collection this result came from.
    pub collection: String,
    /// Result metadata.
    pub metadata: serde_json::Value,
}

/// Response from a multi-collection query.
#[derive(Debug, Clone, Deserialize)]
pub struct MultiQueryResponse {
    /// Matched results across collections.
    pub results: Vec<MultiQueryResult>,
    /// The query that was executed.
    pub query: String,
    /// Collections that were searched.
    pub collections: Vec<String>,
    /// Total number of results.
    pub total: u32,
}

/// A single query within a batch query request.
#[derive(Debug, Clone, Serialize)]
pub struct BatchQueryItem {
    /// Collection to query.
    pub collection: String,
    /// Search query text.
    pub query: String,
    /// Maximum number of results.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
    /// Metadata filters.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub filters: Option<serde_json::Value>,
    /// Minimum similarity score.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_score: Option<f64>,
    /// Search mode.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub search_mode: Option<SearchMode>,
    /// Whether to apply reranking.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rerank: Option<bool>,
}

/// Body for a batch query request.
#[derive(Debug, Clone, Serialize)]
pub struct BatchQueryBody {
    /// Queries to execute (1–20).
    pub queries: Vec<BatchQueryItem>,
}

/// Response from a batch query.
#[derive(Debug, Clone, Deserialize)]
pub struct BatchQueryResponse {
    /// One `QueryResponse` per query in the batch.
    pub results: Vec<QueryResponse>,
}
