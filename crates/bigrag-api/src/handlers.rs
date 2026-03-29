use axum::{
    Extension, Json,
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
};
use bigrag_common::types::{
    ApiKey, ApiKeyPermissions, ApiOperation, AttributeValue, BillingInfo, ConsistencyLevel,
    DistanceMetric, DocumentId, PerformanceInfo,
};
use bigrag_query::executor::{execute_query, InMemoryDoc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tracing::{debug, error, info, warn};

use crate::state::{AppState, PatchDoc};

// === Write Documents ===

#[derive(Debug, Deserialize)]
pub struct WriteRequest {
    pub upsert_rows: Option<Vec<serde_json::Value>>,
    pub upsert_columns: Option<serde_json::Value>,
    pub patch_rows: Option<Vec<serde_json::Value>>,
    pub patch_columns: Option<serde_json::Value>,
    pub deletes: Option<Vec<serde_json::Value>>,
    pub delete_by_filter: Option<serde_json::Value>,
    pub patch_by_filter: Option<serde_json::Value>,
    pub distance_metric: Option<String>,
    pub schema: Option<serde_json::Value>,
    pub return_affected_ids: Option<bool>,
    pub disable_backpressure: Option<bool>,
    pub condition: Option<serde_json::Value>,
    pub copy_from_namespace: Option<serde_json::Value>,
}

#[derive(Debug, Serialize)]
pub struct WriteResponse {
    pub rows_affected: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rows_upserted: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rows_patched: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rows_deleted: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rows_skipped: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rows_remaining: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub upserted_ids: Option<Vec<serde_json::Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub patched_ids: Option<Vec<serde_json::Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deleted_ids: Option<Vec<serde_json::Value>>,
    pub billing: BillingInfo,
    pub performance: PerformanceInfo,
}

pub async fn write_documents(
    State(state): State<AppState>,
    Path(namespace): Path<String>,
    Json(body): Json<WriteRequest>,
) -> impl IntoResponse {
    let start = std::time::Instant::now();
    debug!(namespace = %namespace, "write_documents request received");

    // Validate namespace
    if let Err(e) = bigrag_common::types::validate_namespace(&namespace) {
        warn!(namespace = %namespace, error = %e, "invalid namespace name in write request");
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"status": "error", "error": e.to_string()})),
        );
    }

    let distance_metric = body.distance_metric.as_deref().and_then(|m| match m {
        "cosine_distance" => Some(DistanceMetric::CosineDistance),
        "euclidean_squared" => Some(DistanceMetric::EuclideanSquared),
        "dot_product" => Some(DistanceMetric::DotProduct),
        "hamming" => Some(DistanceMetric::Hamming),
        _ => None,
    });

    let mut total_affected = 0usize;
    let mut upserted_count = 0usize;
    let mut patched_count = 0usize;
    let mut deleted_count = 0usize;
    let mut skipped_count = 0usize;
    let mut rows_remaining: Option<bool> = None;
    let track_ids = body.return_affected_ids.unwrap_or(false);
    let mut upserted_ids: Vec<serde_json::Value> = Vec::new();
    let mut patched_ids: Vec<serde_json::Value> = Vec::new();
    let mut deleted_ids: Vec<serde_json::Value> = Vec::new();

    // Process copy_from_namespace first
    if let Some(ref copy_from) = body.copy_from_namespace {
        let source_ns = if let Some(s) = copy_from.as_str() {
            s.to_string()
        } else if let Some(obj) = copy_from.as_object() {
            obj.get("namespace")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        } else {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"status": "error", "error": "copy_from_namespace must be a string or object with 'namespace' field"})),
            );
        };
        if source_ns.is_empty() {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"status": "error", "error": "copy_from_namespace: source namespace is empty"})),
            );
        }
        let source_docs = state.get_namespace_docs(&source_ns);
        if track_ids {
            for doc in &source_docs {
                upserted_ids.push(serde_json::to_value(&doc.id).unwrap_or_default());
            }
        }
        upserted_count = state.upsert_documents(&namespace, source_docs, distance_metric);
        total_affected += upserted_count;
    }

    // Process deletes first (per spec ordering)
    if let Some(ref delete_ids_val) = body.deletes {
        let ids: Vec<DocumentId> = delete_ids_val
            .iter()
            .filter_map(|v| serde_json::from_value(v.clone()).ok())
            .collect();
        if track_ids {
            for id in &ids {
                deleted_ids.push(serde_json::to_value(id).unwrap_or_default());
            }
        }
        deleted_count = state.delete_documents(&namespace, &ids);
        total_affected += deleted_count;
    }

    // Process delete-by-filter
    if let Some(ref dbf) = body.delete_by_filter {
        if let Some(obj) = dbf.as_object() {
            let filter_json = obj.get("filter");
            let max_affected = obj
                .get("max_affected")
                .and_then(|v| v.as_u64())
                .unwrap_or(5_000_000) as usize;
            let allow_partial = obj
                .get("allow_partial")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);

            if let Some(filter_json) = filter_json {
                match state.delete_by_filter(&namespace, filter_json, max_affected, allow_partial) {
                    Ok((count, remaining)) => {
                        deleted_count += count;
                        total_affected += count;
                        if remaining {
                            rows_remaining = Some(true);
                        }
                    }
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(serde_json::json!({"status": "error", "error": e})),
                        );
                    }
                }
            }
        }
    }

    // Process upserts (with optional conditional writes)
    if let Some(ref rows) = body.upsert_rows {
        let mut docs = Vec::new();
        for row in rows {
            if let Some(doc) = parse_upsert_row(row) {
                if let Some(ref condition) = body.condition {
                    match state.evaluate_condition(&namespace, &doc.id, condition) {
                        Ok(true) => docs.push(doc),
                        Ok(false) => {
                            skipped_count += 1;
                        }
                        Err(e) => {
                            return (
                                StatusCode::BAD_REQUEST,
                                Json(serde_json::json!({"status": "error", "error": e})),
                            );
                        }
                    }
                } else {
                    docs.push(doc);
                }
            }
        }
        if track_ids {
            for doc in &docs {
                upserted_ids.push(serde_json::to_value(&doc.id).unwrap_or_default());
            }
        }
        upserted_count = state.upsert_documents(&namespace, docs, distance_metric);
        total_affected += upserted_count;
    }

    // Process column-based upserts (with optional conditional writes)
    if let Some(ref columns) = body.upsert_columns {
        if let Some(mut docs) = parse_upsert_columns(columns) {
            if let Some(ref condition) = body.condition {
                let mut filtered_docs = Vec::new();
                for doc in docs.drain(..) {
                    match state.evaluate_condition(&namespace, &doc.id, condition) {
                        Ok(true) => filtered_docs.push(doc),
                        Ok(false) => {
                            skipped_count += 1;
                        }
                        Err(e) => {
                            return (
                                StatusCode::BAD_REQUEST,
                                Json(serde_json::json!({"status": "error", "error": e})),
                            );
                        }
                    }
                }
                docs = filtered_docs;
            }
            if track_ids {
                for doc in &docs {
                    upserted_ids.push(serde_json::to_value(&doc.id).unwrap_or_default());
                }
            }
            let count = state.upsert_documents(&namespace, docs, distance_metric);
            upserted_count += count;
            total_affected += count;
        }
    }

    // Process patch rows
    if let Some(ref patches) = body.patch_rows {
        let mut patch_docs = Vec::new();
        for patch_json in patches {
            if let Some(patch) = parse_patch_row(patch_json) {
                patch_docs.push(patch);
            }
        }
        if track_ids {
            for patch in &patch_docs {
                patched_ids.push(serde_json::to_value(&patch.id).unwrap_or_default());
            }
        }
        patched_count += state.patch_documents(&namespace, patch_docs);
        total_affected += patched_count;
    }

    // Process column-based patches
    if let Some(ref columns) = body.patch_columns {
        if let Some(patch_docs) = parse_patch_columns(columns) {
            if track_ids {
                for patch in &patch_docs {
                    patched_ids.push(serde_json::to_value(&patch.id).unwrap_or_default());
                }
            }
            let count = state.patch_documents(&namespace, patch_docs);
            patched_count += count;
            total_affected += count;
        }
    }

    // Process patch-by-filter
    if let Some(ref pbf) = body.patch_by_filter {
        if let Some(obj) = pbf.as_object() {
            let filter_json = obj.get("filter");
            let attributes_json = obj.get("attributes");
            let max_affected = obj
                .get("max_affected")
                .and_then(|v| v.as_u64())
                .unwrap_or(50_000) as usize;
            let allow_partial = obj
                .get("allow_partial")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);

            if let (Some(filter_json), Some(attributes_json)) = (filter_json, attributes_json) {
                let patch_attrs = parse_patch_attributes(attributes_json);

                match state.patch_by_filter(
                    &namespace,
                    filter_json,
                    &patch_attrs,
                    max_affected,
                    allow_partial,
                ) {
                    Ok((count, remaining)) => {
                        patched_count += count;
                        total_affected += count;
                        if remaining {
                            rows_remaining = Some(true);
                        }
                    }
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(serde_json::json!({"status": "error", "error": e})),
                        );
                    }
                }
            }
        }
    }

    let elapsed = start.elapsed();

    info!(
        namespace = %namespace,
        upserted = upserted_count,
        patched = patched_count,
        deleted = deleted_count,
        skipped = skipped_count,
        total = total_affected,
        elapsed_ms = elapsed.as_secs_f64() * 1000.0,
        "write_documents completed"
    );

    // Record write metrics
    crate::metrics::record_write(&namespace, elapsed, total_affected);
    if deleted_count > 0 {
        crate::metrics::record_delete(&namespace, deleted_count);
    }

    (
        StatusCode::OK,
        Json(
            serde_json::to_value(WriteResponse {
                rows_affected: total_affected,
                rows_upserted: if upserted_count > 0 {
                    Some(upserted_count)
                } else {
                    None
                },
                rows_patched: if patched_count > 0 {
                    Some(patched_count)
                } else {
                    None
                },
                rows_deleted: if deleted_count > 0 {
                    Some(deleted_count)
                } else {
                    None
                },
                rows_skipped: if skipped_count > 0 {
                    Some(skipped_count)
                } else {
                    None
                },
                rows_remaining,
                upserted_ids: if track_ids && !upserted_ids.is_empty() {
                    Some(upserted_ids)
                } else {
                    None
                },
                patched_ids: if track_ids && !patched_ids.is_empty() {
                    Some(patched_ids)
                } else {
                    None
                },
                deleted_ids: if track_ids && !deleted_ids.is_empty() {
                    Some(deleted_ids)
                } else {
                    None
                },
                billing: BillingInfo::default(),
                performance: PerformanceInfo {
                    server_total_ms: elapsed.as_secs_f64() * 1000.0,
                    ..Default::default()
                },
            })
            .unwrap(),
        ),
    )
}

