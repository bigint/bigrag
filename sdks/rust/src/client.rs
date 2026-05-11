use std::time::Duration;

use crate::core::Transport;
use crate::error::RagComputerError;
use crate::files::FileInput;
use crate::resources::admin::Admin;
use crate::resources::auth::Auth;
use crate::resources::chat::Chats;
use crate::resources::collections::Collections;
use crate::resources::connectors::Connectors;
use crate::resources::documents::Documents;
use crate::resources::evaluations::Evaluations;
use crate::resources::queries::Queries;
use crate::resources::vectors::Vectors;
use crate::resources::webhooks::Webhooks;
use crate::sse::SseStream;
use crate::types::analytics::AnalyticsResponse;
use crate::types::chat::{ChatBody, ChatCreateResponse};
use crate::types::collections::CollectionStatsResponse;
use crate::types::common::{
    HealthResponse, PlatformStatsResponse, ReadinessResponse, StatusResponse,
};
use crate::types::documents::{
    BatchDeleteDocumentsResponse, BatchGetDocumentsResponse, BatchStatusResponse, Document,
    DocumentChunkListResponse, DocumentChunkOptions, DocumentListOptions, DocumentListResponse,
    UploadSession, UploadSessionCreateRequest, UploadSessionFileResponse,
};
use crate::types::embeddings::EmbeddingModelListResponse;
use crate::types::query::{QueryBody, QueryResponse};
use crate::types::usage::UsageResponse;

const DEFAULT_BASE_URL: &str = "http://localhost:6100";
const DEFAULT_TIMEOUT_SECS: u64 = 120;
const DEFAULT_MAX_RETRIES: u32 = 2;

/// Configuration for the rag.computer client.
#[derive(Debug, Clone)]
pub struct RagComputerConfig {
    /// Base URL of the rag.computer API.
    pub base_url: String,
    /// API key for authentication.
    pub api_key: Option<String>,
    /// Request timeout.
    pub timeout: Duration,
    /// Maximum number of retries for transient errors.
    pub max_retries: u32,
}

/// The rag.computer client.
///
/// # Examples
///
/// ```no_run
/// use rag_computer::RagComputer;
///
/// # async fn example() -> Result<(), rag_computer::RagComputerError> {
/// let client = RagComputer::new("http://localhost:6100", "sk-...");
/// let collections = client.collections().list(None).await?;
/// # Ok(())
/// # }
/// ```
pub struct RagComputer {
    pub(crate) transport: Transport,
    pub(crate) config: RagComputerConfig,
}

impl RagComputer {
    /// Create a new client with a base URL and API key.
    pub fn new(base_url: &str, api_key: &str) -> Self {
        let config = RagComputerConfig {
            base_url: base_url.trim_end_matches('/').to_string(),
            api_key: Some(api_key.to_string()),
            timeout: Duration::from_secs(DEFAULT_TIMEOUT_SECS),
            max_retries: DEFAULT_MAX_RETRIES,
        };
        let transport = Transport::new(
            &config.base_url,
            config.api_key.clone(),
            config.timeout,
            config.max_retries,
        );
        Self { transport, config }
    }

    /// Create a new client from environment variables.
    ///
    /// Reads `RAG_COMPUTER_BASE_URL` (default: `http://localhost:6100`) and
    /// `RAG_COMPUTER_API_KEY` (optional).
    pub fn from_env() -> Result<Self, RagComputerError> {
        let base_url =
            std::env::var("RAG_COMPUTER_BASE_URL").unwrap_or_else(|_| DEFAULT_BASE_URL.to_string());
        let api_key = std::env::var("RAG_COMPUTER_API_KEY").ok();
        let config = RagComputerConfig {
            base_url: base_url.trim_end_matches('/').to_string(),
            api_key,
            timeout: Duration::from_secs(DEFAULT_TIMEOUT_SECS),
            max_retries: DEFAULT_MAX_RETRIES,
        };
        let transport = Transport::new(
            &config.base_url,
            config.api_key.clone(),
            config.timeout,
            config.max_retries,
        );
        Ok(Self { transport, config })
    }

