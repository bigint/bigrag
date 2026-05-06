use serde::Deserialize;

/// Per-collection usage.
#[derive(Debug, Clone, Deserialize)]
pub struct CollectionUsage {
    /// Collection name.
    pub collection: String,
    /// Document count.
    pub documents: u32,
    /// Chunk count.
    pub chunks: u64,
    /// Storage bytes.
    pub storage_bytes: u64,
    /// Embedding tokens.
    pub embedding_tokens: u64,
    /// Estimated embedding cost.
    pub embedding_cost_usd_estimate: f64,
    /// Query count.
    pub queries: u32,
    /// Average query latency.
    pub avg_latency_ms: f64,
}

/// Usage response.
#[derive(Debug, Clone, Deserialize)]
pub struct UsageResponse {
    /// Window length in days.
    pub window_days: u32,
    /// Total queries.
    pub queries_total: u32,
    /// Average queries per day.
    pub queries_per_day_avg: f64,
    /// Total documents.
    pub documents_total: u32,
    /// Total chunks.
    pub chunks_total: u64,
    /// Total storage bytes.
    pub storage_bytes_total: u64,
    /// Total embedding tokens.
    pub embedding_tokens_total: u64,
    /// Estimated embedding cost.
    pub embedding_cost_usd_estimate: f64,
    /// Per-collection usage.
    pub by_collection: Vec<CollectionUsage>,
}
