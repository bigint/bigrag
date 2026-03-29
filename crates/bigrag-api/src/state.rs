use bigrag_common::types::{
    ApiKey, ApiKeyPermissions, ApiKeySummary, ApiOperation, AttributeValue, DistanceMetric,
    DocumentId,
};
use bigrag_index::{InvertedIndex, VectorIndex};
use bigrag_query::executor::InMemoryDoc;
use bigrag_query::filter::{evaluate_filter, parse_filter};
use bigrag_storage::engine::StorageEngine;
use dashmap::DashMap;
use jsonwebtoken::{DecodingKey, Validation};
use metrics_exporter_prometheus::PrometheusHandle;
use parking_lot::RwLock;
use rand::Rng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::Arc;

/// A patch operation: update only specified attributes on an existing document.
pub struct PatchDoc {
    pub id: DocumentId,
    pub vector: Option<Vec<f32>>,
    /// `None` value means remove that attribute; `Some(val)` means set it.
    pub attributes: HashMap<String, Option<AttributeValue>>,
}

// === API Key Store ===

/// Hash a plaintext key with SHA-256 (hex-encoded).
fn hash_key(plaintext: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(plaintext.as_bytes());
    format!("{:x}", hasher.finalize())
}

/// Generate a random API key with "br_" prefix (40 hex chars after prefix).
fn generate_api_key() -> String {
    let random_bytes: [u8; 20] = rand::rng().random();
    let hex: String = random_bytes.iter().map(|b| format!("{b:02x}")).collect();
    format!("br_{hex}")
}

/// In-memory store for API keys with validation and management.
pub struct ApiKeyStore {
    keys: RwLock<Vec<ApiKey>>,
    master_key: Option<String>,
}

impl ApiKeyStore {
    pub fn new(master_key: Option<String>, initial_keys: Vec<String>) -> Self {
        let keys: Vec<ApiKey> = initial_keys
            .into_iter()
            .enumerate()
            .map(|(i, plaintext)| {
                let prefix = if plaintext.len() >= 8 {
                    plaintext[..8].to_string()
                } else {
                    plaintext.clone()
                };
                ApiKey {
                    id: format!("legacy-{i}"),
                    name: format!("legacy-key-{i}"),
                    key_hash: hash_key(&plaintext),
                    prefix,
                    permissions: ApiKeyPermissions {
                        namespaces: vec!["*".to_string()],
                        operations: vec![
                            ApiOperation::Read,
                            ApiOperation::Write,
                            ApiOperation::Delete,
                            ApiOperation::Schema,
                            ApiOperation::Admin,
                        ],
                        admin: true,
                    },
                    created_at: chrono::Utc::now().to_rfc3339(),
                    last_used_at: None,
                    expires_at: None,
                }
            })
            .collect();
        Self {
            keys: RwLock::new(keys),
            master_key,
        }
    }

    /// Returns true when no keys are configured and no master key is set (open access).
    pub fn is_open(&self) -> bool {
        self.master_key.is_none() && self.keys.read().is_empty()
    }

    /// Validate a token against the master key and stored keys.
    /// Returns the matching `ApiKey` if found, updating `last_used_at`.
    pub fn validate(&self, token: &str) -> Option<ApiKey> {
        // Check master key first
        if let Some(ref mk) = self.master_key {
            if token == mk {
                return Some(ApiKey {
                    id: "master".to_string(),
                    name: "master-key".to_string(),
                    key_hash: String::new(),
                    prefix: "master".to_string(),
                    permissions: ApiKeyPermissions {
                        namespaces: vec!["*".to_string()],
                        operations: vec![
                            ApiOperation::Read,
                            ApiOperation::Write,
                            ApiOperation::Delete,
                            ApiOperation::Schema,
                            ApiOperation::Admin,
                        ],
                        admin: true,
                    },
                    created_at: String::new(),
                    last_used_at: None,
                    expires_at: None,
                });
            }
        }

        let token_hash = hash_key(token);
        let mut keys = self.keys.write();
        let now = chrono::Utc::now().to_rfc3339();
        for key in keys.iter_mut() {
            if key.key_hash == token_hash {
                // Check expiry
                if let Some(ref expires) = key.expires_at {
                    if let Ok(exp) = chrono::DateTime::parse_from_rfc3339(expires) {
                        if chrono::Utc::now() > exp {
                            return None;
                        }
                    }
                }
                key.last_used_at = Some(now);
                return Some(key.clone());
            }
        }
        None
    }

