use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// A bigRAG collection.
#[derive(Debug, Clone, Deserialize)]
pub struct Collection {
    /// Unique collection ID.
    pub id: String,
    /// Collection name.
    pub name: String,
    /// Collection description.
    pub description: String,
    /// Embedding provider (`"openai"` or `"cohere"`).
    pub embedding_provider: String,
    /// Embedding model name.
    pub embedding_model: String,
    /// Vector dimensionality.
    pub dimension: u32,
    /// Chunk size in tokens.
    pub chunk_size: u32,
    /// Chunk overlap in tokens.
    pub chunk_overlap: u32,
    /// Chunking algorithm (`"paragraph"` or `"recursive"`).
    pub chunk_strategy: String,
    /// Milvus index type (`"IVF_FLAT"` or `"HNSW"`).
    pub index_type: String,
    /// Optional metadata field used as a tenant partition key.
    pub tenant_field: Option<String>,
    /// Whether this collection validates document metadata against a schema.
    pub has_metadata_schema: bool,
    /// Number of documents in the collection.
    pub document_count: u32,
    /// Whether an embedding API key is configured.
    pub has_api_key: bool,
    /// Whether reranking is enabled.
    pub reranking_enabled: bool,
    /// Reranking model name.
    pub reranking_model: String,
    /// Whether a reranking API key is configured.
    pub has_reranking_api_key: bool,
    /// Default number of results to return.
    pub default_top_k: u32,
    /// Default minimum similarity score.
    pub default_min_score: Option<f64>,
    /// Default search mode.
    pub default_search_mode: String,
    /// User-defined metadata.
    pub metadata: serde_json::Value,
    /// Creation timestamp.
    pub created_at: String,
    /// Last update timestamp.
    pub updated_at: String,
}

/// Paginated list of collections.
#[derive(Debug, Clone, Deserialize)]
pub struct CollectionListResponse {
    /// Collections in this page.
    pub collections: Vec<Collection>,
    /// Total number of collections matching the query.
    pub total: u32,
}

/// Options for listing collections.
#[derive(Debug, Clone, Default, Serialize)]
pub struct CollectionListOptions {
    /// Filter by name prefix.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    /// Maximum number of results.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<u32>,
    /// Number of results to skip.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub offset: Option<u32>,
}

/// Body for creating a new collection.
#[derive(Debug, Clone, Default, Serialize)]
pub struct CreateCollectionBody {
    /// Collection name (required).
    pub name: String,
    /// Collection description.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    /// Embedding preset ID to derive provider/model/key/base URL/dimension.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_preset_id: Option<String>,
    /// Embedding provider (`"openai"` or `"cohere"`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_provider: Option<String>,
    /// Embedding model name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_model: Option<String>,
    /// Embedding API key (if not configured globally).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_api_key: Option<String>,
    /// OpenAI-compatible embedding base URL.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_base_url: Option<String>,
    /// Vector dimensionality (auto-detected if omitted).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dimension: Option<u32>,
    /// Chunk size in tokens (64–10000, default 512).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chunk_size: Option<u32>,
    /// Chunk overlap in tokens (must be less than chunk_size).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chunk_overlap: Option<u32>,
    /// Chunking algorithm (`"paragraph"` or `"recursive"`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chunk_strategy: Option<String>,
    /// Milvus index type (`"IVF_FLAT"` or `"HNSW"`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub index_type: Option<String>,
    /// Optional metadata field used as a tenant partition key.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tenant_field: Option<String>,
    /// Optional JSON Schema used to validate document metadata.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata_schema: Option<serde_json::Value>,
    /// User-defined metadata.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
    /// Enable reranking.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reranking_enabled: Option<bool>,
    /// Reranking model name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reranking_model: Option<String>,
    /// Reranking API key.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reranking_api_key: Option<String>,
    /// Default top-K results.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_top_k: Option<u32>,
    /// Default minimum similarity score.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_min_score: Option<f64>,
    /// Default search mode.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_search_mode: Option<String>,
}

