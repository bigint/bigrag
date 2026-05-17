use std::collections::VecDeque;
use std::pin::Pin;
use std::task::{Context, Poll};

use futures_core::Stream;

use crate::error::BigRagError;
use crate::types::sse::ProgressEvent;

pub(crate) struct SseFrame {
    pub event: String,
    pub data: String,
}

pub(crate) struct FrameParser {
    buffer: String,
}

impl FrameParser {
    pub fn new() -> Self {
        Self {
            buffer: String::new(),
        }
    }

    pub fn push(&mut self, text: &str) -> Vec<SseFrame> {
        self.buffer.push_str(text);
        let mut frames = Vec::new();
        while let Some((pos, len)) = find_boundary(&self.buffer) {
            let block = self.buffer[..pos].to_string();
            self.buffer.drain(..pos + len);
            if let Some(frame) = parse_block(&block) {
                frames.push(frame);
            }
        }
        frames
    }
}

fn find_boundary(buffer: &str) -> Option<(usize, usize)> {
    match (buffer.find("\n\n"), buffer.find("\r\n\r\n")) {
        (Some(lf), Some(crlf)) if lf < crlf => Some((lf, 2)),
        (Some(_), Some(crlf)) => Some((crlf, 4)),
        (Some(lf), None) => Some((lf, 2)),
        (None, Some(crlf)) => Some((crlf, 4)),
        (None, None) => None,
    }
}

fn parse_block(block: &str) -> Option<SseFrame> {
    let mut event = "message".to_string();
    let mut data: Vec<String> = Vec::new();
    for raw in block.lines() {
        let line = raw.trim_end_matches('\r');
        if line.is_empty() || line.starts_with(':') {
            continue;
        }
        if let Some(value) = line.strip_prefix("event:") {
            event = trim_value(value).to_string();
        } else if let Some(value) = line.strip_prefix("data:") {
            data.push(trim_value(value).to_string());
        }
    }
    if data.is_empty() {
        return None;
    }
    let payload = data.join("\n");
    if payload == "[DONE]" {
        return None;
    }
    Some(SseFrame {
        event,
        data: payload,
    })
}

fn trim_value(value: &str) -> &str {
    value.strip_prefix(' ').unwrap_or(value)
}

/// A stream of SSE progress events from the bigRAG API.
///
/// Implements `futures_core::Stream<Item = Result<ProgressEvent, BigRagError>>`.
/// Consume with `StreamExt::next()` from `futures-util` or `tokio-stream`.
pub struct SseStream {
    inner: Pin<Box<dyn Stream<Item = Result<bytes::Bytes, reqwest::Error>> + Send>>,
    parser: FrameParser,
    pending: VecDeque<Result<ProgressEvent, BigRagError>>,
    byte_buf: Vec<u8>,
}

impl SseStream {
    pub(crate) fn new(response: reqwest::Response) -> Self {
        Self {
            inner: Box::pin(response.bytes_stream()),
            parser: FrameParser::new(),
            pending: VecDeque::new(),
            byte_buf: Vec::new(),
        }
    }
}

impl Stream for SseStream {
    type Item = Result<ProgressEvent, BigRagError>;

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
                        serde_json::from_str(&frame.data).map_err(BigRagError::Serialization)
                    })
                    .collect();

                if let Some(first) = self.pending.pop_front() {
                    Poll::Ready(Some(first))
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
