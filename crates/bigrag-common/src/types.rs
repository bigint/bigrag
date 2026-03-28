use serde::{Deserialize, Serialize};
use std::fmt;

/// Document ID: u64, UUID, or string (max 64 bytes).
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum DocumentId {
    UInt(u64),
    Uuid(uuid::Uuid),
    String(String),
}

impl DocumentId {
    pub fn validate(&self) -> crate::error::Result<()> {
        if let Self::String(s) = self {
            if s.len() > 64 {
                return Err(crate::error::BigRagError::BadRequest(
                    "string ID exceeds 64 bytes".into(),
                ));
            }
        }
        Ok(())
    }

    pub fn as_bytes(&self) -> Vec<u8> {
        match self {
            Self::UInt(n) => n.to_be_bytes().to_vec(),
            Self::Uuid(u) => u.as_bytes().to_vec(),
            Self::String(s) => s.as_bytes().to_vec(),
        }
    }
}

impl fmt::Display for DocumentId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UInt(n) => write!(f, "{n}"),
            Self::Uuid(u) => write!(f, "{u}"),
            Self::String(s) => write!(f, "{s}"),
        }
    }
}

impl Serialize for DocumentId {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match self {
            Self::UInt(n) => serializer.serialize_u64(*n),
            Self::Uuid(u) => serializer.serialize_str(&u.to_string()),
            Self::String(s) => serializer.serialize_str(s),
        }
    }
}

impl<'de> Deserialize<'de> for DocumentId {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let value = serde_json::Value::deserialize(deserializer)?;
        match value {
            serde_json::Value::Number(n) => {
                if let Some(u) = n.as_u64() {
                    Ok(Self::UInt(u))
                } else {
                    Err(serde::de::Error::custom("ID number must be unsigned 64-bit"))
                }
            }
            serde_json::Value::String(s) => {
                if let Ok(u) = s.parse::<uuid::Uuid>() {
                    Ok(Self::Uuid(u))
                } else {
                    Ok(Self::String(s))
                }
            }
            _ => Err(serde::de::Error::custom(
                "ID must be a number, UUID string, or string",
            )),
        }
    }
}

/// Distance metric for vector search.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DistanceMetric {
    CosineDistance,
    EuclideanSquared,
    DotProduct,
    Hamming,
}

/// Attribute value stored in documents.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum AttributeValue {
    Null,
    Bool(bool),
    Int(i64),
    UInt(u64),
    Float(f64),
    String(String),
    Uuid(uuid::Uuid),
    DateTime(chrono::DateTime<chrono::Utc>),
    ArrayBool(Vec<bool>),
    ArrayInt(Vec<i64>),
    ArrayUInt(Vec<u64>),
    ArrayFloat(Vec<f64>),
    ArrayString(Vec<String>),
    ArrayUuid(Vec<uuid::Uuid>),
    ArrayDateTime(Vec<chrono::DateTime<chrono::Utc>>),
}

impl AttributeValue {
    pub fn is_null(&self) -> bool {
        matches!(self, Self::Null)
    }
}

/// A single document with its ID, optional vector, and attributes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Document {
    pub id: DocumentId,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vector: Option<Vec<f32>>,
    #[serde(flatten)]
    pub attributes: std::collections::HashMap<String, AttributeValue>,
}

/// Consistency level for queries.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsistencyLevel {
    pub level: ConsistencyMode,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConsistencyMode {
    Strong,
    Eventual,
}

impl Default for ConsistencyLevel {
    fn default() -> Self {
        Self {
            level: ConsistencyMode::Strong,
        }
    }
}

/// Billing information returned in responses.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct BillingInfo {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub billable_logical_bytes_written: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub billable_logical_bytes_queried: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub billable_logical_bytes_returned: Option<u64>,
}

/// Performance information returned in responses.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PerformanceInfo {
    pub server_total_ms: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query_execution_ms: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cache_hit_ratio: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cache_temperature: Option<CacheTemperature>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exhaustive_search_count: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub approx_namespace_size: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CacheTemperature {
    Hot,
    Warm,
    Cold,
}

/// Namespace name validation: [A-Za-z0-9-_.]{1,128}
pub fn validate_namespace(name: &str) -> crate::error::Result<()> {
    if name.is_empty() || name.len() > 128 {
        return Err(crate::error::BigRagError::BadRequest(
            "namespace name must be 1-128 characters".into(),
        ));
    }
    if !name
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.')
    {
        return Err(crate::error::BigRagError::BadRequest(
            "namespace name must match [A-Za-z0-9-_.]{1,128}".into(),
        ));
    }
    Ok(())
}

// === API Key Types ===

/// Scoped API key with permissions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKey {
    pub id: String,
    pub name: String,
    pub key_hash: String,
    pub prefix: String,
    pub permissions: ApiKeyPermissions,
    pub created_at: String,
    pub last_used_at: Option<String>,
    pub expires_at: Option<String>,
}

/// Summary of an API key (without the hash), safe to return in list responses.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeySummary {
    pub id: String,
    pub name: String,
    pub prefix: String,
    pub permissions: ApiKeyPermissions,
    pub created_at: String,
    pub last_used_at: Option<String>,
    pub expires_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeyPermissions {
    pub namespaces: Vec<String>,
    pub operations: Vec<ApiOperation>,
    pub admin: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ApiOperation {
    Read,
    Write,
    Delete,
    Schema,
    Admin,
}

impl ApiKey {
    /// Check if this key can access the given namespace with the given operation.
    pub fn can_access(&self, namespace: &str, operation: ApiOperation) -> bool {
        if self.permissions.admin {
            return true;
        }
        if !self.permissions.operations.contains(&operation) {
            return false;
        }
        self.permissions.namespaces.iter().any(|pattern| {
            if pattern == "*" {
                return true;
            }
            if let Some(prefix) = pattern.strip_suffix('*') {
                namespace.starts_with(prefix)
            } else {
                pattern == namespace
            }
        })
    }

    /// Convert to a summary (without the key hash).
    pub fn to_summary(&self) -> ApiKeySummary {
        ApiKeySummary {
            id: self.id.clone(),
            name: self.name.clone(),
            prefix: self.prefix.clone(),
            permissions: self.permissions.clone(),
            created_at: self.created_at.clone(),
            last_used_at: self.last_used_at.clone(),
            expires_at: self.expires_at.clone(),
        }
    }
}

/// Attribute name validation: max 128 chars, must not start with `$`.
pub fn validate_attribute_name(name: &str) -> crate::error::Result<()> {
    if name.is_empty() || name.len() > 128 {
        return Err(crate::error::BigRagError::BadRequest(
            "attribute name must be 1-128 characters".into(),
        ));
    }
    if name.starts_with('$') {
        return Err(crate::error::BigRagError::BadRequest(
            "attribute name must not start with '$'".into(),
        ));
    }
    Ok(())
}