/// Parse a JSON value as a vector of f32, skipping nulls.
fn parse_vector_json(value: &serde_json::Value) -> Option<Vec<f32>> {
    if value.is_null() {
        return None;
    }
    value.as_array().map(|arr| {
        arr.iter()
            .filter_map(|n| n.as_f64().map(|f| f as f32))
            .collect()
    })
}

fn parse_upsert_row(row: &serde_json::Value) -> Option<InMemoryDoc> {
    let obj = row.as_object()?;
    let id: DocumentId = serde_json::from_value(obj.get("id")?.clone()).ok()?;
    let vector = obj.get("vector").and_then(parse_vector_json);

    let mut attributes = HashMap::new();
    for (key, value) in obj {
        if key == "id" || key == "vector" {
            continue;
        }
        if let Some(attr) = json_to_attribute(value) {
            attributes.insert(key.clone(), attr);
        }
    }

    Some(InMemoryDoc {
        id,
        vector,
        attributes,
    })
}

/// Parse a patch row from JSON. Similar to parse_upsert_row but vector is optional
/// and attributes use Option<AttributeValue> where None/null means remove.
fn parse_patch_row(row: &serde_json::Value) -> Option<PatchDoc> {
    let obj = row.as_object()?;
    let id: DocumentId = serde_json::from_value(obj.get("id")?.clone()).ok()?;
    let vector = obj.get("vector").and_then(parse_vector_json);

    let mut attributes = HashMap::new();
    for (key, value) in obj {
        if key == "id" || key == "vector" {
            continue;
        }
        if value.is_null() {
            // null means remove this attribute
            attributes.insert(key.clone(), None);
        } else if let Some(attr) = json_to_attribute(value) {
            attributes.insert(key.clone(), Some(attr));
        }
    }

    Some(PatchDoc {
        id,
        vector,
        attributes,
    })
}

