use serde::{Deserialize, Serialize};

/// A vector entry for direct upsert.
#[derive(Debug, Clone, Serialize)]
pub struct VectorEntry {
    /// Unique vector ID.
    pub id: String,
    /// Embedding values.
    pub embedding: Vec<f64>,
    /// Source text.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
    /// Vector metadata.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
}

/// Response from vector upsert.
#[derive(Debug, Clone, Deserialize)]
pub struct UpsertResponse {
    /// Status string.
    pub status: String,
    /// Number of vectors upserted.
    pub upserted: u32,
}

/// Response from vector deletion.
#[derive(Debug, Clone, Deserialize)]
pub struct DeleteResponse {
    /// Status string.
    pub status: String,
    /// Number of vectors deleted.
    pub deleted: u32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_serialize_vector_entry_skips_none() {
        let entry = VectorEntry {
            id: "v1".into(),
            embedding: vec![0.1, 0.2, 0.3],
            text: None,
            metadata: None,
        };
        let json = serde_json::to_value(&entry).unwrap();
        assert_eq!(json["id"], "v1");
        assert!(json.get("text").is_none());
    }

    #[test]
    fn test_deserialize_upsert_response() {
        let json = r#"{"status":"ok","upserted":5}"#;
        let resp: UpsertResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.upserted, 5);
    }

    #[test]
    fn test_deserialize_delete_response() {
        let json = r#"{"status":"ok","deleted":3}"#;
        let resp: DeleteResponse = serde_json::from_str(json).unwrap();
        assert_eq!(resp.deleted, 3);
    }
}