/// Body for updating a collection.
#[derive(Debug, Clone, Default, Serialize)]
pub struct UpdateCollectionBody {
    /// Updated description.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    /// Updated metadata.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
    /// Updated reranking enabled flag.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reranking_enabled: Option<bool>,
    /// Updated reranking model.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reranking_model: Option<String>,
    /// Updated reranking API key.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reranking_api_key: Option<String>,
    /// Updated default top-K.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_top_k: Option<u32>,
    /// Updated default minimum score.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_min_score: Option<f64>,
    /// Updated default search mode.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_search_mode: Option<String>,
    /// Updated chunking algorithm.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chunk_strategy: Option<String>,
    /// Updated document metadata schema.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata_schema: Option<serde_json::Value>,
}

/// Response from `GET /v1/collections/{name}/stats`.
#[derive(Debug, Clone, Deserialize)]
pub struct CollectionStatsResponse {
    /// Collection name.
    pub collection: String,
    /// Number of documents.
    pub document_count: u32,
    /// Total chunks across all documents.
    pub total_chunks: u32,
    /// Total tokens.
    pub total_tokens: u64,
    /// Total size in bytes.
    pub total_size_bytes: u64,
    /// Document counts grouped by status.
    pub status_counts: HashMap<String, u32>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_collection() {
        let json = r#"{
            "id": "col-1", "name": "docs", "description": "My docs",
            "embedding_provider": "openai", "embedding_model": "text-embedding-3-small",
            "dimension": 1536, "chunk_size": 512, "chunk_overlap": 50,
            "chunk_strategy": "paragraph", "index_type": "IVF_FLAT",
            "tenant_field": null, "has_metadata_schema": false,
            "document_count": 42, "has_api_key": true,
            "reranking_enabled": false, "reranking_model": "rerank-v3.5",
            "has_reranking_api_key": false, "default_top_k": 10,
            "default_min_score": null, "default_search_mode": "semantic",
            "metadata": {}, "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"
        }"#;
        let col: Collection = serde_json::from_str(json).unwrap();
        assert_eq!(col.name, "docs");
        assert_eq!(col.dimension, 1536);
        assert_eq!(col.chunk_strategy, "paragraph");
        assert_eq!(col.index_type, "IVF_FLAT");
        assert_eq!(col.document_count, 42);
        assert_eq!(col.default_min_score, None);
    }

    #[test]
    fn test_serialize_create_collection_body_skips_none() {
        let body = CreateCollectionBody {
            name: "test".into(),
            ..Default::default()
        };
        let json = serde_json::to_value(&body).unwrap();
        assert_eq!(json["name"], "test");
        assert!(json.get("description").is_none());
        assert!(json.get("embedding_provider").is_none());
    }

    #[test]
    fn test_deserialize_collection_list_response() {
        let json = r#"{"collections":[{"id":"1","name":"a","description":"","embedding_provider":"openai","embedding_model":"m","dimension":768,"chunk_size":512,"chunk_overlap":50,"chunk_strategy":"paragraph","index_type":"IVF_FLAT","tenant_field":null,"has_metadata_schema":false,"document_count":0,"has_api_key":false,"reranking_enabled":false,"reranking_model":"","has_reranking_api_key":false,"default_top_k":10,"default_min_score":null,"default_search_mode":"semantic","metadata":{},"created_at":"","updated_at":""}],"total":1}"#;
        let resp: CollectionListResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.total, 1);
        assert_eq!(resp.collections[0].name, "a");
    }

    #[test]
    fn test_deserialize_collection_stats() {
        let json = r#"{"collection":"docs","document_count":10,"total_chunks":500,"total_tokens":10000,"total_size_bytes":5000000,"status_counts":{"ready":8,"failed":2}}"#;
        let resp: CollectionStatsResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.total_chunks, 500);
        assert_eq!(resp.status_counts["ready"], 8);
    }
}