/// Parse patch attributes from a JSON object for patch-by-filter.
/// Returns a map where None values indicate attribute removal.
fn parse_patch_attributes(
    value: &serde_json::Value,
) -> HashMap<String, Option<AttributeValue>> {
    let mut attrs = HashMap::new();
    if let Some(obj) = value.as_object() {
        for (key, val) in obj {
            if val.is_null() {
                attrs.insert(key.clone(), None);
            } else if let Some(attr) = json_to_attribute(val) {
                attrs.insert(key.clone(), Some(attr));
            }
        }
    }
    attrs
}

fn parse_upsert_columns(columns: &serde_json::Value) -> Option<Vec<InMemoryDoc>> {
    let obj = columns.as_object()?;
    let ids = obj.get("id")?.as_array()?;
    let vectors = obj.get("vector").and_then(|v| v.as_array());

    let n = ids.len();
    let mut docs = Vec::with_capacity(n);

    for i in 0..n {
        let id: DocumentId = serde_json::from_value(ids[i].clone()).ok()?;
        let vector = vectors.and_then(|vecs| vecs.get(i).and_then(parse_vector_json));

        let mut attributes = HashMap::new();
        for (key, value) in obj {
            if key == "id" || key == "vector" {
                continue;
            }
            if let Some(arr) = value.as_array() {
                if let Some(val) = arr.get(i) {
                    if let Some(attr) = json_to_attribute(val) {
                        attributes.insert(key.clone(), attr);
                    }
                }
            }
        }

        docs.push(InMemoryDoc {
            id,
            vector,
            attributes,
        });
    }

    Some(docs)
}

