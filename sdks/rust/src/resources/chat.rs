use crate::client::RagComputer;
use crate::error::RagComputerError;
use crate::types::chat::{
    ChatBody, ChatCreateResponse, ChatDeleteResponse, ChatDetailResponse, ChatListResponse,
    ChatUpdateBody,
};

/// Chats resource — generated answers with persisted conversations.
pub struct Chats<'a> {
    pub(crate) client: &'a RagComputer,
}

impl Chats<'_> {
    /// Create a non-streaming chat turn.
    pub async fn create(&self, mut body: ChatBody) -> Result<ChatCreateResponse, RagComputerError> {
        body.stream = Some(false);
        self.client.transport.post("/v1/chat", &body).await
    }

    /// List owned conversations.
    pub async fn list(
        &self,
        limit: Option<u32>,
        offset: Option<u32>,
    ) -> Result<ChatListResponse, RagComputerError> {
        let mut query = Vec::new();
        if let Some(limit) = limit {
            query.push(("limit".to_string(), limit.to_string()));
        }
        if let Some(offset) = offset {
            query.push(("offset".to_string(), offset.to_string()));
        }
        self.client.transport.get("/v1/chat", query).await
    }

    /// Get a conversation and its messages.
    pub async fn get(&self, conversation_id: &str) -> Result<ChatDetailResponse, RagComputerError> {
        let path = format!("/v1/chat/{}", crate::core::urlencode(conversation_id));
        self.client.transport.get(&path, vec![]).await
    }

    /// Rename a conversation.
    pub async fn update_title(
        &self,
        conversation_id: &str,
        title: &str,
    ) -> Result<ChatDetailResponse, RagComputerError> {
        let path = format!("/v1/chat/{}", crate::core::urlencode(conversation_id));
        let body = ChatUpdateBody {
            title: title.to_string(),
        };
        self.client.transport.patch(&path, &body).await
    }

    /// Delete a conversation.
    pub async fn delete(
        &self,
        conversation_id: &str,
    ) -> Result<ChatDeleteResponse, RagComputerError> {
        let path = format!("/v1/chat/{}", crate::core::urlencode(conversation_id));
        self.client.transport.delete(&path).await
    }
}
