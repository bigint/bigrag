use crate::client::BigRag;
use crate::error::BigRagError;
use crate::types::evaluations::{EvalBody, EvalResponse};

/// Evaluations resource.
pub struct Evaluations<'a> {
    pub(crate) client: &'a BigRag,
}

impl Evaluations<'_> {
    /// Run a retrieval evaluation.
    pub async fn run(&self, body: EvalBody) -> Result<EvalResponse, BigRagError> {
        self.client.transport.post("/v1/evaluation", &body).await
    }
}