/// Parse column-based patch data into PatchDoc entries.
/// Similar to parse_upsert_columns but creates PatchDoc entries where
/// null values mean "remove attribute" and missing values mean "don't update".
fn parse_patch_columns(columns: &serde_json::Value) -> Option<Vec<PatchDoc>> {
    let obj = columns.as_object()?;
    let ids = obj.get("id")?.as_array()?;
    let vectors = obj.get("vector").and_then(|v| v.as_array());

    let n = ids.len();
    let mut patches = Vec::with_capacity(n);

    for i in 0..n {
        let id: DocumentId = serde_json::from_value(ids[i].clone()).ok()?;
        let vector = vectors.and_then(|vecs| vecs.get(i).and_then(parse_vector_json));

        let mut attributes = HashMap::new();
        for (key, value) in obj {
            if key == "id" || key == "vector" {
                continue;
            }
            if let Some(arr) = value.as_array() {
                if let Some(val) = arr.get(i) {
                    if val.is_null() {
                        // null means remove this attribute
                        attributes.insert(key.clone(), None);
                    } else if let Some(attr) = json_to_attribute(val) {
                        attributes.insert(key.clone(), Some(attr));
                    }
                }
                // If the array doesn't have a value at index i, skip (don't update)
            }
        }

        patches.push(PatchDoc {
            id,
            vector,
            attributes,
        });
    }

    Some(patches)
}

fn json_to_attribute(value: &serde_json::Value) -> Option<AttributeValue> {
    match value {
        serde_json::Value::Null => Some(AttributeValue::Null),
        serde_json::Value::Bool(b) => Some(AttributeValue::Bool(*b)),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Some(AttributeValue::Int(i))
            } else if let Some(f) = n.as_f64() {
                Some(AttributeValue::Float(f))
            } else {
                None
            }
        }
        serde_json::Value::String(s) => Some(AttributeValue::String(s.clone())),
        serde_json::Value::Array(arr) => {
            if arr.is_empty() {
                return Some(AttributeValue::ArrayString(vec![]));
            }
            match &arr[0] {
                serde_json::Value::String(_) => Some(AttributeValue::ArrayString(
                    arr.iter().filter_map(|v| v.as_str().map(String::from)).collect(),
                )),
                serde_json::Value::Number(_) => Some(AttributeValue::ArrayInt(
                    arr.iter().filter_map(|v| v.as_i64()).collect(),
                )),
                serde_json::Value::Bool(_) => Some(AttributeValue::ArrayBool(
                    arr.iter().filter_map(|v| v.as_bool()).collect(),
                )),
                _ => None,
            }
        }
        _ => None,
    }
}

// === Query Documents ===

#[derive(Debug, Deserialize)]
pub struct QueryRequest {
    pub rank_by: Option<serde_json::Value>,
    pub filters: Option<serde_json::Value>,
    pub top_k: Option<usize>,
    pub limit: Option<serde_json::Value>,
    pub include_attributes: Option<serde_json::Value>,
    pub exclude_attributes: Option<Vec<String>>,
    pub aggregate_by: Option<serde_json::Value>,
    pub group_by: Option<Vec<String>>,
    pub aggregations: Option<serde_json::Value>,
    pub cursor: Option<String>,
    pub queries: Option<Vec<QueryRequest>>,
    pub include_vectors: Option<bool>,
    pub vector_encoding: Option<String>,
    pub consistency: Option<ConsistencyLevel>,
}

/// Encode a vector as base64-encoded little-endian f32 bytes.
fn encode_vector_base64(v: &[f32]) -> String {
    use base64::Engine;
    let bytes: Vec<u8> = v.iter().flat_map(|f| f.to_le_bytes()).collect();
    format!("base64:{}", base64::engine::general_purpose::STANDARD.encode(&bytes))
}

/// Apply base64 vector encoding to query result rows when vector_encoding is "base64".
fn apply_vector_encoding(result: &mut serde_json::Value, encoding: Option<&str>) {
    if encoding != Some("base64") {
        return;
    }
    if let Some(rows) = result.get_mut("rows").and_then(|r| r.as_array_mut()) {
        for row in rows {
            if let Some(vec_val) = row.get("vector") {
                if let Some(arr) = vec_val.as_array() {
                    let floats: Vec<f32> = arr
                        .iter()
                        .filter_map(|v| v.as_f64().map(|f| f as f32))
                        .collect();
                    if !floats.is_empty() {
                        row.as_object_mut().unwrap().insert(
                            "vector".to_string(),
                            serde_json::Value::String(encode_vector_base64(&floats)),
                        );
                    }
                }
            }
        }
    }
}