    /// Create a new API key. Returns (plaintext_key, api_key_record).
    pub fn create_key(
        &self,
        name: String,
        permissions: ApiKeyPermissions,
        expires_at: Option<String>,
    ) -> (String, ApiKey) {
        let plaintext = generate_api_key();
        let prefix = plaintext[..11].to_string(); // "br_" + first 8 hex chars
        let id = uuid::Uuid::new_v4().to_string();
        let api_key = ApiKey {
            id,
            name,
            key_hash: hash_key(&plaintext),
            prefix,
            permissions,
            created_at: chrono::Utc::now().to_rfc3339(),
            last_used_at: None,
            expires_at,
        };
        self.keys.write().push(api_key.clone());
        (plaintext, api_key)
    }

    /// List all keys as summaries (without hashes).
    pub fn list_keys(&self) -> Vec<ApiKeySummary> {
        self.keys.read().iter().map(|k| k.to_summary()).collect()
    }

    /// Revoke (delete) a key by ID. Returns true if found and removed.
    pub fn revoke_key(&self, id: &str) -> bool {
        let mut keys = self.keys.write();
        let before = keys.len();
        keys.retain(|k| k.id != id);
        keys.len() < before
    }
}

// === JWT Configuration ===

/// JWT configuration for HS256 shared-secret validation.
#[derive(Clone)]
pub struct JwtConfig {
    pub secret: String,
    pub issuer: Option<String>,
}

/// JWT claims structure.
#[derive(Debug, Serialize, Deserialize)]
pub struct JwtClaims {
    pub sub: Option<String>,
    pub exp: Option<u64>,
    pub iat: Option<u64>,
    pub iss: Option<String>,
    #[serde(default)]
    pub namespaces: Vec<String>,
    #[serde(default)]
    pub operations: Vec<ApiOperation>,
    #[serde(default)]
    pub admin: bool,
}

impl JwtConfig {
    pub fn validate_jwt(&self, token: &str) -> Result<ApiKey, String> {
        let mut validation = Validation::new(jsonwebtoken::Algorithm::HS256);
        if let Some(ref iss) = self.issuer {
            validation.set_issuer(&[iss]);
        }
        // Required claims: exp
        validation.set_required_spec_claims(&["exp"]);

        let key = DecodingKey::from_secret(self.secret.as_bytes());
        let token_data = jsonwebtoken::decode::<JwtClaims>(token, &key, &validation)
            .map_err(|e| format!("JWT validation failed: {e}"))?;

        let claims = token_data.claims;
        let namespaces = if claims.namespaces.is_empty() {
            vec!["*".to_string()]
        } else {
            claims.namespaces
        };
        let operations = if claims.operations.is_empty() {
            vec![
                ApiOperation::Read,
                ApiOperation::Write,
                ApiOperation::Delete,
                ApiOperation::Schema,
            ]
        } else {
            claims.operations
        };

        Ok(ApiKey {
            id: format!("jwt-{}", claims.sub.as_deref().unwrap_or("anonymous")),
            name: format!("jwt-{}", claims.sub.as_deref().unwrap_or("anonymous")),
            key_hash: String::new(),
            prefix: "jwt".to_string(),
            permissions: ApiKeyPermissions {
                namespaces,
                operations,
                admin: claims.admin,
            },
            created_at: String::new(),
            last_used_at: None,
            expires_at: None,
        })
    }
}

/// Apply a set of attribute patches to a document's attributes map.
/// `None` or `Null` values remove the attribute; `Some(val)` sets it.
fn apply_attribute_patch(
    attributes: &mut HashMap<String, AttributeValue>,
    patches: &HashMap<String, Option<AttributeValue>>,
) {
    for (key, maybe_val) in patches {
        match maybe_val {
            Some(val) if val.is_null() => {
                attributes.remove(key);
            }
            Some(val) => {
                attributes.insert(key.clone(), val.clone());
            }
            None => {
                attributes.remove(key);
            }
        }
    }
}

/// Application state shared across all handlers.
#[derive(Clone)]
pub struct AppState {
    pub engine: Arc<StorageEngine>,
    /// In-memory document store per namespace (for queries).
    pub documents: Arc<DashMap<String, NamespaceData>>,
    /// API key store for authentication and management.
    pub key_store: Arc<ApiKeyStore>,
    /// Optional JWT configuration for token-based auth.
    pub jwt_config: Option<Arc<JwtConfig>>,
    /// Handle to render Prometheus metrics output.
    pub prometheus_handle: PrometheusHandle,
}

