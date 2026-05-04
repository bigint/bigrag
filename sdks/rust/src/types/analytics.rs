use serde::Deserialize;

/// Response from `GET /v1/collections/{name}/analytics`.
#[derive(Debug, Clone, Deserialize)]
pub struct AnalyticsResponse {
    /// Collection name.
    pub collection: String,
    /// Stats for the last 24 hours.
    pub period_24h: PeriodStats,
    /// Stats for the last 7 days.
    pub period_7d: PeriodStats,
    /// Stats for the last 30 days.
    pub period_30d: PeriodStats,
    /// Most frequent queries.
    pub top_queries: Vec<TopQuery>,
}

/// Query statistics for a time period.
#[derive(Debug, Clone, Deserialize)]
pub struct PeriodStats {
    /// Number of queries in this period.
    pub query_count: u32,
    /// Average query latency in milliseconds.
    pub avg_latency_ms: f64,
    /// Average similarity score.
    pub avg_score: f64,
    /// Average number of results returned.
    pub avg_result_count: f64,
}

/// A frequently-used query string and its count.
#[derive(Debug, Clone, Deserialize)]
pub struct TopQuery {
    /// The query text.
    pub query: String,
    /// Number of times this query was issued.
    pub count: u32,
}
