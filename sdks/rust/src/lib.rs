#![warn(missing_docs)]
#![doc = include_str!("../README.md")]

mod client;
mod core;
mod files;
mod sse;

/// Error types.
pub mod error;
/// Resource namespaces for interacting with the bigRAG API.
pub mod resources;
/// Request and response types.
pub mod types;

pub use client::{BigRag, BigRagBuilder, BigRagConfig, CollectionClient};
pub use error::BigRagError;
pub use files::FileInput;
pub use resources::{Collections, Documents, Queries, Vectors, Webhooks};
pub use sse::SseStream;