    /// Create a builder for fine-grained configuration.
    pub fn builder() -> RagComputerBuilder {
        RagComputerBuilder::default()
    }

    /// Access the admin resource.
    pub fn admin(&self) -> Admin<'_> {
        Admin { client: self }
    }

    /// Access the auth resource.
    pub fn auth(&self) -> Auth<'_> {
        Auth { client: self }
    }

    /// Access the chat resource.
    pub fn chat(&self) -> Chats<'_> {
        Chats { client: self }
    }

    /// Access the collections resource.
    pub fn collections(&self) -> Collections<'_> {
        Collections { client: self }
    }

    /// Access the connectors resource.
    pub fn connectors(&self) -> Connectors<'_> {
        Connectors { client: self }
    }

    /// Access the documents resource.
    pub fn documents(&self) -> Documents<'_> {
        Documents { client: self }
    }

    /// Access the evaluations resource.
    pub fn evaluations(&self) -> Evaluations<'_> {
        Evaluations { client: self }
    }

    /// Access the queries resource.
    pub fn queries(&self) -> Queries<'_> {
        Queries { client: self }
    }

    /// Access the vectors resource.
    pub fn vectors(&self) -> Vectors<'_> {
        Vectors { client: self }
    }

    /// Access the webhooks resource.
    pub fn webhooks(&self) -> Webhooks<'_> {
        Webhooks { client: self }
    }

    /// Create a collection-scoped client for convenience.
    pub fn collection(&self, name: &str) -> CollectionClient<'_> {
        CollectionClient {
            client: self,
            name: name.to_string(),
        }
    }

    /// Check API health.
    pub async fn health(&self) -> Result<HealthResponse, RagComputerError> {
        self.transport.get("/health", vec![]).await
    }

    /// Check API readiness (includes dependency health).
    pub async fn readiness(&self) -> Result<ReadinessResponse, RagComputerError> {
        self.transport.get("/health/ready", vec![]).await
    }

    /// Get platform-wide statistics.
    pub async fn stats(&self) -> Result<PlatformStatsResponse, RagComputerError> {
        self.transport.get("/v1/stats", vec![]).await
    }

    /// List available embedding models.
    pub async fn embedding_models(&self) -> Result<EmbeddingModelListResponse, RagComputerError> {
        self.transport.get("/v1/embeddings/models", vec![]).await
    }

    /// Get analytics for a collection.
    pub async fn analytics(&self, collection: &str) -> Result<AnalyticsResponse, RagComputerError> {
        let path = format!(
            "/v1/collections/{}/analytics",
            crate::core::urlencode(collection)
        );
        self.transport.get(&path, vec![]).await
    }

    /// Get workspace usage analytics.
    pub async fn usage(&self, window_days: Option<u32>) -> Result<UsageResponse, RagComputerError> {
        let mut query = Vec::new();
        if let Some(window_days) = window_days {
            query.push(("window_days".to_string(), window_days.to_string()));
        }
        self.transport.get("/v1/usage", query).await
    }
}

/// Builder for creating a [`RagComputer`] client with custom configuration.
#[derive(Default)]
pub struct RagComputerBuilder {
    base_url: Option<String>,
    api_key: Option<String>,
    timeout: Option<Duration>,
    max_retries: Option<u32>,
    reqwest_client: Option<reqwest::Client>,
}

impl RagComputerBuilder {
    /// Set the base URL.
    pub fn base_url(mut self, url: &str) -> Self {
        self.base_url = Some(url.to_string());
        self
    }

    /// Set the API key.
    pub fn api_key(mut self, key: &str) -> Self {
        self.api_key = Some(key.to_string());
        self
    }

