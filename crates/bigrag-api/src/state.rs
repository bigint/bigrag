use bigrag_common::types::{AttributeValue, DocumentId, DistanceMetric};
use bigrag_index::{InvertedIndex, VectorIndex};
use bigrag_query::executor::InMemoryDoc;
use bigrag_query::filter::{evaluate_filter, parse_filter};
use bigrag_storage::engine::StorageEngine;
use dashmap::DashMap;
use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;

/// A patch operation: update only specified attributes on an existing document.
pub struct PatchDoc {
    pub id: DocumentId,
    pub vector: Option<Vec<f32>>,
    /// `None` value means remove that attribute; `Some(val)` means set it.
    pub attributes: HashMap<String, Option<AttributeValue>>,
}

/// Application state shared across all handlers.
#[derive(Clone)]
pub struct AppState {
    pub engine: Arc<StorageEngine>,
    /// In-memory document store per namespace (for queries).
    pub documents: Arc<DashMap<String, NamespaceData>>,
    /// API keys for authentication.
    pub api_keys: Arc<Vec<String>>,
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
    pub fn new(engine: Arc<StorageEngine>, api_keys: Vec<String>) -> Self {
        Self {
            engine,
            documents: Arc::new(DashMap::new()),
            api_keys: Arc::new(api_keys),
        }
    }

    pub fn validate_auth(&self, token: &str) -> bool {
        self.api_keys.is_empty() || self.api_keys.contains(&token.to_string())
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

    /// Delete a namespace and all its data.
    pub fn delete_namespace(&self, namespace: &str) -> bool {
        self.documents.remove(namespace).is_some()
    }
}