/// Per-namespace in-memory data for serving queries.
pub struct NamespaceData {
    pub docs: RwLock<Vec<InMemoryDoc>>,
    pub vector_index: Option<VectorIndex>,
    pub inverted_indexes: HashMap<String, RwLock<InvertedIndex>>,
    pub distance_metric: Option<DistanceMetric>,
    pub schema: Option<serde_json::Value>,
}

impl AppState {
    pub fn new(
        engine: Arc<StorageEngine>,
        key_store: ApiKeyStore,
        jwt_config: Option<JwtConfig>,
        prometheus_handle: PrometheusHandle,
    ) -> Self {
        Self {
            engine,
            documents: Arc::new(DashMap::new()),
            key_store: Arc::new(key_store),
            jwt_config: jwt_config.map(Arc::new),
            prometheus_handle,
        }
    }

    /// Validate a bearer token. Tries JWT first (if token starts with "ey" and
    /// JWT is configured), then falls back to API key store.
    pub fn validate_auth(&self, token: &str) -> Option<ApiKey> {
        // JWT tokens start with "ey" (base64-encoded JSON header)
        if token.starts_with("ey") {
            if let Some(ref jwt_config) = self.jwt_config {
                if let Ok(api_key) = jwt_config.validate_jwt(token) {
                    return Some(api_key);
                }
            }
        }
        self.key_store.validate(token)
    }

