use axum::{
    Json,
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
};
use bigrag_common::types::{
    AttributeValue, BillingInfo, ConsistencyLevel, DistanceMetric, DocumentId, PerformanceInfo,
};
use bigrag_query::executor::{execute_query, InMemoryDoc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::state::{AppState, PatchDoc};

// === Write Documents ===

#[derive(Debug, Deserialize)]
pub struct WriteRequest {
    pub upsert_rows: Option<Vec<serde_json::Value>>,
    pub upsert_columns: Option<serde_json::Value>,
    pub patch_rows: Option<Vec<serde_json::Value>>,
    pub deletes: Option<Vec<serde_json::Value>>,
    pub delete_by_filter: Option<serde_json::Value>,
    pub patch_by_filter: Option<serde_json::Value>,
    pub distance_metric: Option<String>,
    pub schema: Option<serde_json::Value>,
    pub return_affected_ids: Option<bool>,
    pub disable_backpressure: Option<bool>,
    pub condition: Option<serde_json::Value>,
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

    // Validate namespace
    if let Err(e) = bigrag_common::types::validate_namespace(&namespace) {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"status": "error", "error": e.to_string()})),
        );
    }

    let distance_metric = body.distance_metric.as_deref().and_then(|m| match m {
        "cosine_distance" => Some(DistanceMetric::CosineDistance),
        "euclidean_squared" => Some(DistanceMetric::EuclideanSquared),
        _ => None,
    });

    let mut total_affected = 0usize;
    let mut upserted_count = 0usize;
    let mut deleted_count = 0usize;

    // Process deletes first (per spec ordering)
    if let Some(ref delete_ids) = body.deletes {
        let ids: Vec<DocumentId> = delete_ids
            .iter()
            .filter_map(|v| serde_json::from_value(v.clone()).ok())
            .collect();
        deleted_count = state.delete_documents(&namespace, &ids);
        total_affected += deleted_count;
    }

    // Process upserts
    if let Some(ref rows) = body.upsert_rows {
        let mut docs = Vec::new();
        for row in rows {
            if let Some(doc) = parse_upsert_row(row) {
                docs.push(doc);
            }
        }
        upserted_count = state.upsert_documents(&namespace, docs, distance_metric);
        total_affected += upserted_count;
    }

    // Process column-based upserts
    if let Some(ref columns) = body.upsert_columns {
        if let Some(docs) = parse_upsert_columns(columns) {
            upserted_count += state.upsert_documents(&namespace, docs, distance_metric);
            total_affected += upserted_count;
        }
    }

    let elapsed = start.elapsed();

    (
        StatusCode::OK,
        Json(serde_json::to_value(WriteResponse {
            rows_affected: total_affected,
            rows_upserted: if upserted_count > 0 {
                Some(upserted_count)
            } else {
                None
            },
            rows_patched: None,
            rows_deleted: if deleted_count > 0 {
                Some(deleted_count)
            } else {
                None
            },
            upserted_ids: None,
            patched_ids: None,
            deleted_ids: None,
            billing: BillingInfo::default(),
            performance: PerformanceInfo {
                server_total_ms: elapsed.as_secs_f64() * 1000.0,
                ..Default::default()
            },
        }).unwrap()),
    )
}

fn parse_upsert_row(row: &serde_json::Value) -> Option<InMemoryDoc> {
    let obj = row.as_object()?;
    let id: DocumentId = serde_json::from_value(obj.get("id")?.clone()).ok()?;

    let vector = obj.get("vector").and_then(|v| {
        v.as_array().map(|arr| {
            arr.iter()
                .filter_map(|n| n.as_f64().map(|f| f as f32))
                .collect()
        })
    });

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

fn parse_upsert_columns(columns: &serde_json::Value) -> Option<Vec<InMemoryDoc>> {
    let obj = columns.as_object()?;
    let ids = obj.get("id")?.as_array()?;
    let vectors = obj.get("vector").and_then(|v| v.as_array());

    let n = ids.len();
    let mut docs = Vec::with_capacity(n);

    for i in 0..n {
        let id: DocumentId = serde_json::from_value(ids[i].clone()).ok()?;

        let vector = vectors.and_then(|vecs| {
            vecs.get(i).and_then(|v| {
                if v.is_null() {
                    None
                } else {
                    v.as_array().map(|arr| {
                        arr.iter()
                            .filter_map(|n| n.as_f64().map(|f| f as f32))
                            .collect()
                    })
                }
            })
        });

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
    pub queries: Option<Vec<QueryRequest>>,
    pub vector_encoding: Option<String>,
    pub consistency: Option<ConsistencyLevel>,
}

pub async fn query_documents(
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

    // Handle multi-query
    if let Some(ref queries) = body.queries {
        let docs = state.get_namespace_docs(&namespace);
        let mut results = Vec::new();
        for sub_query in queries {
            let top_k = resolve_limit(sub_query.top_k.as_ref().copied(), sub_query.limit.as_ref());
            match execute_query(
                &docs,
                sub_query.rank_by.as_ref(),
                sub_query.filters.as_ref(),
                top_k,
                sub_query.include_attributes.as_ref(),
                sub_query.exclude_attributes.as_deref(),
            ) {
                Ok(r) => results.push(serde_json::to_value(r).unwrap()),
                Err(e) => {
                    return (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        Json(serde_json::json!({"status": "error", "error": e.to_string()})),
                    );
                }
            }
        }
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
    ) {
        Ok(result) => (StatusCode::OK, Json(serde_json::to_value(result).unwrap())),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({"status": "error", "error": e.to_string()})),
        ),
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
        (StatusCode::OK, Json(serde_json::json!({"status": "ok"})))
    } else {
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
    State(_state): State<AppState>,
    Path(_namespace): Path<String>,
    Json(body): Json<RecallRequest>,
) -> impl IntoResponse {
    let _num = body.num.unwrap_or(25);
    let _top_k = body.top_k.unwrap_or(10);

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "avg_recall": 1.0,
            "avg_exhaustive_count": 0,
            "avg_ann_count": 0
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
