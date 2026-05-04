use serde::Deserialize;

/// A progress event received from an SSE stream.
#[derive(Debug, Clone, Deserialize)]
pub struct ProgressEvent {
    /// Processing step name (e.g. `"chunking"`, `"embedding"`).
    pub step: String,
    /// Human-readable progress message.
    pub message: String,
    /// Progress percentage (0–100).
    pub progress: f64,
    /// Optional status string (e.g. `"processing"`, `"complete"`).
    pub status: Option<String>,
    /// Additional fields not captured by named fields.
    #[serde(flatten)]
    pub extra: serde_json::Value,
}
