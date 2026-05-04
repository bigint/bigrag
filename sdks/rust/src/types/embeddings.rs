use serde::Deserialize;

/// Information about a supported embedding model.
#[derive(Debug, Clone, Deserialize)]
pub struct EmbeddingModelInfo {
    /// Provider name (e.g. `"openai"`, `"cohere"`).
    pub provider: String,
    /// Model identifier.
    pub model: String,
    /// Vector dimensionality produced by this model.
    pub dimension: u32,
    /// Human-readable description.
    pub description: String,
}

/// Response from `GET /v1/embeddings/models`.
#[derive(Debug, Clone, Deserialize)]
pub struct EmbeddingModelListResponse {
    /// Available embedding models.
    pub models: Vec<EmbeddingModelInfo>,
}
