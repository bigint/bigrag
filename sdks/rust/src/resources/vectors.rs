use crate::client::BigRag;
use crate::core::urlencode;
use crate::error::BigRagError;
use crate::types::vectors::{DeleteResponse, UpsertResponse, VectorEntry};

/// Vectors resource — manage raw vectors directly.
pub struct Vectors<'a> {
    pub(crate) client: &'a BigRag,
}

impl Vectors<'_> {
    /// Upsert vectors into a collection.
    pub async fn upsert(
        &self,
        collection: &str,
        vectors: Vec<VectorEntry>,
    ) -> Result<UpsertResponse, BigRagError> {
        let path = format!("/v1/collections/{}/vectors/upsert", urlencode(collection));
        let body = serde_json::json!({ "vectors": vectors });
        self.client.transport.post(&path, &body).await
    }

    /// Delete vectors by ID from a collection.
    pub async fn delete(
        &self,
        collection: &str,
        ids: &[&str],
    ) -> Result<DeleteResponse, BigRagError> {
        let path = format!("/v1/collections/{}/vectors/delete", urlencode(collection));
        let body = serde_json::json!({ "ids": ids });
        self.client.transport.post(&path, &body).await
    }
}
