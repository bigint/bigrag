use crate::client::RagComputer;
use crate::error::RagComputerError;
use crate::types::evaluations::{EvalBody, EvalResponse};

/// Evaluations resource.
pub struct Evaluations<'a> {
    pub(crate) client: &'a RagComputer,
}

impl Evaluations<'_> {
    /// Run a retrieval evaluation.
    pub async fn run(&self, body: EvalBody) -> Result<EvalResponse, RagComputerError> {
        self.client.transport.post("/v1/evaluation", &body).await
    }
}
