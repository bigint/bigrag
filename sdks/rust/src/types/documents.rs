use serde::{Deserialize, Serialize};

/// A document ingested into a collection.
#[derive(Debug, Clone, Deserialize)]
pub struct Document {
    /// Unique document ID.
    pub id: String,
    /// Collection this document belongs to.
    pub collection_id: String,
    /// Original filename.
    pub filename: String,
    /// File type (e.g. `"pdf"`, `"docx"`).
    pub file_type: String,
    /// File size in bytes.
    pub file_size: u64,
    /// Number of chunks produced.
    pub chunk_count: u32,
    /// Processing status (`"pending"`, `"processing"`, `"ready"`, `"failed"`).
    pub status: String,
    /// Error message if processing failed.
    pub error_message: Option<String>,
    /// User-defined metadata.
    pub metadata: serde_json::Value,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Paginated list of documents.
#[derive(Debug, Clone, Deserialize)]
pub struct DocumentListResponse {
    /// Documents in this page.
    pub documents: Vec<Document>,
    /// Total documents matching the query.
    pub total: u32,
}

/// Options for listing documents.
#[derive(Debug, Clone, Default, Serialize)]
pub struct DocumentListOptions {
    /// Filter by processing status.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
    /// Maximum number of results.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<u32>,
    /// Number of results to skip.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub offset: Option<u32>,
}

/// A chunk of a document.
#[derive(Debug, Clone, Deserialize)]
pub struct DocumentChunk {
    /// Unique chunk ID.
    pub id: String,
    /// Parent document ID.
    pub document_id: String,
    /// Position within the document (0-indexed).
    pub chunk_index: u32,
    /// Chunk text content.
    pub text: String,
    /// Chunk metadata.
    pub metadata: serde_json::Value,
}

/// List of document chunks.
#[derive(Debug, Clone, Deserialize)]
pub struct DocumentChunkListResponse {
    /// Chunks for this document.
    pub chunks: Vec<DocumentChunk>,
    /// Total number of chunks.
    pub total: u32,
}

/// Status of a single document in a batch status request.
#[derive(Debug, Clone, Deserialize)]
pub struct BatchStatusItem {
    /// Document ID.
    pub id: String,
    /// Processing status.
    pub status: String,
    /// Error message if processing failed.
    pub error_message: Option<String>,
    /// Number of chunks produced.
    pub chunk_count: u32,
}

/// Response from batch status check.
#[derive(Debug, Clone, Deserialize)]
pub struct BatchStatusResponse {
    /// Document statuses.
    pub documents: Vec<BatchStatusItem>,
    /// Total documents returned.
    pub total: u32,
}

/// Response from batch document retrieval.
#[derive(Debug, Clone, Deserialize)]
pub struct BatchGetDocumentsResponse {
    /// Full document objects.
    pub documents: Vec<Document>,
    /// Total documents returned.
    pub total: u32,
}

/// Response from batch document deletion.
#[derive(Debug, Clone, Deserialize)]
pub struct BatchDeleteDocumentsResponse {
    /// Status string.
    pub status: String,
    /// Number of documents successfully deleted.
    pub deleted: u32,
    /// Errors for documents that could not be deleted.
    pub errors: Vec<BatchDeleteError>,
}

/// An error from batch deletion.
#[derive(Debug, Clone, Deserialize)]
pub struct BatchDeleteError {
    /// Document ID that failed to delete.
    pub document_id: String,
    /// Error description.
    pub error: String,
}

/// Body for S3 ingestion.
#[derive(Debug, Clone, Default, Serialize)]
pub struct S3IngestBody {
    /// S3 bucket name (required).
    pub bucket: String,
    /// Object key prefix to filter by.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prefix: Option<String>,
    /// AWS region.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub region: Option<String>,
    /// Custom S3-compatible endpoint URL.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub endpoint_url: Option<String>,
    /// AWS access key.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub access_key: Option<String>,
    /// AWS secret key.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub secret_key: Option<String>,
    /// Skip request signing (for public buckets).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub no_sign_request: Option<bool>,
    /// Metadata applied to all ingested documents.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
    /// File types to ingest (empty means all supported types).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file_types: Option<Vec<String>>,
}

/// Response from S3 ingestion start.
#[derive(Debug, Clone, Deserialize)]
pub struct S3IngestResponse {
    /// Status string (typically `"accepted"`).
    pub status: String,
    /// Human-readable message.
    pub message: String,
}

/// An S3 ingestion job.
#[derive(Debug, Clone, Deserialize)]
pub struct S3Job {
    /// Unique job ID.
    pub id: String,
    /// Collection name.
    pub collection_name: String,
    /// S3 bucket.
    pub bucket: String,
    /// S3 prefix.
    pub prefix: String,
    /// AWS region.
    pub region: String,
    /// Job status (`"running"`, `"completed"`, `"failed"`).
    pub status: String,
    /// Total objects found in S3.
    pub total_found: u32,
    /// Objects successfully ingested.
    pub total_ingested: u32,
    /// Objects skipped.
    pub total_skipped: u32,
    /// Error message if the job failed.
    pub error_message: Option<String>,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Paginated list of S3 jobs.
#[derive(Debug, Clone, Deserialize)]
pub struct S3JobListResponse {
    /// S3 jobs.
    pub jobs: Vec<S3Job>,
    /// Total jobs.
    pub total: u32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_document() {
        let json = r#"{"id":"doc-1","collection_id":"col-1","filename":"report.pdf","file_type":"pdf","file_size":1024,"chunk_count":10,"status":"ready","error_message":null,"metadata":{},"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}"#;
        let doc: Document = serde_json::from_str(json).unwrap();
        assert_eq!(doc.filename, "report.pdf");
        assert_eq!(doc.status, "ready");
        assert_eq!(doc.error_message, None);
    }

    #[test]
    fn test_deserialize_batch_delete_response() {
        let json = r#"{"status":"ok","deleted":3,"errors":[{"document_id":"x","error":"not found"}]}"#;
        let resp: BatchDeleteDocumentsResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.deleted, 3);
        assert_eq!(resp.errors.len(), 1);
        assert_eq!(resp.errors[0].document_id, "x");
    }

    #[test]
    fn test_serialize_s3_ingest_body_skips_none() {
        let body = S3IngestBody {
            bucket: "my-bucket".into(),
            ..Default::default()
        };
        let json = serde_json::to_value(&body).unwrap();
        assert_eq!(json["bucket"], "my-bucket");
        assert!(json.get("prefix").is_none());
        assert!(json.get("access_key").is_none());
    }

    #[test]
    fn test_deserialize_s3_job() {
        let json = r#"{"id":"job-1","collection_name":"docs","bucket":"b","prefix":"p/","region":"us-east-1","status":"running","total_found":100,"total_ingested":50,"total_skipped":5,"error_message":null,"created_at":"","updated_at":""}"#;
        let job: S3Job = serde_json::from_str(json).unwrap();
        assert_eq!(job.status, "running");
        assert_eq!(job.total_found, 100);
    }
}
