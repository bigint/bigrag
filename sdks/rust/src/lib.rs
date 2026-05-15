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
pub use resources::{
    AccessLogOptions, Admin, AdminAccess, AdminApiKeys, AdminAudit, AdminBackups, AdminConnectors,
    AdminEmbeddingPresets, AdminGoogleConnector, AdminMcpServers, AdminRealtime,
    AdminRealtimeConnectorSyncJobsOptions, AdminRealtimeDocumentsOptions, AdminRealtimeStream,
    AdminSettings, AdminUsers, AuditLogOptions, Auth, ChatStream, Chats, Collections, Connectors,
    Documents, Evaluations, GoogleDrive, Queries, Vectors, Webhooks,
};
pub use sse::SseStream;
