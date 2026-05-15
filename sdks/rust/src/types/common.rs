use serde::{Deserialize, Serialize};

/// Generic status response from the API.
#[derive(Debug, Clone, Deserialize)]
pub struct StatusResponse {
    /// Status string, typically `"ok"`.
    pub status: String,
    /// Human-readable message.
    #[serde(default)]
    pub message: Option<String>,
}

/// Pagination parameters for list endpoints.
#[derive(Debug, Clone, Default, Serialize)]
pub struct PaginationOptions {
    /// Maximum number of results to return.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<u32>,
    /// Number of results to skip.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub offset: Option<u32>,
}

/// Response from `GET /health`.
#[derive(Debug, Clone, Deserialize)]
pub struct HealthResponse {
    /// Status string.
    pub status: String,
    /// Server version.
    pub version: String,
}

/// Response from `GET /health/ready`.
#[derive(Debug, Clone, Deserialize)]
pub struct ReadinessResponse {
    /// Status string (`"ok"` or `"degraded"`).
    pub status: String,
    /// Server version.
    pub version: String,
    /// Whether Postgres is reachable.
    pub postgres: bool,
    /// Whether configured vector-store clients are reachable.
    #[serde(default)]
    pub vector_store: bool,
    /// Vector store readiness mode.
    #[serde(default)]
    pub vector_store_provider: Option<String>,
    /// Whether Qdrant is reachable, when configured.
    #[serde(default)]
    pub qdrant: Option<bool>,
    /// Whether Redis is reachable.
    pub redis: bool,
    /// Whether the embedding provider is reachable.
    pub embedding: Option<bool>,
    /// Source of embedding configuration (`"settings"`, `"preset"`, `"collection"`).
    #[serde(default)]
    pub embedding_source: Option<String>,
    /// Error message if the embedding provider check failed.
    pub embedding_error: Option<String>,
}

/// Response from `GET /v1/stats`.
#[derive(Debug, Clone, Deserialize)]
pub struct PlatformStatsResponse {
    /// Total number of collections.
    pub collections: u32,
    /// Document statistics.
    pub documents: DocumentStats,
    /// Total number of webhooks.
    pub webhooks: u32,
    /// Queue statistics.
    pub queue: QueueStats,
    /// Worker heartbeat statistics.
    #[serde(default)]
    pub workers: Option<WorkerStats>,
}

/// Document-level aggregate statistics.
#[derive(Debug, Clone, Deserialize)]
pub struct DocumentStats {
    /// Total documents across all collections.
    pub total: u32,
    /// Documents in `ready` state.
    pub ready: u32,
    /// Documents in `pending` state.
    pub pending: u32,
    /// Documents in `processing` state.
    pub processing: u32,
    /// Documents in `failed` state.
    pub failed: u32,
    /// Total chunks across all documents.
    pub total_chunks: u64,
    /// Total tokens across all documents.
    pub total_tokens: u64,
    /// Total file size in bytes.
    pub total_size_bytes: u64,
}

/// Processing queue statistics.
#[derive(Debug, Clone, Deserialize)]
pub struct QueueStats {
    /// Jobs waiting in queue.
    pub queued: u32,
    /// Jobs completed successfully.
    pub completed: u32,
    /// Jobs that failed.
    pub failed: u32,
    /// Jobs pending start.
    pub pending: u32,
    /// Jobs currently processing.
    pub processing: u32,
    /// Jobs delayed for retry.
    #[serde(default)]
    pub retrying: Option<u32>,
    /// Jobs retained after terminal failure.
    #[serde(default)]
    pub dead_lettered: Option<u32>,
    /// Processing jobs with active leases.
    #[serde(default)]
    pub leased_processing: Option<u32>,
    /// Processing jobs whose leases are stale.
    #[serde(default)]
    pub stale_processing: Option<u32>,
}

/// Background worker heartbeat statistics.
#[derive(Debug, Clone, Deserialize)]
pub struct WorkerStats {
    /// Whether a recent worker heartbeat exists.
    pub online: bool,
    /// Last worker heartbeat timestamp.
    pub heartbeat_at: Option<String>,
    /// Seconds since the last worker heartbeat.
    pub heartbeat_age_seconds: Option<u64>,
}
