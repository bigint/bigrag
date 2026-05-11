use crate::client::BigRag;
use crate::core::urlencode;
use crate::error::BigRagError;
use crate::types::query::{
    BatchQueryBody, BatchQueryResponse, MultiQueryBody, MultiQueryResponse, QueryBody,
    QueryResponse,
};

/// Queries resource — search collections.
pub struct Queries<'a> {
    pub(crate) client: &'a BigRag,
}

impl Queries<'_> {
    /// Query a single collection.
    pub async fn query(
        &self,
        collection: &str,
        body: QueryBody,
    ) -> Result<QueryResponse, BigRagError> {
        let path = format!("/v1/collections/{}/query", urlencode(collection));
        self.client.transport.post(&path, &body).await
    }

    /// Query across multiple collections.
    pub async fn multi_query(
        &self,
        body: MultiQueryBody,
    ) -> Result<MultiQueryResponse, BigRagError> {
        self.client.transport.post("/v1/query", &body).await
    }

    /// Execute multiple queries in a single request.
    pub async fn batch_query(
        &self,
        body: BatchQueryBody,
    ) -> Result<BatchQueryResponse, BigRagError> {
        self.client.transport.post("/v1/batch/query", &body).await
    }
}
