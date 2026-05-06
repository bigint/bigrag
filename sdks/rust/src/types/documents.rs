use serde::{Deserialize, Serialize};

/// Latest ingestion progress snapshot for a document.
#[derive(Debug, Clone, Deserialize)]
pub struct DocumentProgress {
    /// Document ID.
    pub document_id: String,
    /// Collection name.
    pub collection_name: String,
    /// Current ingestion step.
    pub step: String,
    /// Step status.
    pub status: String,
    /// Human-readable progress message.
    pub message: String,
    /// Completed fraction from 0.0 to 1.0.
    pub progress: f64,
    /// Step-specific progress detail.
    pub detail: serde_json::Value,
}

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
    /// Content hash used for deduplication.
    pub content_hash: Option<String>,
    /// Whether this response points at an existing deduplicated document.
    #[serde(default)]
    pub deduped: bool,
    /// Latest ingestion progress snapshot.
    #[serde(default)]
    pub progress: Option<DocumentProgress>,
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

/// Options for listing document chunks.
#[derive(Debug, Clone, Default, Serialize)]
pub struct DocumentChunkOptions {
    /// Maximum number of chunks to return.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<u32>,
    /// Number of chunks to skip.
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
    /// Latest ingestion progress snapshot.
    #[serde(default)]
    pub progress: Option<DocumentProgress>,
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
