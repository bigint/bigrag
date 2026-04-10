use reqwest::multipart::Form;

use crate::client::BigRag;
use crate::core::urlencode;
use crate::error::BigRagError;
use crate::files::FileInput;
use crate::sse::SseStream;
use crate::types::common::StatusResponse;
use crate::types::documents::{
    BatchDeleteDocumentsResponse, BatchGetDocumentsResponse, BatchStatusResponse, Document,
    DocumentChunkListResponse, DocumentListOptions, DocumentListResponse, S3IngestBody,
    S3IngestResponse, S3JobListResponse,
};

/// Documents resource — upload, manage, and retrieve documents.
pub struct Documents<'a> {
    pub(crate) client: &'a BigRag,
}

impl Documents<'_> {
    /// Upload a single file to a collection.
    pub async fn upload(
        &self,
        collection: &str,
        file: impl Into<FileInput>,
        metadata: Option<serde_json::Value>,
    ) -> Result<Document, BigRagError> {
        let file_input: FileInput = file.into();
        let part = file_input.into_multipart_part().await?;
        let mut form = Form::new().part("file", part);
        if let Some(meta) = metadata {
            form = form.text("metadata", serde_json::to_string(&meta)?);
        }
        let path = format!("/v1/collections/{}/documents", urlencode(collection));
        self.client.transport.post_multipart(&path, form).await
    }

    /// Upload multiple files to a collection.
    pub async fn batch_upload(
        &self,
        collection: &str,
        files: Vec<FileInput>,
        metadata: Option<serde_json::Value>,
    ) -> Result<DocumentListResponse, BigRagError> {
        let mut form = Form::new();
        for file_input in files {
            let part = file_input.into_multipart_part().await?;
            form = form.part("files", part);
        }
        if let Some(meta) = metadata {
            form = form.text("metadata", serde_json::to_string(&meta)?);
        }
        let path = format!(
            "/v1/collections/{}/documents/batch/upload",
            urlencode(collection)
        );
        self.client.transport.post_multipart(&path, form).await
    }

    /// List documents in a collection.
    pub async fn list(
        &self,
        collection: &str,
        options: Option<DocumentListOptions>,
    ) -> Result<DocumentListResponse, BigRagError> {
        let mut query = Vec::new();
        if let Some(opts) = options {
            if let Some(status) = opts.status {
                query.push(("status".into(), status));
            }
            if let Some(limit) = opts.limit {
                query.push(("limit".into(), limit.to_string()));
            }
            if let Some(offset) = opts.offset {
                query.push(("offset".into(), offset.to_string()));
            }
        }
        let path = format!("/v1/collections/{}/documents", urlencode(collection));
        self.client.transport.get(&path, query).await
    }

    /// Get a document by ID within a collection.
    pub async fn get(
        &self,
        collection: &str,
        document_id: &str,
    ) -> Result<Document, BigRagError> {
        let path = format!(
            "/v1/collections/{}/documents/{}",
            urlencode(collection),
            urlencode(document_id)
        );
        self.client.transport.get(&path, vec![]).await
    }

    /// Delete a document.
    pub async fn delete(
        &self,
        collection: &str,
        document_id: &str,
    ) -> Result<StatusResponse, BigRagError> {
        let path = format!(
            "/v1/collections/{}/documents/{}",
            urlencode(collection),
            urlencode(document_id)
        );
        self.client.transport.delete(&path).await
    }

    /// Reprocess a document.
    pub async fn reprocess(
        &self,
        collection: &str,
        document_id: &str,
    ) -> Result<StatusResponse, BigRagError> {
        let path = format!(
            "/v1/collections/{}/documents/{}/reprocess",
            urlencode(collection),
            urlencode(document_id)
        );
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
    }

    /// Get chunks for a document.
    pub async fn get_chunks(
        &self,
        collection: &str,
        document_id: &str,
    ) -> Result<DocumentChunkListResponse, BigRagError> {
        let path = format!(
            "/v1/collections/{}/documents/{}/chunks",
            urlencode(collection),
            urlencode(document_id)
        );
        self.client.transport.get(&path, vec![]).await
    }

    /// Get the download URL for a document's original file.
    pub fn get_file_url(&self, collection: &str, document_id: &str) -> String {
        format!(
            "{}/v1/collections/{}/documents/{}/file",
            self.client.config.base_url,
            urlencode(collection),
            urlencode(document_id)
        )
    }

    /// Get processing status for multiple documents.
    pub async fn batch_get_status(
        &self,
        collection: &str,
        document_ids: &[&str],
    ) -> Result<BatchStatusResponse, BigRagError> {
        let path = format!(
            "/v1/collections/{}/documents/batch/status",
            urlencode(collection)
        );
        let body = serde_json::json!({
            "document_ids": document_ids,
        });
        self.client.transport.post(&path, &body).await
    }

    /// Get full document objects for multiple IDs.
    pub async fn batch_get(
        &self,
        collection: &str,
        document_ids: &[&str],
    ) -> Result<BatchGetDocumentsResponse, BigRagError> {
        let path = format!(
            "/v1/collections/{}/documents/batch/get",
            urlencode(collection)
        );
        let body = serde_json::json!({
            "document_ids": document_ids,
        });
        self.client.transport.post(&path, &body).await
    }

    /// Delete multiple documents.
    pub async fn batch_delete(
        &self,
        collection: &str,
        document_ids: &[&str],
    ) -> Result<BatchDeleteDocumentsResponse, BigRagError> {
        let path = format!(
            "/v1/collections/{}/documents/batch/delete",
            urlencode(collection)
        );
        let body = serde_json::json!({
            "document_ids": document_ids,
        });
        self.client.transport.post(&path, &body).await
    }

    /// Start S3 ingestion for a collection.
    pub async fn ingest_s3(
        &self,
        collection: &str,
        body: S3IngestBody,
    ) -> Result<S3IngestResponse, BigRagError> {
        let path = format!("/v1/collections/{}/documents/s3", urlencode(collection));
        self.client.transport.post(&path, &body).await
    }

    /// List S3 ingestion jobs for a collection.
    pub async fn list_s3_jobs(
        &self,
        collection: &str,
    ) -> Result<S3JobListResponse, BigRagError> {
        let path = format!("/v1/collections/{}/s3-jobs", urlencode(collection));
        self.client.transport.get(&path, vec![]).await
    }

    /// Delete an S3 ingestion job.
    pub async fn delete_s3_job(
        &self,
        collection: &str,
        job_id: &str,
    ) -> Result<StatusResponse, BigRagError> {
        let path = format!(
            "/v1/collections/{}/s3-jobs/{}",
            urlencode(collection),
            urlencode(job_id)
        );
        self.client.transport.delete(&path).await
    }

    /// Re-sync an S3 ingestion job.
    pub async fn resync_s3_job(
        &self,
        collection: &str,
        job_id: &str,
    ) -> Result<StatusResponse, BigRagError> {
        let path = format!(
            "/v1/collections/{}/s3-jobs/{}/resync",
            urlencode(collection),
            urlencode(job_id)
        );
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
    }

    /// Get a document by ID (global, no collection scope).
    pub async fn get_by_id(&self, document_id: &str) -> Result<Document, BigRagError> {
        let path = format!("/v1/documents/{}", urlencode(document_id));
        self.client.transport.get(&path, vec![]).await
    }

    /// Get chunks for a document by ID (global, no collection scope).
    pub async fn get_chunks_by_id(
        &self,
        document_id: &str,
    ) -> Result<DocumentChunkListResponse, BigRagError> {
        let path = format!("/v1/documents/{}/chunks", urlencode(document_id));
        self.client.transport.get(&path, vec![]).await
    }

    /// Stream processing progress for a single document via SSE.
    pub async fn stream_progress(
        &self,
        collection: &str,
        document_id: &str,
    ) -> Result<SseStream, BigRagError> {
        let path = format!(
            "/v1/collections/{}/documents/{}/progress",
            urlencode(collection),
            urlencode(document_id)
        );
        let response = self.client.transport.get_stream(&path).await?;
        Ok(SseStream::new(response))
    }

    /// Stream processing progress for multiple documents via SSE.
    pub async fn stream_batch_progress(
        &self,
        collection: &str,
        document_ids: &[&str],
    ) -> Result<SseStream, BigRagError> {
        let ids = document_ids.join(",");
        let path = format!(
            "/v1/collections/{}/documents/batch/progress?ids={}",
            urlencode(collection),
            ids
        );
        let response = self.client.transport.get_stream(&path).await?;
        Ok(SseStream::new(response))
    }
}
