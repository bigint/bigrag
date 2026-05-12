use serde::{Deserialize, Serialize};

use crate::types::query::SearchMode;

/// Body for a production chat turn.
#[derive(Debug, Clone, Default, Serialize)]
pub struct ChatBody {
    /// User message to answer.
    pub message: String,
    /// Existing conversation ID for follow-up turns.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub conversation_id: Option<String>,
    /// Collection to query when starting a new conversation.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub collection: Option<String>,
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
    /// Total retrieval latency in milliseconds.
    pub total_ms: f64,
}

/// Stored chat message.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatMessage {
    /// Message ID.
    pub id: String,
    /// Conversation ID.
    pub conversation_id: String,
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

/// Stored chat conversation.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatConversation {
    /// Conversation ID.
    pub id: String,
    /// Display title.
    pub title: String,
    /// Bound collection.
    pub collection: Option<String>,
    /// Provider.
    pub model_provider: String,
    /// Model.
    pub model: String,
    /// Temperature.
    pub temperature: f64,
    /// Default retrieval top-k.
    pub top_k: u32,
    /// Default retrieval mode.
    pub search_mode: String,
    /// Default minimum score.
    pub min_score: Option<f64>,
    /// Default rerank override.
    pub rerank: Option<bool>,
    /// Number of messages.
    pub message_count: u32,
    /// ISO creation timestamp.
    pub created_at: String,
    /// ISO update timestamp.
    pub updated_at: String,
    /// ISO timestamp for latest message.
    pub last_message_at: Option<String>,
}

/// Conversation list response.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatListResponse {
    /// Conversations.
    pub conversations: Vec<ChatConversation>,
    /// Total matching conversations.
    pub total: u32,
}

/// Conversation detail response.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatDetailResponse {
    /// Conversation metadata.
    pub conversation: ChatConversation,
    /// Stored messages.
    pub messages: Vec<ChatMessage>,
}

/// Non-streaming chat response.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatCreateResponse {
    /// Conversation metadata.
    pub conversation: ChatConversation,
    /// Stored user message.
    pub message: ChatMessage,
    /// Stored assistant message.
    pub assistant_message: ChatMessage,
    /// Retrieved sources.
    pub sources: Vec<ChatSource>,
    /// Retrieval timings.
    pub timings: Option<ChatTimings>,
}

/// Delete response.
#[derive(Debug, Clone, Deserialize)]
pub struct ChatDeleteResponse {
    /// Deleted status.
    pub status: String,
}

/// Body for renaming a conversation.
#[derive(Debug, Clone, Serialize)]
pub struct ChatUpdateBody {
    /// New title.
    pub title: String,
}
