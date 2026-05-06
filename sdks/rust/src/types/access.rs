use serde::Deserialize;

/// Access log entry.
#[derive(Debug, Clone, Deserialize)]
pub struct AccessLogEntry {
    /// Entry ID.
    pub id: String,
    /// Actor user ID.
    pub actor_id: Option<String>,
    /// Actor email.
    pub actor_email: Option<String>,
    /// API key ID.
    pub api_key_id: Option<String>,
    /// API key name.
    pub api_key_name: Option<String>,
    /// Auth method.
    pub auth_method: Option<String>,
    /// Access action.
    pub action: String,
    /// Resource type.
    pub resource_type: String,
    /// Resource ID.
    pub resource_id: Option<String>,
    /// Collection name.
    pub collection_name: Option<String>,
    /// HTTP method.
    pub method: String,
    /// Request path.
    pub path: String,
    /// Matched route.
    pub route: Option<String>,
    /// HTTP status code.
    pub status_code: u16,
    /// Whether the request succeeded.
    pub success: bool,
    /// Request latency in milliseconds.
    pub latency_ms: f64,
    /// Request ID.
    pub request_id: Option<String>,
    /// Extra metadata.
    pub metadata: serde_json::Value,
    /// Client IP.
    pub ip: Option<String>,
    /// User agent.
    pub user_agent: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
}

/// Access log list response.
#[derive(Debug, Clone, Deserialize)]
pub struct AccessLogListResponse {
    /// Entries in this page.
    pub entries: Vec<AccessLogEntry>,
    /// Total matching entries.
    pub total: u32,
}

/// Access log bucket.
#[derive(Debug, Clone, Deserialize)]
pub struct AccessLogBucket {
    /// Bucket label.
    pub label: String,
    /// Event count.
    pub count: u32,
    /// Average latency.
    pub avg_latency_ms: Option<f64>,
}

/// Access log timeline point.
#[derive(Debug, Clone, Deserialize)]
pub struct AccessLogTimelinePoint {
    /// Timeline bucket timestamp.
    pub bucket: String,
    /// Event count.
    pub events: u32,
    /// Error count.
    pub errors: u32,
    /// Average latency.
    pub avg_latency_ms: f64,
}

/// Access log overview response.
#[derive(Debug, Clone, Deserialize)]
pub struct AccessLogOverviewResponse {
    /// Window length in days.
    pub window_days: u32,
    /// Total events.
    pub total_events: u32,
    /// Success rate.
    pub success_rate: f64,
    /// Error rate.
    pub error_rate: f64,
    /// Average latency.
    pub avg_latency_ms: f64,
    /// P95 latency.
    pub p95_latency_ms: f64,
    /// Unique users.
    pub unique_users: u32,
    /// Query event count.
    pub query_events: u32,
    /// Buckets by action.
    pub by_action: Vec<AccessLogBucket>,
    /// Latency buckets by action.
    pub latency_by_action: Vec<AccessLogBucket>,
    /// Timeline points.
    pub timeline: Vec<AccessLogTimelinePoint>,
    /// Recent entries.
    pub recent: Vec<AccessLogEntry>,
}