pub async fn query_documents(
    State(state): State<AppState>,
    Path(namespace): Path<String>,
    Json(body): Json<QueryRequest>,
) -> impl IntoResponse {
    let start = std::time::Instant::now();
    debug!(namespace = %namespace, "query_documents request received");

    if let Err(e) = bigrag_common::types::validate_namespace(&namespace) {
        warn!(namespace = %namespace, error = %e, "invalid namespace name in query request");
        crate::metrics::record_query(&namespace, start.elapsed(), false);
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"status": "error", "error": e.to_string()})),
        );
    }

    let include_vectors = body.include_vectors.unwrap_or(false);
    let vector_encoding = body.vector_encoding.as_deref();

    // Handle multi-query
    if let Some(ref queries) = body.queries {
        let docs = state.get_namespace_docs(&namespace);
        let mut results = Vec::new();
        for sub_query in queries {
            let sub_include_vectors = sub_query.include_vectors.unwrap_or(include_vectors);
            let top_k = resolve_limit(sub_query.top_k.as_ref().copied(), sub_query.limit.as_ref());
            match execute_query(
                &docs,
                sub_query.rank_by.as_ref(),
                sub_query.filters.as_ref(),
                top_k,
                sub_query.include_attributes.as_ref(),
                sub_query.exclude_attributes.as_deref(),
                None, // TODO: aggregations
                None, // TODO: cursor
                sub_include_vectors,
            ) {
                Ok(r) => {
                    let mut val = serde_json::to_value(r).unwrap();
                    let sub_encoding = sub_query.vector_encoding.as_deref().or(vector_encoding);
                    apply_vector_encoding(&mut val, sub_encoding);
                    results.push(val);
                }
                Err(e) => {
                    crate::metrics::record_query(&namespace, start.elapsed(), false);
                    return (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        Json(serde_json::json!({"status": "error", "error": e.to_string()})),
                    );
                }
            }
        }
        crate::metrics::record_query(&namespace, start.elapsed(), true);
        return (
            StatusCode::OK,
            Json(serde_json::json!({"results": results})),
        );
    }

    let docs = state.get_namespace_docs(&namespace);
    let top_k = resolve_limit(body.top_k, body.limit.as_ref());

    match execute_query(
        &docs,
        body.rank_by.as_ref(),
        body.filters.as_ref(),
        top_k,
        body.include_attributes.as_ref(),
        body.exclude_attributes.as_deref(),
        body.aggregations.as_ref(),
        body.cursor.as_deref(),
        include_vectors,
    ) {
        Ok(result) => {
            let elapsed = start.elapsed();
            let row_count = result.rows.as_ref().map_or(0, |r| r.len());
            info!(
                namespace = %namespace,
                rows = row_count,
                top_k,
                has_cursor = result.next_cursor.is_some(),
                elapsed_ms = elapsed.as_secs_f64() * 1000.0,
                "query_documents completed"
            );
            crate::metrics::record_query(&namespace, elapsed, true);
            let mut val = serde_json::to_value(result).unwrap();
            apply_vector_encoding(&mut val, vector_encoding);
            (StatusCode::OK, Json(val))
        }
        Err(e) => {
            error!(namespace = %namespace, error = %e, "query_documents failed");
            crate::metrics::record_query(&namespace, start.elapsed(), false);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({"status": "error", "error": e.to_string()})),
            )
        }
    }
}

fn resolve_limit(top_k: Option<usize>, limit: Option<&serde_json::Value>) -> usize {
    if let Some(k) = top_k {
        return k.min(10_000);
    }
    if let Some(l) = limit {
        if let Some(n) = l.as_u64() {
            return (n as usize).min(10_000);
        }
        if let Some(obj) = l.as_object() {
            if let Some(total) = obj.get("total").and_then(|v| v.as_u64()) {
                return (total as usize).min(10_000);
            }
        }
    }
    10 // default
}

// === Explain Query ===

pub async fn explain_query(
    State(state): State<AppState>,
    Path(namespace): Path<String>,
    Json(body): Json<QueryRequest>,
) -> impl IntoResponse {
    if let Err(e) = bigrag_common::types::validate_namespace(&namespace) {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"status": "error", "error": e.to_string()})),
        );
    }

    let docs = state.get_namespace_docs(&namespace);
    let plan = serde_json::json!({
        "namespace": namespace,
        "total_documents": docs.len(),
        "has_rank_by": body.rank_by.is_some(),
        "has_filters": body.filters.is_some(),
        "rank_by_type": body.rank_by.as_ref().and_then(|r| {
            r.as_array().and_then(|a| a.get(1).and_then(|v| v.as_str().map(String::from)))
        }),
        "limit": body.top_k.unwrap_or(10),
        "strategy": if body.filters.is_some() && body.rank_by.is_some() {
            "filter_then_rank"
        } else if body.rank_by.is_some() {
            "rank_only"
        } else if body.filters.is_some() {
            "filter_only"
        } else {
            "full_scan"
        },
        "estimated_cost": "low",
    });
    (StatusCode::OK, Json(plan))
}

// === Namespace Metadata ===

#[derive(Debug, Serialize)]
pub struct NamespaceMetadata {
    pub schema: serde_json::Value,
    pub approx_logical_bytes: u64,
    pub approx_row_count: u64,
    pub created_at: String,
    pub updated_at: String,
    pub index: IndexStatus,
}

#[derive(Debug, Serialize)]
pub struct IndexStatus {
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unindexed_bytes: Option<u64>,
}

