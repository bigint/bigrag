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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_progress_event() {
        let json = r#"{"step":"chunking","message":"Splitting into chunks","progress":45.0,"status":"processing"}"#;
        let event: ProgressEvent = serde_json::from_str(json).unwrap();
        assert_eq!(event.step, "chunking");
        assert_eq!(event.progress, 45.0);
        assert_eq!(event.status.as_deref(), Some("processing"));
    }

    #[test]
    fn test_deserialize_progress_event_with_extras() {
        let json = r#"{"step":"batch_progress","message":"Processing","progress":50.0,"document_id":"abc-123","total":10,"completed":5}"#;
        let event: ProgressEvent = serde_json::from_str(json).unwrap();
        assert_eq!(event.step, "batch_progress");
        assert_eq!(event.extra["document_id"], "abc-123");
        assert_eq!(event.extra["total"], 10);
    }
}
