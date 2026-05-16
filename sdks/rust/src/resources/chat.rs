use std::collections::VecDeque;
use std::pin::Pin;
use std::task::{Context, Poll};

use futures_core::Stream;

use crate::client::BigRag;
use crate::error::BigRagError;
use crate::types::chat::{ChatBody, ChatCreateResponse, ChatStreamEvent};

/// Chats resource — generated answers for one playground turn.
pub struct Chats<'a> {
    pub(crate) client: &'a BigRag,
}

impl Chats<'_> {
    /// Create a non-streaming chat turn.
    pub async fn create(&self, body: ChatBody) -> Result<ChatCreateResponse, BigRagError> {
        #[derive(serde::Serialize)]
        struct NonStreamingBody<'a> {
            #[serde(flatten)]
            body: &'a ChatBody,
            stream: bool,
        }
        let payload = NonStreamingBody {
            body: &body,
            stream: false,
        };
        self.client.transport.post("/v1/chat", &payload).await
    }

    /// Create a streaming chat turn.
    pub async fn stream(&self, body: ChatBody) -> Result<ChatStream, BigRagError> {
        #[derive(serde::Serialize)]
        struct StreamingBody<'a> {
            #[serde(flatten)]
            body: &'a ChatBody,
            stream: bool,
        }
        let payload = StreamingBody {
            body: &body,
            stream: true,
        };
        let response = self
            .client
            .transport
            .post_stream("/v1/chat", &payload)
            .await?;
        Ok(ChatStream::new(response))
    }
}

/// A stream of chat Server-Sent Events.
pub struct ChatStream {
    inner: Pin<Box<dyn Stream<Item = Result<bytes::Bytes, reqwest::Error>> + Send>>,
    parser: ChatSseParser,
    pending: VecDeque<Result<ChatStreamEvent, BigRagError>>,
}

impl ChatStream {
    pub(crate) fn new(response: reqwest::Response) -> Self {
        Self {
            inner: Box::pin(response.bytes_stream()),
            parser: ChatSseParser::new(),
            pending: VecDeque::new(),
        }
    }
}

impl Stream for ChatStream {
    type Item = Result<ChatStreamEvent, BigRagError>;

    fn poll_next(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        if let Some(event) = self.pending.pop_front() {
            return Poll::Ready(Some(event));
        }

        match self.inner.as_mut().poll_next(cx) {
            Poll::Ready(Some(Ok(chunk))) => {
                let text = String::from_utf8_lossy(&chunk);
                self.pending = self.parser.push(&text).into();

                if let Some(event) = self.pending.pop_front() {
                    Poll::Ready(Some(event))
                } else {
                    cx.waker().wake_by_ref();
                    Poll::Pending
                }
            }
            Poll::Ready(Some(Err(e))) => {
                Poll::Ready(Some(Err(BigRagError::Connection(e.to_string()))))
            }
            Poll::Ready(None) => Poll::Ready(None),
            Poll::Pending => Poll::Pending,
        }
    }
}

struct ChatSseParser {
    buffer: String,
}

impl ChatSseParser {
    fn new() -> Self {
        Self {
            buffer: String::new(),
        }
    }

    fn push(&mut self, text: &str) -> Vec<Result<ChatStreamEvent, BigRagError>> {
        self.buffer.push_str(text);
        let mut events = Vec::new();

        while let Some((pos, len)) = find_sse_boundary(&self.buffer) {
            let block = self.buffer[..pos].to_string();
            self.buffer = self.buffer[pos + len..].to_string();

            if let Some(event) = parse_chat_sse_block(&block) {
                events.push(event);
            }
        }

        events
    }
}

fn find_sse_boundary(buffer: &str) -> Option<(usize, usize)> {
    match (buffer.find("\n\n"), buffer.find("\r\n\r\n")) {
        (Some(lf), Some(crlf)) if lf < crlf => Some((lf, 2)),
        (Some(_lf), Some(crlf)) => Some((crlf, 4)),
        (Some(lf), None) => Some((lf, 2)),
        (None, Some(crlf)) => Some((crlf, 4)),
        (None, None) => None,
    }
}

fn parse_chat_sse_block(block: &str) -> Option<Result<ChatStreamEvent, BigRagError>> {
    let mut event = "message".to_string();
    let mut data = Vec::new();

    for raw in block.lines() {
        let line = raw.trim_end_matches('\r');
        if line.is_empty() || line.starts_with(':') {
            continue;
        }
        if let Some(value) = line.strip_prefix("event:") {
            event = trim_sse_value(value).to_string();
        } else if let Some(value) = line.strip_prefix("data:") {
            data.push(trim_sse_value(value).to_string());
        }
    }

    if data.is_empty() {
        return None;
    }

    let payload = data.join("\n");
    if payload == "[DONE]" {
        return None;
    }

    Some(
        serde_json::from_str(&payload)
            .map(|data| ChatStreamEvent { event, data })
            .map_err(BigRagError::from),
    )
}

fn trim_sse_value(value: &str) -> &str {
    value.strip_prefix(' ').unwrap_or(value)
}

#[cfg(test)]
mod tests {
    use super::ChatSseParser;

    #[test]
    fn parses_chat_stream_events() {
        let mut parser = ChatSseParser::new();

        assert!(parser.push("event: delta\r\ndata: {\"delta\"").is_empty());
        let events = parser.push(":\"hi\"}\r\n\r\n");

        assert_eq!(events.len(), 1);
        let event = events.into_iter().next().unwrap().unwrap();
        assert_eq!(event.event, "delta");
        assert_eq!(event.data["delta"], "hi");
    }

    #[test]
    fn ignores_comments_and_done_marker() {
        let mut parser = ChatSseParser::new();
        let events =
            parser.push(": ping\n\ndata: [DONE]\n\nevent: error\ndata: {\"message\":\"bad\"}\n\n");

        assert_eq!(events.len(), 1);
        let event = events.into_iter().next().unwrap().unwrap();
        assert_eq!(event.event, "error");
        assert_eq!(event.data["message"], "bad");
    }
}