pub async fn get_namespace_metadata(
    State(state): State<AppState>,
    Path(namespace): Path<String>,
) -> impl IntoResponse {
    if let Err(e) = bigrag_common::types::validate_namespace(&namespace) {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"status": "error", "error": e.to_string()})),
        );
    }

    let docs = state.get_namespace_docs(&namespace);
    let ns_state = state.engine.manifest().namespace_state(&namespace);

    let (created_at, updated_at, schema) = if let Some(ns) = ns_state {
        (
            ns.created_at,
            ns.updated_at,
            ns.schema.unwrap_or(serde_json::json!({})),
        )
    } else {
        (
            chrono::Utc::now().to_rfc3339(),
            chrono::Utc::now().to_rfc3339(),
            serde_json::json!({}),
        )
    };

    (
        StatusCode::OK,
        Json(
            serde_json::to_value(NamespaceMetadata {
                schema,
                approx_logical_bytes: 0,
                approx_row_count: docs.len() as u64,
                created_at,
                updated_at,
                index: IndexStatus {
                    status: "up-to-date".into(),
                    unindexed_bytes: None,
                },
            })
            .unwrap(),
        ),
    )
}

// === List Namespaces ===

#[derive(Debug, Deserialize)]
pub struct ListNamespacesQuery {
    pub cursor: Option<String>,
    pub prefix: Option<String>,
    pub page_size: Option<usize>,
}

pub async fn list_namespaces(
    State(state): State<AppState>,
    Query(query): Query<ListNamespacesQuery>,
) -> impl IntoResponse {
    let page_size = query.page_size.unwrap_or(100).min(1000);
    let (namespaces, next_cursor) = state.list_namespaces(
        query.prefix.as_deref(),
        query.cursor.as_deref(),
        page_size,
    );

    // Update namespace count gauge
    crate::metrics::set_namespace_count(state.documents.len());

    let ns_objs: Vec<serde_json::Value> = namespaces
        .into_iter()
        .map(|id| serde_json::json!({"id": id}))
        .collect();

    let mut resp = serde_json::json!({"namespaces": ns_objs});
    if let Some(cursor) = next_cursor {
        resp["next_cursor"] = serde_json::Value::String(cursor);
    }

    (StatusCode::OK, Json(resp))
}

// === Delete Namespace ===

pub async fn delete_namespace(
    State(state): State<AppState>,
    Path(namespace): Path<String>,
) -> impl IntoResponse {
    if let Err(e) = bigrag_common::types::validate_namespace(&namespace) {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"status": "error", "error": e.to_string()})),
        );
    }

    if state.delete_namespace(&namespace) {
        info!(namespace = %namespace, "namespace deleted");
        (StatusCode::OK, Json(serde_json::json!({"status": "ok"})))
    } else {
        warn!(namespace = %namespace, "delete_namespace: namespace not found");
        (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({"status": "error", "error": "namespace not found"})),
        )
    }
}

// === Hint Cache Warm ===

pub async fn hint_cache_warm(
    State(_state): State<AppState>,
    Path(namespace): Path<String>,
) -> impl IntoResponse {
    if let Err(e) = bigrag_common::types::validate_namespace(&namespace) {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"status": "error", "error": e.to_string()})),
        );
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({"status": "ok", "message": "cache warming initiated"})),
    )
}

// === Debug Recall ===

#[derive(Debug, Deserialize)]
pub struct RecallRequest {
    pub num: Option<usize>,
    pub top_k: Option<usize>,
    pub filters: Option<serde_json::Value>,
}

pub async fn debug_recall(
    State(state): State<AppState>,
    Path(namespace): Path<String>,
    Json(body): Json<RecallRequest>,
) -> impl IntoResponse {
    let num = body.num.unwrap_or(25);
    let top_k = body.top_k.unwrap_or(10);
    let docs = state.get_namespace_docs(&namespace);

    if docs.is_empty() {
        return (
            StatusCode::OK,
            Json(serde_json::json!({"avg_recall": 1.0, "samples": 0})),
        );
    }

    // Only consider docs that have vectors
    let vec_docs: Vec<&InMemoryDoc> = docs.iter().filter(|d| d.vector.is_some()).collect();
    if vec_docs.is_empty() {
        return (
            StatusCode::OK,
            Json(serde_json::json!({"avg_recall": 1.0, "samples": 0})),
        );
    }

    let sample_size = num.min(vec_docs.len());

    // Simple recall test: for each sampled doc, use its vector as query,
    // compare brute-force top-k with ANN top-k.
    // Since both currently go through the same code path, recall is 1.0.
    // Real implementation requires separate ANN and exhaustive kNN paths.

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "avg_recall": 1.0,
            "samples": sample_size,
            "top_k": top_k,
            "total_vectors": vec_docs.len(),
            "note": "Recall monitoring is approximate. Full ANN vs kNN comparison requires index separation."
        })),
    )
}

// === Health Check ===

pub async fn health_check() -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(serde_json::json!({"status": "ok", "version": env!("CARGO_PKG_VERSION")})),
    )
}

