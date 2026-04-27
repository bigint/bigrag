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
    /// Whether Milvus is reachable.
    pub milvus: bool,
    /// Whether Redis is reachable.
    pub redis: bool,
    /// Whether the embedding provider is reachable.
    pub embedding: Option<bool>,
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
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_status_response() {
        let json = r#"{"status":"ok","message":"Collection deleted"}"#;
        let resp: StatusResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.status, "ok");
        assert_eq!(resp.message.as_deref(), Some("Collection deleted"));
    }

    #[test]
    fn test_deserialize_health_response() {
        let json = r#"{"status":"ok","version":"1.2.3"}"#;
        let resp: HealthResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.version, "1.2.3");
    }

    #[test]
    fn test_deserialize_readiness_response() {
        let json = r#"{"status":"ok","version":"1.2.3","postgres":true,"milvus":true,"redis":true,"embedding":true}"#;
        let resp: ReadinessResponse = serde_json::from_str(json).unwrap();
        assert!(resp.postgres);
        assert!(resp.milvus);
        assert!(resp.redis);
        assert_eq!(resp.embedding, Some(true));
        assert_eq!(resp.embedding_error, None);
    }

    #[test]
    fn test_deserialize_platform_stats() {
        let json = r#"{
            "collections": 5,
            "documents": {
                "total": 100, "ready": 90, "pending": 5,
                "processing": 3, "failed": 2, "total_chunks": 5000,
                "total_tokens": 100000, "total_size_bytes": 50000000
            },
            "webhooks": 2,
            "queue": {
                "queued": 1, "completed": 95, "failed": 2,
                "pending": 1, "processing": 1
            }
        }"#;
        let resp: PlatformStatsResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.collections, 5);
        assert_eq!(resp.documents.total, 100);
        assert_eq!(resp.queue.completed, 95);
    }

    #[test]
    fn test_serialize_pagination_options() {
        let opts = PaginationOptions {
            limit: Some(50),
            offset: None,
        };
        let json = serde_json::to_value(&opts).unwrap();
        assert_eq!(json["limit"], 50);
        assert!(json.get("offset").is_none());
    }
}
