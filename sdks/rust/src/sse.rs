use std::collections::VecDeque;
use std::pin::Pin;
use std::task::{Context, Poll};

use futures_core::Stream;

use crate::error::BigRagError;
use crate::types::sse::ProgressEvent;

/// Incrementally parses SSE text into `ProgressEvent` values.
pub(crate) struct SseParser {
    buffer: String,
}

impl SseParser {
    pub fn new() -> Self {
        Self {
            buffer: String::new(),
        }
    }

    /// Push a chunk of text and return any complete events found.
    pub fn push(&mut self, text: &str) -> Vec<ProgressEvent> {
        self.buffer.push_str(text);
        let mut events = Vec::new();

        while let Some(pos) = self.buffer.find("\n\n") {
            let block = self.buffer[..pos].to_string();
            self.buffer = self.buffer[pos + 2..].to_string();

            for line in block.lines() {
                if let Some(json_str) = line.strip_prefix("data: ") {
                    if let Ok(event) = serde_json::from_str::<ProgressEvent>(json_str) {
                        events.push(event);
                    }
                }
                // Skip comments (": heartbeat") and other lines
            }
        }

        events
    }
}

/// A stream of SSE progress events from the bigRAG API.
///
/// Implements `futures_core::Stream<Item = Result<ProgressEvent, BigRagError>>`.
/// Consume with `StreamExt::next()` from `futures-util` or `tokio-stream`.
pub struct SseStream {
    inner: Pin<Box<dyn Stream<Item = Result<bytes::Bytes, reqwest::Error>> + Send>>,
    parser: SseParser,
    pending: VecDeque<ProgressEvent>,
}

impl SseStream {
    /// Create an SSE stream from a raw reqwest response.
    pub(crate) fn new(response: reqwest::Response) -> Self {
        Self {
            inner: Box::pin(response.bytes_stream()),
            parser: SseParser::new(),
            pending: VecDeque::new(),
        }
    }
}

impl Stream for SseStream {
    type Item = Result<ProgressEvent, BigRagError>;

    fn poll_next(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        // Yield any buffered events first.
        if let Some(event) = self.pending.pop_front() {
            return Poll::Ready(Some(Ok(event)));
        }

        // Try to read more data from the byte stream.
        match self.inner.as_mut().poll_next(cx) {
            Poll::Ready(Some(Ok(chunk))) => {
                let text = String::from_utf8_lossy(&chunk);
                let mut events: VecDeque<_> = self.parser.push(&text).into();

                if let Some(first) = events.pop_front() {
                    self.pending = events;
                    Poll::Ready(Some(Ok(first)))
                } else {
                    // Got data but no complete event yet, wake and retry.
                    cx.waker().wake_by_ref();
                    Poll::Pending
                }
            }
            Poll::Ready(Some(Err(e))) => {
                Poll::Ready(Some(Err(BigRagError::Connection(e.to_string()))))
            }
            Poll::Ready(None) => Poll::Ready(None), // Stream ended.
            Poll::Pending => Poll::Pending,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_sse_lines_data() {
        let mut parser = SseParser::new();
        let events =
            parser.push("data: {\"step\":\"chunking\",\"message\":\"ok\",\"progress\":50.0}\n\n");
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].step, "chunking");
        assert_eq!(events[0].progress, 50.0);
    }

    #[test]
    fn test_parse_sse_lines_skips_heartbeat() {
        let mut parser = SseParser::new();
        let events = parser.push(": heartbeat\n\n");
        assert_eq!(events.len(), 0);
    }

    #[test]
    fn test_parse_sse_lines_handles_partial() {
        let mut parser = SseParser::new();
        let events = parser.push("data: {\"step\":\"chunk");
        assert_eq!(events.len(), 0);
        let events = parser.push("ing\",\"message\":\"ok\",\"progress\":50.0}\n\n");
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].step, "chunking");
    }

    #[test]
    fn test_parse_sse_lines_multiple_events() {
        let mut parser = SseParser::new();
        let input = "data: {\"step\":\"a\",\"message\":\"\",\"progress\":0.0}\n\ndata: {\"step\":\"b\",\"message\":\"\",\"progress\":100.0}\n\n";
        let events = parser.push(input);
        assert_eq!(events.len(), 2);
        assert_eq!(events[0].step, "a");
        assert_eq!(events[1].step, "b");
    }
}