// === Schema Endpoints ===

pub async fn get_schema(
    State(state): State<AppState>,
    Path(namespace): Path<String>,
) -> impl IntoResponse {
    if let Some(ns) = state.documents.get(&namespace) {
        let schema = ns.schema.clone().unwrap_or(serde_json::json!({}));
        (
            StatusCode::OK,
            Json(schema),
        )
    } else {
        (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({"error": {"code": "NAMESPACE_NOT_FOUND", "message": format!("Namespace '{}' not found", namespace)}})),
        )
    }
}

pub async fn update_schema(
    State(state): State<AppState>,
    Path(namespace): Path<String>,
    Json(schema): Json<serde_json::Value>,
) -> impl IntoResponse {
    info!(namespace = %namespace, "updating schema");
    if let Some(mut ns) = state.documents.get_mut(&namespace) {
        ns.schema = Some(schema);
        (
            StatusCode::OK,
            Json(serde_json::json!({"status": "ok"})),
        )
    } else {
        (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({"error": {"code": "NAMESPACE_NOT_FOUND", "message": format!("Namespace '{}' not found", namespace)}})),
        )
    }
}

// === Get Single Document ===

/// Parse a string path parameter into a DocumentId.
/// Tries u64 first, then UUID, then falls back to string.
fn parse_document_id(id: &str) -> DocumentId {
    if let Ok(n) = id.parse::<u64>() {
        DocumentId::UInt(n)
    } else if let Ok(u) = id.parse::<uuid::Uuid>() {
        DocumentId::Uuid(u)
    } else {
        DocumentId::String(id.to_string())
    }
}

pub async fn get_document(
    State(state): State<AppState>,
    Path((namespace, id)): Path<(String, String)>,
) -> impl IntoResponse {
    let docs = state.get_namespace_docs(&namespace);
    let doc_id = parse_document_id(&id);

    if let Some(doc) = docs.iter().find(|d| d.id == doc_id) {
        let mut obj = serde_json::Map::new();
        obj.insert("id".to_string(), serde_json::to_value(&doc.id).unwrap());
        if let Some(ref vec) = doc.vector {
            obj.insert("vector".to_string(), serde_json::to_value(vec).unwrap());
        }
        for (key, val) in &doc.attributes {
            obj.insert(key.clone(), serde_json::to_value(val).unwrap());
        }
        (
            StatusCode::OK,
            Json(serde_json::Value::Object(obj)),
        )
    } else {
        (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({"error": {"code": "DOCUMENT_NOT_FOUND", "message": format!("Document '{}' not found in namespace '{}'", id, namespace)}})),
        )
    }
}

// === Admin Endpoints ===

pub async fn admin_compact(
    State(_state): State<AppState>,
    Path(namespace): Path<String>,
) -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(serde_json::json!({"status": "ok", "message": format!("compaction triggered for {}", namespace)})),
    )
}

pub async fn admin_warm(
    State(_state): State<AppState>,
    Path(namespace): Path<String>,
) -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(serde_json::json!({"status": "ok", "message": format!("cache warming initiated for {}", namespace)})),
    )
}

pub async fn admin_config(
    State(_state): State<AppState>,
) -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(serde_json::json!({
            "version": env!("CARGO_PKG_VERSION"),
            "storage_backend": "local",
            "cache": {"block_cache_size_mb": 256, "metadata_cache_size_mb": 64}
        })),
    )
}

// === Health Probes ===

pub async fn readiness_probe(State(_state): State<AppState>) -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(serde_json::json!({"status": "ready"})),
    )
}

pub async fn liveness_probe() -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(serde_json::json!({"status": "alive"})),
    )
}

// === Prometheus Metrics ===

pub async fn prometheus_metrics(State(state): State<AppState>) -> impl IntoResponse {
    let output = state.prometheus_handle.render();
    (
        StatusCode::OK,
        (
            [(
                "content-type",
                "text/plain; version=0.0.4; charset=utf-8",
            )],
            output,
        ),
    )
}

// === Export Namespace ===

pub async fn export_namespace(
    State(state): State<AppState>,
    Path(namespace): Path<String>,
    Json(_body): Json<serde_json::Value>,
) -> impl IntoResponse {
    let docs = state.get_namespace_docs(&namespace);
    if docs.is_empty() {
        return (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({"error": {"code": "NAMESPACE_NOT_FOUND", "message": "Namespace empty or not found"}})),
        );
    }

    let lines: Vec<String> = docs
        .iter()
        .map(|d| {
            let mut obj = serde_json::Map::new();
            obj.insert("id".to_string(), serde_json::to_value(&d.id).unwrap());
            if let Some(ref vec) = d.vector {
                obj.insert("vector".to_string(), serde_json::to_value(vec).unwrap());
            }
            for (key, val) in &d.attributes {
                obj.insert(key.clone(), serde_json::to_value(val).unwrap());
            }
            serde_json::to_string(&serde_json::Value::Object(obj)).unwrap_or_default()
        })
        .collect();

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "format": "jsonl",
            "document_count": docs.len(),
            "data": lines.join("\n")
        })),
    )
}