    /// Set the request timeout.
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = Some(timeout);
        self
    }

    /// Set the maximum number of retries.
    pub fn max_retries(mut self, retries: u32) -> Self {
        self.max_retries = Some(retries);
        self
    }

    /// Provide a pre-configured `reqwest::Client`.
    pub fn reqwest_client(mut self, client: reqwest::Client) -> Self {
        self.reqwest_client = Some(client);
        self
    }

    /// Build the client.
    pub fn build(self) -> Result<RagComputer, RagComputerError> {
        let config = RagComputerConfig {
            base_url: self
                .base_url
                .unwrap_or_else(|| DEFAULT_BASE_URL.to_string())
                .trim_end_matches('/')
                .to_string(),
            api_key: self.api_key,
            timeout: self
                .timeout
                .unwrap_or(Duration::from_secs(DEFAULT_TIMEOUT_SECS)),
            max_retries: self.max_retries.unwrap_or(DEFAULT_MAX_RETRIES),
        };

        let transport = if let Some(http) = self.reqwest_client {
            Transport::with_client(
                http,
                &config.base_url,
                config.api_key.clone(),
                config.timeout,
                config.max_retries,
            )
        } else {
            Transport::new(
                &config.base_url,
                config.api_key.clone(),
                config.timeout,
                config.max_retries,
            )
        };

        Ok(RagComputer { transport, config })
    }
}

/// A collection-scoped client for convenience.
///
/// All methods automatically use the bound collection name.
///
/// # Examples
///
/// ```no_run
/// use rag_computer::RagComputer;
///
/// # async fn example() -> Result<(), rag_computer::RagComputerError> {
/// let client = RagComputer::new("http://localhost:6100", "sk-...");
/// let col = client.collection("my-collection");
/// let docs = col.list_documents(None).await?;
/// # Ok(())
/// # }
/// ```
pub struct CollectionClient<'a> {
    pub(crate) client: &'a RagComputer,
    pub(crate) name: String,
}

