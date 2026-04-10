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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_embedding_model_list() {
        let json = r#"{"models":[{"provider":"openai","model":"text-embedding-3-small","dimension":1536,"description":"OpenAI small"}]}"#;
        let resp: EmbeddingModelListResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.models.len(), 1);
        assert_eq!(resp.models[0].dimension, 1536);
    }
}
