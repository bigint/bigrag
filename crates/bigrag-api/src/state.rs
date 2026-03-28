use bigrag_common::types::{AttributeValue, DistanceMetric, DocumentId};
use bigrag_index::{InvertedIndex, VectorIndex};
use bigrag_query::executor::InMemoryDoc;
use bigrag_query::filter::{evaluate_filter, parse_filter};
use bigrag_storage::engine::StorageEngine;
use dashmap::DashMap;
use metrics_exporter_prometheus::PrometheusHandle;
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
        api_keys: Vec<String>,
        prometheus_handle: PrometheusHandle,
    ) -> Self {
        Self {
            engine,
            documents: Arc::new(DashMap::new()),
            api_keys: Arc::new(api_keys),
            prometheus_handle,
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

    /// Patch documents: merge attributes into existing docs, optionally replace vector.
    /// Setting an attribute value to None removes it. Returns the count of docs actually patched.
    pub fn patch_documents(&self, namespace: &str, patches: Vec<PatchDoc>) -> usize {
        if let Some(ns) = self.documents.get(namespace) {
            let mut docs = ns.docs.write();
            let mut patched = 0usize;

            for patch in patches {
                if let Some(doc) = docs.iter_mut().find(|d| d.id == patch.id) {
                    // Replace vector only if specified
                    if let Some(new_vec) = patch.vector {
                        doc.vector = Some(new_vec);
                    }

                    // Merge attributes
                    for (key, maybe_val) in patch.attributes {
                        match maybe_val {
                            Some(val) if val.is_null() => {
                                // Setting to null removes the attribute
                                doc.attributes.remove(&key);
                            }
                            Some(val) => {
                                doc.attributes.insert(key, val);
                            }
                            None => {
                                // None also removes the attribute
                                doc.attributes.remove(&key);
                            }
                        }
                    }

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
                for (key, maybe_val) in patch_attrs {
                    match maybe_val {
                        Some(val) if val.is_null() => {
                            doc.attributes.remove(key);
                        }
                        Some(val) => {
                            doc.attributes.insert(key.clone(), val.clone());
                        }
                        None => {
                            doc.attributes.remove(key);
                        }
                    }
                }
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
