#![warn(missing_docs)]
#![doc = include_str!("../README.md")]

mod client;
mod core;
mod files;
mod sse;

/// Error types.
pub mod error;
/// Resource namespaces for interacting with the rag.computer API.
pub mod resources;
/// Request and response types.
pub mod types;

pub use client::{CollectionClient, RagComputer, RagComputerBuilder, RagComputerConfig};
pub use error::RagComputerError;
pub use files::FileInput;
pub use resources::{
    AccessLogOptions, Admin, AdminAccess, AdminApiKeys, AdminAudit, AdminConnectors,
    AdminEmbeddingPresets, AdminGoogleConnector, AdminMcpServers, AdminUsers, AuditLogOptions,
    Auth, Chats, Collections, Connectors, Documents, Evaluations, GoogleDrive, Queries, Vectors,
    Webhooks,
};
pub use sse::SseStream;