    /// Get or create namespace data.
    pub fn get_or_create_namespace(
        &self,
        namespace: &str,
        distance_metric: Option<DistanceMetric>,
    ) -> dashmap::mapref::one::RefMut<'_, String, NamespaceData> {
        if !self.documents.contains_key(namespace) {
            let vector_index = distance_metric.map(|m| VectorIndex::new(0, m));
            self.documents.insert(
                namespace.to_string(),
                NamespaceData {
                    docs: RwLock::new(Vec::new()),
                    vector_index,
                    inverted_indexes: HashMap::new(),
                    distance_metric,
                    schema: None,
                },
            );
        }
        self.documents.get_mut(namespace).unwrap()
    }

    /// Insert or update documents in a namespace.
    pub fn upsert_documents(
        &self,
        namespace: &str,
        new_docs: Vec<InMemoryDoc>,
        distance_metric: Option<DistanceMetric>,
    ) -> usize {
        let ns = self.get_or_create_namespace(namespace, distance_metric);
        let mut docs = ns.docs.write();
        let count = new_docs.len();

        for new_doc in new_docs {
            // Remove existing doc with same ID
            docs.retain(|d| d.id != new_doc.id);

            // Add to vector index if has vector
            if let (Some(vi), Some(vec)) = (&ns.vector_index, &new_doc.vector) {
                if let DocumentId::UInt(uid) = &new_doc.id {
                    vi.insert(*uid, vec.clone());
                }
            }

            docs.push(new_doc);
        }

        count
    }

    /// Delete documents by IDs from a namespace.
    pub fn delete_documents(&self, namespace: &str, ids: &[DocumentId]) -> usize {
        if let Some(ns) = self.documents.get(namespace) {
            let mut docs = ns.docs.write();
            let before = docs.len();
            docs.retain(|d| !ids.contains(&d.id));
            before - docs.len()
        } else {
            0
        }
    }

    /// Get all documents for a namespace (for query execution).
    pub fn get_namespace_docs(&self, namespace: &str) -> Vec<InMemoryDoc> {
        if let Some(ns) = self.documents.get(namespace) {
            ns.docs.read().clone()
        } else {
            vec![]
        }
    }

    /// List namespace names.
    pub fn list_namespaces(
        &self,
        prefix: Option<&str>,
        cursor: Option<&str>,
        page_size: usize,
    ) -> (Vec<String>, Option<String>) {
        let mut names: Vec<String> = self
            .documents
            .iter()
            .map(|entry| entry.key().clone())
            .collect();
        names.sort();

        // Filter by prefix
        if let Some(p) = prefix {
            names.retain(|n: &String| n.starts_with(p));
        }

        // Apply cursor
        let start_idx = if let Some(c) = cursor {
            names.iter().position(|n: &String| n.as_str() > c).unwrap_or(names.len())
        } else {
            0
        };

        let page: Vec<String> = names[start_idx..].iter().take(page_size).cloned().collect();
        let next_cursor = if start_idx + page_size < names.len() {
            page.last().cloned()
        } else {
            None
        };

        (page, next_cursor)
    }

    /// Patch documents: merge attributes into existing docs, optionally replace vector.
    /// Setting an attribute value to None removes it. Returns the count of docs actually patched.
    pub fn patch_documents(&self, namespace: &str, patches: Vec<PatchDoc>) -> usize {
        if let Some(ns) = self.documents.get(namespace) {
            let mut docs = ns.docs.write();
            let mut patched = 0usize;

            for patch in patches {
                if let Some(doc) = docs.iter_mut().find(|d| d.id == patch.id) {
                    if let Some(new_vec) = patch.vector {
                        doc.vector = Some(new_vec);
                    }
                    apply_attribute_patch(&mut doc.attributes, &patch.attributes);
                    patched += 1;
                }
            }

            patched
        } else {
            0
        }
    }

    /// Delete documents matching a filter. Returns (count_deleted, has_remaining).
    pub fn delete_by_filter(
        &self,
        namespace: &str,
        filter_json: &serde_json::Value,
        max_affected: usize,
        allow_partial: bool,
    ) -> Result<(usize, bool), String> {
        let filter = parse_filter(filter_json).map_err(|e| e.to_string())?;

        if let Some(ns) = self.documents.get(namespace) {
            let mut docs = ns.docs.write();

            // First, find all matching indices
            let matching_indices: Vec<usize> = docs
                .iter()
                .enumerate()
                .filter(|(_, d)| evaluate_filter(&filter, &d.attributes))
                .map(|(i, _)| i)
                .collect();

            let total_matching = matching_indices.len();

            if total_matching > max_affected && !allow_partial {
                return Err(format!(
                    "filter matches {} rows which exceeds max_affected ({}). Set allow_partial=true to delete up to max_affected.",
                    total_matching, max_affected
                ));
            }

            let to_delete: Vec<usize> = matching_indices
                .into_iter()
                .take(max_affected)
                .collect();

            let count = to_delete.len();
            let has_remaining = total_matching > max_affected;

            // Remove in reverse order to preserve indices
            for idx in to_delete.into_iter().rev() {
                docs.swap_remove(idx);
            }

            Ok((count, has_remaining))
        } else {
            Ok((0, false))
        }
    }

    /// Patch documents matching a filter with the given attributes.
    /// Returns (count_patched, has_remaining).
    pub fn patch_by_filter(
        &self,
        namespace: &str,
        filter_json: &serde_json::Value,
        patch_attrs: &HashMap<String, Option<AttributeValue>>,
        max_affected: usize,
        allow_partial: bool,
    ) -> Result<(usize, bool), String> {
        let filter = parse_filter(filter_json).map_err(|e| e.to_string())?;

        if let Some(ns) = self.documents.get(namespace) {
            let mut docs = ns.docs.write();

            // Find all matching indices
            let matching_indices: Vec<usize> = docs
                .iter()
                .enumerate()
                .filter(|(_, d)| evaluate_filter(&filter, &d.attributes))
                .map(|(i, _)| i)
                .collect();

            let total_matching = matching_indices.len();

            if total_matching > max_affected && !allow_partial {
                return Err(format!(
                    "filter matches {} rows which exceeds max_affected ({}). Set allow_partial=true to patch up to max_affected.",
                    total_matching, max_affected
                ));
            }

            let to_patch: Vec<usize> = matching_indices
                .into_iter()
                .take(max_affected)
                .collect();

            let count = to_patch.len();
            let has_remaining = total_matching > max_affected;

            for idx in &to_patch {
                let doc = &mut docs[*idx];
                apply_attribute_patch(&mut doc.attributes, patch_attrs);
            }

            Ok((count, has_remaining))
        } else {
            Ok((0, false))
        }
    }

    /// Evaluate a condition against an existing document for conditional writes.
    /// Returns true if the condition is met (document should be written).
    pub fn evaluate_condition(
        &self,
        namespace: &str,
        doc_id: &DocumentId,
        condition_json: &serde_json::Value,
    ) -> Result<bool, String> {
        let filter = parse_filter(condition_json).map_err(|e| e.to_string())?;

        if let Some(ns) = self.documents.get(namespace) {
            let docs = ns.docs.read();
            if let Some(existing) = docs.iter().find(|d| d.id == *doc_id) {
                Ok(evaluate_filter(&filter, &existing.attributes))
            } else {
                // No existing doc — condition evaluates against empty attributes
                Ok(evaluate_filter(&filter, &HashMap::new()))
            }
        } else {
            // Namespace doesn't exist yet — evaluate against empty
            Ok(evaluate_filter(&filter, &HashMap::new()))
        }
    }

    /// Delete a namespace and all its data.
    pub fn delete_namespace(&self, namespace: &str) -> bool {
        self.documents.remove(namespace).is_some()
    }
}
