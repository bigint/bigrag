use crate::client::BigRag;
use crate::core::urlencode;
use crate::error::BigRagError;
use crate::types::common::StatusResponse;
use crate::types::connectors::{
    CreateGoogleSourceBody, GoogleAccount, GoogleDriveFileListResponse,
    GoogleOAuthStartUrlResponse, GoogleSource, GoogleSourceListResponse, GoogleSyncJob,
    GoogleSyncJobListResponse, UpdateGoogleSourceBody,
};

/// Connectors resource.
pub struct Connectors<'a> {
    pub(crate) client: &'a BigRag,
}

impl Connectors<'_> {
    /// Access Google Drive connector operations.
    pub fn google(&self) -> GoogleDrive<'_> {
        GoogleDrive {
            client: self.client,
        }
    }
}

/// Google Drive connector resource.
pub struct GoogleDrive<'a> {
    pub(crate) client: &'a BigRag,
}

impl GoogleDrive<'_> {
    /// Get current user's Google account status.
    pub async fn account(&self) -> Result<GoogleAccount, BigRagError> {
        self.client
            .transport
            .get("/v1/connectors/google/account", vec![])
            .await
    }

    /// List Google Drive files.
    pub async fn files(
        &self,
        parent_id: Option<&str>,
        query: Option<&str>,
        page_token: Option<&str>,
        page_size: Option<u32>,
    ) -> Result<GoogleDriveFileListResponse, BigRagError> {
        let mut params = vec![(
            "parent_id".to_string(),
            parent_id.unwrap_or("root").to_string(),
        )];
        if let Some(query) = query {
            params.push(("query".to_string(), query.to_string()));
        }
        if let Some(page_token) = page_token {
            params.push(("page_token".to_string(), page_token.to_string()));
        }
        if let Some(page_size) = page_size {
            params.push(("page_size".to_string(), page_size.to_string()));
        }
        self.client
            .transport
            .get("/v1/connectors/google/files", params)
            .await
    }

    /// Build a Google OAuth URL.
    pub async fn oauth_start_url(
        &self,
        redirect_path: Option<&str>,
    ) -> Result<GoogleOAuthStartUrlResponse, BigRagError> {
        let mut params = Vec::new();
        if let Some(redirect_path) = redirect_path {
            params.push(("redirect_path".to_string(), redirect_path.to_string()));
        }
        self.client
            .transport
            .get("/v1/connectors/google/oauth/start-url", params)
            .await
    }

    /// Disconnect current user's Google account.
    pub async fn disconnect(&self) -> Result<StatusResponse, BigRagError> {
        self.client
            .transport
            .post("/v1/connectors/google/disconnect", &serde_json::Value::Null)
            .await
    }

    /// List Google Drive sync sources.
    pub async fn sources(
        &self,
        collection: Option<&str>,
    ) -> Result<GoogleSourceListResponse, BigRagError> {
        let mut params = Vec::new();
        if let Some(collection) = collection {
            params.push(("collection".to_string(), collection.to_string()));
        }
        self.client
            .transport
            .get("/v1/connectors/google/sources", params)
            .await
    }

    /// Create a Google Drive sync source.
    pub async fn create_source(
        &self,
        body: CreateGoogleSourceBody,
    ) -> Result<GoogleSource, BigRagError> {
        self.client
            .transport
            .post("/v1/connectors/google/sources", &body)
            .await
    }

    /// Update a Google Drive sync source.
    pub async fn update_source(
        &self,
        source_id: &str,
        body: UpdateGoogleSourceBody,
    ) -> Result<GoogleSource, BigRagError> {
        let path = format!("/v1/connectors/google/sources/{}", urlencode(source_id));
        self.client.transport.patch(&path, &body).await
    }

    /// Delete a Google Drive sync source.
    pub async fn delete_source(&self, source_id: &str) -> Result<StatusResponse, BigRagError> {
        let path = format!("/v1/connectors/google/sources/{}", urlencode(source_id));
        self.client.transport.delete(&path).await
    }

    /// Trigger a Google Drive sync source.
    pub async fn sync_source(&self, source_id: &str) -> Result<GoogleSyncJob, BigRagError> {
        let path = format!(
            "/v1/connectors/google/sources/{}/sync",
            urlencode(source_id)
        );
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
    }

    /// List Google Drive sync jobs.
    pub async fn sync_jobs(
        &self,
        source_id: Option<&str>,
        limit: Option<u32>,
    ) -> Result<GoogleSyncJobListResponse, BigRagError> {
        self.sync_jobs_filtered(None, source_id, limit).await
    }

    /// List Google Drive sync jobs with an optional collection filter.
    pub async fn sync_jobs_filtered(
        &self,
        collection: Option<&str>,
        source_id: Option<&str>,
        limit: Option<u32>,
    ) -> Result<GoogleSyncJobListResponse, BigRagError> {
        let mut params = Vec::new();
        if let Some(collection) = collection {
            params.push(("collection".to_string(), collection.to_string()));
        }
        if let Some(source_id) = source_id {
            params.push(("source_id".to_string(), source_id.to_string()));
        }
        if let Some(limit) = limit {
            params.push(("limit".to_string(), limit.to_string()));
        }
        self.client
            .transport
            .get("/v1/connectors/google/sync-jobs", params)
            .await
    }
}
