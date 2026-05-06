use serde::{Deserialize, Serialize};

use crate::types::query::SearchMode;

/// Evaluation case.
#[derive(Debug, Clone, Serialize)]
pub struct EvalCase {
    /// Query text.
    pub query: String,
    /// Relevant document or chunk IDs.
    pub relevant_ids: Vec<String>,
    /// Per-case top-k override.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
}

/// Evaluation request body.
#[derive(Debug, Clone, Serialize)]
pub struct EvalBody {
    /// Collection name.
    pub collection: String,
    /// Evaluation cases.
    pub cases: Vec<EvalCase>,
    /// Default top-k.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
    /// Search mode.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub search_mode: Option<SearchMode>,
}

/// Per-case evaluation result.
#[derive(Debug, Clone, Deserialize)]
pub struct EvalPerCase {
    /// Query text.
    pub query: String,
    /// Hit IDs.
    pub hit_ids: Vec<String>,
    /// Expected IDs.
    pub expected_ids: Vec<String>,
    /// Recall at k.
    pub recall_at_k: f64,
    /// Reciprocal rank.
    pub reciprocal_rank: f64,
    /// NDCG at k.
    pub ndcg_at_k: f64,
}

/// Evaluation response.
#[derive(Debug, Clone, Deserialize)]
pub struct EvalResponse {
    /// Collection name.
    pub collection: String,
    /// Number of cases.
    pub total_cases: u32,
    /// Average recall at k.
    pub recall_at_k_avg: f64,
    /// Mean reciprocal rank.
    pub mrr: f64,
    /// Average NDCG at k.
    pub ndcg_at_k_avg: f64,
    /// Per-case results.
    pub per_case: Vec<EvalPerCase>,
}
