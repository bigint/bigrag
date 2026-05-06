/// Analytics response types.
pub mod analytics;
/// Chat types (generated answers and persisted conversations).
pub mod chat;
/// Collection types (create, update, list, stats).
pub mod collections;
/// Common response types (status, pagination, health).
pub mod common;
/// Document types (upload, batch, chunks).
pub mod documents;
/// Embedding model types.
pub mod embeddings;
/// Query types (single, multi, batch, search mode).
pub mod query;
/// SSE progress event types.
pub mod sse;
/// Vector types (upsert, delete).
pub mod vectors;
/// Webhook types (create, update, deliveries).
pub mod webhooks;

pub use analytics::*;
pub use chat::*;
pub use collections::*;
pub use common::*;
pub use documents::*;
pub use embeddings::*;
pub use query::*;
pub use sse::*;
pub use vectors::*;
pub use webhooks::*;
