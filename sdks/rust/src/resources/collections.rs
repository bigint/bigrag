use crate::client::RagComputer;
use crate::core::urlencode;
use crate::error::RagComputerError;
use crate::sse::SseStream;
use crate::types::collections::{
    Collection, CollectionListOptions, CollectionListResponse, CollectionStatsResponse,
    CreateCollectionBody, UpdateCollectionBody,
};
use crate::types::common::StatusResponse;

/// Collections resource — manage rag.computer collections.
pub struct Collections<'a> {
    pub(crate) client: &'a RagComputer,
}

impl Collections<'_> {
    /// List collections with optional filters.
    pub async fn list(
        &self,
        options: Option<CollectionListOptions>,
    ) -> Result<CollectionListResponse, RagComputerError> {
        let mut query = Vec::new();
        if let Some(opts) = options {
            if let Some(name) = opts.name {
                query.push(("name".into(), name));
            }
            if let Some(limit) = opts.limit {
                query.push(("limit".into(), limit.to_string()));
            }
            if let Some(offset) = opts.offset {
                query.push(("offset".into(), offset.to_string()));
            }
        }
        self.client.transport.get("/v1/collections", query).await
    }

    /// Get a collection by name.
    pub async fn get(&self, name: &str) -> Result<Collection, RagComputerError> {
        let path = format!("/v1/collections/{}", urlencode(name));
        self.client.transport.get(&path, vec![]).await
    }

    /// Create a new collection.
    pub async fn create(&self, body: CreateCollectionBody) -> Result<Collection, RagComputerError> {
        self.client.transport.post("/v1/collections", &body).await
    }

    /// Update a collection.
    pub async fn update(
        &self,
        name: &str,
        body: UpdateCollectionBody,
    ) -> Result<Collection, RagComputerError> {
        let path = format!("/v1/collections/{}", urlencode(name));
        self.client.transport.put(&path, &body).await
    }

    /// Delete a collection and all its data.
    pub async fn delete(&self, name: &str) -> Result<StatusResponse, RagComputerError> {
        let path = format!("/v1/collections/{}", urlencode(name));
        self.client.transport.delete(&path).await
    }

    /// Get collection statistics.
    pub async fn stats(&self, name: &str) -> Result<CollectionStatsResponse, RagComputerError> {
        let path = format!("/v1/collections/{}/stats", urlencode(name));
        self.client.transport.get(&path, vec![]).await
    }

    /// Truncate a collection (delete all documents but keep the collection).
    pub async fn truncate(&self, name: &str) -> Result<StatusResponse, RagComputerError> {
        let path = format!("/v1/collections/{}/truncate", urlencode(name));
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
    }

    /// Queue all ready/failed documents in a collection for re-embedding.
    pub async fn reembed(&self, name: &str) -> Result<StatusResponse, RagComputerError> {
        let path = format!("/v1/collections/{}/reembed", urlencode(name));
        self.client
            .transport
            .post(&path, &serde_json::Value::Null)
            .await
    }

    /// Stream real-time events for a collection via SSE.
    pub async fn stream_events(&self, name: &str) -> Result<SseStream, RagComputerError> {
        let path = format!("/v1/collections/{}/events", urlencode(name));
        let response = self.client.transport.get_stream(&path).await?;
        Ok(SseStream::new(response))
    }
}
