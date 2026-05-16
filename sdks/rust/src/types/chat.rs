use serde::{Deserialize, Serialize};

use crate::types::query::SearchMode;

/// Body for a production chat turn.
#[derive(Debug, Clone, Default, Serialize)]
pub struct ChatBody {
    /// User message to answer.
    pub message: String,
    /// Collection to query.
    pub collection: String,
    /// Chat provider (`openai` or `openai_compatible`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model_provider: Option<String>,
    /// Chat model name.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    /// LLM temperature.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub temperature: Option<f64>,
    /// Number of chunks to retrieve.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
    /// Retrieval mode.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub search_mode: Option<SearchMode>,
    /// Minimum source score.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_score: Option<f64>,
    /// Rerank override.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rerank: Option<bool>,
    /// Metadata filters.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub filters: Option<serde_json::Value>,
    /// System prompt override.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_prompt: Option<String>,
    /// Per-request provider API key.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provider_api_key: Option<String>,
    /// OpenAI-compatible base URL override.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provider_base_url: Option<String>,
}

/// Source chunk used by a chat answer.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatSource {
    /// Source ID.
    pub id: String,
    /// Source text.
    pub text: String,
    /// Retrieval score.
    pub score: f64,
    /// Document ID.
    pub document_id: Option<String>,
    /// Document filename when available.
    pub document_filename: Option<String>,
    /// Chunk index.
    pub chunk_index: Option<u32>,
    /// Page number when available.
    pub page_no: Option<u32>,
    /// Character start offset.
    pub char_start: Option<u32>,
    /// Character end offset.
    pub char_end: Option<u32>,
    /// Source metadata.
    pub metadata: serde_json::Value,
}

/// Retrieval timings for a chat turn.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatTimings {
    /// Embedding latency in milliseconds.
    pub embed_ms: f64,
    /// Search latency in milliseconds.
    pub search_ms: f64,
    /// Reranking latency in milliseconds.
    pub rerank_ms: f64,
    /// Cache lookup latency in milliseconds.
    pub cache_ms: f64,
    /// Total retrieval latency in milliseconds.
    pub total_ms: f64,
    /// Whether the retrieval results came from cache.
    pub cache_hit: bool,
}

/// Chat message returned for the current turn.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatMessage {
    /// Message ID.
    pub id: String,
    /// Message role.
    pub role: String,
    /// Message content.
    pub content: String,
    /// Completion status.
    pub status: String,
    /// Error message when status is `error`.
    pub error_message: Option<String>,
    /// Provider used for assistant messages.
    pub model_provider: Option<String>,
    /// Model used for assistant messages.
    pub model: Option<String>,
    /// Retrieval payload.
    pub retrieval: serde_json::Value,
    /// Sources used by assistant messages.
    pub sources: Vec<ChatSource>,
    /// ISO timestamp.
    pub created_at: String,
}

/// Non-streaming chat response.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatCreateResponse {
    /// User message.
    pub message: ChatMessage,
    /// Assistant message.
    pub assistant_message: ChatMessage,
    /// Retrieved sources.
    pub sources: Vec<ChatSource>,
    /// Retrieval timings.
    pub timings: Option<ChatTimings>,
}

/// Streaming chat SSE event.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatStreamEvent {
    /// SSE event name.
    pub event: String,
    /// Event payload.
    pub data: serde_json::Value,
}