impl CollectionClient<'_> {
    /// Upload a file to this collection.
    pub async fn upload(
        &self,
        file: impl Into<FileInput>,
        metadata: Option<serde_json::Value>,
    ) -> Result<Document, RagComputerError> {
        self.client
            .documents()
            .upload(&self.name, file, metadata)
            .await
    }

    /// Batch upload files to this collection.
    pub async fn batch_upload(
        &self,
        files: Vec<FileInput>,
        metadata: Option<serde_json::Value>,
    ) -> Result<DocumentListResponse, RagComputerError> {
        self.client
            .documents()
            .batch_upload(&self.name, files, metadata)
            .await
    }

    /// Create an upload session for this collection.
    pub async fn create_upload_session(
        &self,
        body: UploadSessionCreateRequest,
    ) -> Result<UploadSession, RagComputerError> {
        self.client
            .documents()
            .create_upload_session(&self.name, body)
            .await
    }

    /// Get an upload session.
    pub async fn get_upload_session(
        &self,
        session_id: &str,
    ) -> Result<UploadSession, RagComputerError> {
        self.client
            .documents()
            .get_upload_session(&self.name, session_id)
            .await
    }

    /// Upload one file into an upload session.
    pub async fn upload_session_file(
        &self,
        session_id: &str,
        file: impl Into<FileInput>,
        client_item_id: Option<&str>,
    ) -> Result<UploadSessionFileResponse, RagComputerError> {
        self.client
            .documents()
            .upload_session_file(&self.name, session_id, file, client_item_id)
            .await
    }

    /// Complete an upload session.
    pub async fn complete_upload_session(
        &self,
        session_id: &str,
    ) -> Result<UploadSession, RagComputerError> {
        self.client
            .documents()
            .complete_upload_session(&self.name, session_id)
            .await
    }

    /// Cancel an upload session.
    pub async fn cancel_upload_session(
        &self,
        session_id: &str,
    ) -> Result<StatusResponse, RagComputerError> {
        self.client
            .documents()
            .cancel_upload_session(&self.name, session_id)
            .await
    }

    /// List documents in this collection.
    pub async fn list_documents(
        &self,
        options: Option<DocumentListOptions>,
    ) -> Result<DocumentListResponse, RagComputerError> {
        self.client.documents().list(&self.name, options).await
    }

    /// Get a document by ID in this collection.
    pub async fn get_document(&self, document_id: &str) -> Result<Document, RagComputerError> {
        self.client.documents().get(&self.name, document_id).await
    }

    /// Delete a document from this collection.
    pub async fn delete_document(
        &self,
        document_id: &str,
    ) -> Result<StatusResponse, RagComputerError> {
        self.client
            .documents()
            .delete(&self.name, document_id)
            .await
    }

    /// Reprocess a document in this collection.
    pub async fn reprocess_document(
        &self,
        document_id: &str,
    ) -> Result<StatusResponse, RagComputerError> {
        self.client
            .documents()
            .reprocess(&self.name, document_id)
            .await
    }

    /// Get chunks for a document in this collection.
    pub async fn get_document_chunks(
        &self,
        document_id: &str,
    ) -> Result<DocumentChunkListResponse, RagComputerError> {
        self.get_document_chunks_with_options(document_id, None)
            .await
    }

    /// Get chunks for a document in this collection with pagination options.
    pub async fn get_document_chunks_with_options(
        &self,
        document_id: &str,
        options: Option<DocumentChunkOptions>,
    ) -> Result<DocumentChunkListResponse, RagComputerError> {
        self.client
            .documents()
            .get_chunks_with_options(&self.name, document_id, options)
            .await
    }

    /// Get batch document status.
    pub async fn batch_get_status(
        &self,
        document_ids: &[&str],
    ) -> Result<BatchStatusResponse, RagComputerError> {
        self.client
            .documents()
            .batch_get_status(&self.name, document_ids)
            .await
    }

    /// Get batch documents.
    pub async fn batch_get_documents(
        &self,
        document_ids: &[&str],
    ) -> Result<BatchGetDocumentsResponse, RagComputerError> {
        self.client
            .documents()
            .batch_get(&self.name, document_ids)
            .await
    }

    /// Batch delete documents.
    pub async fn batch_delete(
        &self,
        document_ids: &[&str],
    ) -> Result<BatchDeleteDocumentsResponse, RagComputerError> {
        self.client
            .documents()
            .batch_delete(&self.name, document_ids)
            .await
    }

    /// Query this collection.
    pub async fn query(&self, body: QueryBody) -> Result<QueryResponse, RagComputerError> {
        self.client.queries().query(&self.name, body).await
    }

    /// Create a chat turn against this collection.
    pub async fn chat(&self, mut body: ChatBody) -> Result<ChatCreateResponse, RagComputerError> {
        if body.collection.is_none() {
            body.collection = Some(self.name.clone());
        }
        self.client.chat().create(body).await
    }

    /// Get collection statistics.
    pub async fn stats(&self) -> Result<CollectionStatsResponse, RagComputerError> {
        self.client.collections().stats(&self.name).await
    }

    /// Queue all ready/failed documents in this collection for re-embedding.
    pub async fn reembed(&self) -> Result<StatusResponse, RagComputerError> {
        self.client.collections().reembed(&self.name).await
    }

    /// Get collection analytics.
    pub async fn analytics(&self) -> Result<AnalyticsResponse, RagComputerError> {
        let path = format!(
            "/v1/collections/{}/analytics",
            crate::core::urlencode(&self.name)
        );
        self.client.transport.get(&path, vec![]).await
    }

    /// Stream real-time events for this collection via SSE.
    pub async fn stream_events(&self) -> Result<SseStream, RagComputerError> {
        self.client.collections().stream_events(&self.name).await
    }
}
