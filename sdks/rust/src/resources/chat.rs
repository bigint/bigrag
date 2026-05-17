use std::collections::VecDeque;
use std::pin::Pin;
use std::task::{Context, Poll};

use futures_core::Stream;

use crate::client::BigRag;
use crate::error::BigRagError;
use crate::sse::FrameParser;
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
    parser: FrameParser,
    pending: VecDeque<Result<ChatStreamEvent, BigRagError>>,
    byte_buf: Vec<u8>,
}

impl ChatStream {
    pub(crate) fn new(response: reqwest::Response) -> Self {
        Self {
            inner: Box::pin(response.bytes_stream()),
            parser: FrameParser::new(),
            pending: VecDeque::new(),
            byte_buf: Vec::new(),
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
                self.byte_buf.extend_from_slice(&chunk);
                let valid_up_to = match std::str::from_utf8(&self.byte_buf) {
                    Ok(_) => self.byte_buf.len(),
                    Err(e) => e.valid_up_to(),
                };
                let text = std::str::from_utf8(&self.byte_buf[..valid_up_to])
                    .unwrap_or("")
                    .to_string();
                self.byte_buf.drain(..valid_up_to);
                self.pending = self
                    .parser
                    .push(&text)
                    .into_iter()
                    .map(|frame| {
                        serde_json::from_str(&frame.data)
                            .map(|data| ChatStreamEvent {
                                event: frame.event,
                                data,
                            })
                            .map_err(BigRagError::from)
                    })
                    .collect();

                if let Some(event) = self.pending.pop_front() {
                    Poll::Ready(Some(event))
                } else {
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
