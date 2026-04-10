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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_analytics_response() {
        let json = r#"{
            "collection": "docs",
            "period_24h": {"query_count": 10, "avg_latency_ms": 50.5, "avg_score": 0.85, "avg_result_count": 5.2},
            "period_7d": {"query_count": 70, "avg_latency_ms": 48.0, "avg_score": 0.82, "avg_result_count": 4.8},
            "period_30d": {"query_count": 300, "avg_latency_ms": 52.1, "avg_score": 0.80, "avg_result_count": 5.0},
            "top_queries": [{"query": "how to deploy", "count": 15}]
        }"#;
        let resp: AnalyticsResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.collection, "docs");
        assert_eq!(resp.period_24h.query_count, 10);
        assert_eq!(resp.top_queries.len(), 1);
        assert_eq!(resp.top_queries[0].count, 15);
    }
}
