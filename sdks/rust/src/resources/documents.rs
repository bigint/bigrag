use reqwest::multipart::Form;

use crate::client::BigRag;
use crate::core::urlencode;
use crate::error::BigRagError;
use crate::files::FileInput;
use crate::types::common::StatusResponse;
use crate::types::documents::{
    BatchDeleteDocumentsResponse, BatchGetDocumentsResponse, BatchStatusResponse, Document,
    DocumentChunkListResponse, DocumentChunkOptions, DocumentListOptions, DocumentListResponse,
    UploadSession, UploadSessionCreateRequest, UploadSessionFileResponse,
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

    /// Create a resumable upload session.
    pub async fn create_upload_session(
        &self,
        collection: &str,
        body: UploadSessionCreateRequest,
    ) -> Result<UploadSession, BigRagError> {
        let path = format!("/v1/collections/{}/upload-sessions", urlencode(collection));
        self.client.transport.post(&path, &body).await
    }

    /// Get a resumable upload session.
    pub async fn get_upload_session(
        &self,
        collection: &str,
        session_id: &str,
    ) -> Result<UploadSession, BigRagError> {
        let path = format!(
            "/v1/collections/{}/upload-sessions/{}",
            urlencode(collection),
            urlencode(session_id)
        );
        self.client.transport.get(&path, vec![]).await
    }

    /// Upload one file into a resumable upload session.
    pub async fn upload_session_file(
        &self,
        collection: &str,
        session_id: &str,
        file: impl Into<FileInput>,
        client_item_id: Option<&str>,
    ) -> Result<UploadSessionFileResponse, BigRagError> {
        let file_input: FileInput = file.into();
        let part = file_input.into_multipart_part().await?;
        let mut form = Form::new().part("file", part);
        if let Some(client_item_id) = client_item_id {
            form = form.text("client_item_id", client_item_id.to_string());
        }
        let path = format!(
            "/v1/collections/{}/upload-sessions/{}/files",
            urlencode(collection),
            urlencode(session_id)
        );
        self.client.transport.post_multipart(&path, form).await
    }

    /// Mark a resumable upload session complete.
    pub async fn complete_upload_session(
        &self,
        collection: &str,
        session_id: &str,
    ) -> Result<UploadSession, BigRagError> {
        let path = format!(
            "/v1/collections/{}/upload-sessions/{}/complete",
            urlencode(collection),
            urlencode(session_id)
        );
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
    }

    /// Cancel a resumable upload session.
    pub async fn cancel_upload_session(
        &self,
        collection: &str,
        session_id: &str,
    ) -> Result<StatusResponse, BigRagError> {
        let path = format!(
            "/v1/collections/{}/upload-sessions/{}/cancel",
            urlencode(collection),
            urlencode(session_id)
        );
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
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
    pub async fn get(&self, collection: &str, document_id: &str) -> Result<Document, BigRagError> {
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
        self.get_chunks_with_options(collection, document_id, None)
            .await
    }

    /// Get chunks for a document with pagination options.
    pub async fn get_chunks_with_options(
        &self,
        collection: &str,
        document_id: &str,
        options: Option<DocumentChunkOptions>,
    ) -> Result<DocumentChunkListResponse, BigRagError> {
        let mut query = Vec::new();
        if let Some(opts) = options {
            if let Some(limit) = opts.limit {
                query.push(("limit".into(), limit.to_string()));
            }
            if let Some(offset) = opts.offset {
                query.push(("offset".into(), offset.to_string()));
            }
        }
        let path = format!(
            "/v1/collections/{}/documents/{}/chunks",
            urlencode(collection),
            urlencode(document_id)
        );
        self.client.transport.get(&path, query).await
    }

    /// Get the download URL for a document's original file.
    ///
    /// The API requires authentication for this URL; pass the client's bearer
    /// token in an `Authorization` header when downloading it.
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
        self.get_chunks_by_id_with_options(document_id, None).await
    }

    /// Get chunks for a document by ID with pagination options.
    pub async fn get_chunks_by_id_with_options(
        &self,
        document_id: &str,
        options: Option<DocumentChunkOptions>,
    ) -> Result<DocumentChunkListResponse, BigRagError> {
        let mut query = Vec::new();
        if let Some(opts) = options {
            if let Some(limit) = opts.limit {
                query.push(("limit".into(), limit.to_string()));
            }
            if let Some(offset) = opts.offset {
                query.push(("offset".into(), offset.to_string()));
            }
        }
        let path = format!("/v1/documents/{}/chunks", urlencode(document_id));
        self.client.transport.get(&path, query).await
    }
}