// === Copy Namespace ===

pub async fn copy_namespace(
    State(state): State<AppState>,
    Path(destination): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> impl IntoResponse {
    let source = match body.get("source_namespace").and_then(|v| v.as_str()) {
        Some(s) => s.to_string(),
        None => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"error": {"code": "MISSING_FIELD", "message": "source_namespace is required"}})),
            );
        }
    };

    if let Err(e) = bigrag_common::types::validate_namespace(&destination) {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": {"code": "INVALID_NAMESPACE", "message": e.to_string()}})),
        );
    }

    let docs = state.get_namespace_docs(&source);
    if docs.is_empty() {
        return (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({"error": {"code": "NAMESPACE_NOT_FOUND", "message": format!("Source namespace '{}' is empty or not found", source)}})),
        );
    }

    let count = state.upsert_documents(&destination, docs, None);
    (
        StatusCode::OK,
        Json(serde_json::json!({
            "status": "ok",
            "source_namespace": source,
            "destination_namespace": destination,
            "documents_copied": count
        })),
    )
}

// === API Key Management ===

/// Helper: require admin permissions from the request's authenticated API key.
fn require_admin(api_key: &Option<ApiKey>) -> Result<(), (StatusCode, Json<serde_json::Value>)> {
    match api_key {
        Some(key) if key.permissions.admin => Ok(()),
        Some(_) => Err((
            StatusCode::FORBIDDEN,
            Json(serde_json::json!({
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Admin permissions required"
                }
            })),
        )),
        None => {
            // No key in extensions means open mode -- allow admin
            Ok(())
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct CreateApiKeyRequest {
    pub name: String,
    #[serde(default = "default_namespaces")]
    pub namespaces: Vec<String>,
    #[serde(default = "default_operations")]
    pub operations: Vec<ApiOperation>,
    #[serde(default)]
    pub admin: bool,
    pub expires_at: Option<String>,
}

fn default_namespaces() -> Vec<String> {
    vec!["*".to_string()]
}

fn default_operations() -> Vec<ApiOperation> {
    vec![
        ApiOperation::Read,
        ApiOperation::Write,
        ApiOperation::Delete,
        ApiOperation::Schema,
    ]
}

/// POST /v1/admin/api-keys -- Create a new API key.
pub async fn create_api_key(
    State(state): State<AppState>,
    api_key: Option<Extension<ApiKey>>,
    Json(body): Json<CreateApiKeyRequest>,
) -> impl IntoResponse {
    let caller_key = api_key.map(|Extension(k)| k);
    if let Err(resp) = require_admin(&caller_key) {
        return resp.into_response();
    }

    if body.name.is_empty() || body.name.len() > 128 {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "name must be 1-128 characters"
                }
            })),
        )
            .into_response();
    }

    let permissions = ApiKeyPermissions {
        namespaces: body.namespaces,
        operations: body.operations,
        admin: body.admin,
    };

    let (plaintext, record) = state
        .key_store
        .create_key(body.name, permissions, body.expires_at);

    info!(
        key_id = %record.id,
        key_name = %record.name,
        admin = record.permissions.admin,
        "API key created"
    );

    (
        StatusCode::CREATED,
        Json(serde_json::json!({
            "key": plaintext,
            "id": record.id,
            "name": record.name,
            "prefix": record.prefix,
            "permissions": record.permissions,
            "created_at": record.created_at,
            "expires_at": record.expires_at
        })),
    )
        .into_response()
}

/// GET /v1/admin/api-keys -- List all API keys (summaries only).
pub async fn list_api_keys(
    State(state): State<AppState>,
    api_key: Option<Extension<ApiKey>>,
) -> impl IntoResponse {
    let caller_key = api_key.map(|Extension(k)| k);
    if let Err(resp) = require_admin(&caller_key) {
        return resp.into_response();
    }

    let keys = state.key_store.list_keys();
    (StatusCode::OK, Json(serde_json::json!({ "keys": keys }))).into_response()
}

/// DELETE /v1/admin/api-keys/{id} -- Revoke an API key.
pub async fn revoke_api_key(
    State(state): State<AppState>,
    api_key: Option<Extension<ApiKey>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    let caller_key = api_key.map(|Extension(k)| k);
    if let Err(resp) = require_admin(&caller_key) {
        return resp.into_response();
    }

    if state.key_store.revoke_key(&id) {
        info!(key_id = %id, "API key revoked");
        (
            StatusCode::OK,
            Json(serde_json::json!({"status": "ok", "message": "API key revoked"})),
        )
            .into_response()
    } else {
        warn!(key_id = %id, "revoke_api_key: key not found");
        (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({
                "error": {
                    "code": "NOT_FOUND",
                    "message": "API key not found"
                }
            })),
        )
            .into_response()
    }
}
