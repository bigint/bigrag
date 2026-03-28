use base64::Engine;
use bigrag_common::types::{AttributeValue, BillingInfo, DocumentId, PerformanceInfo};
use std::collections::HashMap;

use crate::filter::{evaluate_filter, parse_filter};
use crate::ranking::{parse_rank_by, RankBy};

// === Aggregation types ===

/// Aggregation request types.
#[derive(Debug, Clone)]
pub enum AggregationRequest {
    Count,
    Sum { attribute: String },
    Min { attribute: String },
    Max { attribute: String },
    GroupBy { attribute: String, limit: usize },
    Distinct { attribute: String },
}

/// Parse aggregation requests from JSON.
/// Expects an array of objects like:
/// `[{"type": "count"}, {"type": "sum", "attribute": "score"}]`
pub fn parse_aggregations(
    json: &serde_json::Value,
) -> Result<Vec<AggregationRequest>, QueryError> {
    let arr = json
        .as_array()
        .ok_or_else(|| QueryError::Filter("aggregations must be an array".into()))?;

    let mut aggs = Vec::with_capacity(arr.len());
    for item in arr {
        let obj = item
            .as_object()
            .ok_or_else(|| QueryError::Filter("each aggregation must be an object".into()))?;
        let agg_type = obj
            .get("type")
            .and_then(|v| v.as_str())
            .ok_or_else(|| QueryError::Filter("aggregation missing 'type' field".into()))?;

        let agg = match agg_type {
            "count" => AggregationRequest::Count,
            "sum" => AggregationRequest::Sum {
                attribute: require_attribute(obj, "sum")?,
            },
            "min" => AggregationRequest::Min {
                attribute: require_attribute(obj, "min")?,
            },
            "max" => AggregationRequest::Max {
                attribute: require_attribute(obj, "max")?,
            },
            "group_by" => AggregationRequest::GroupBy {
                attribute: require_attribute(obj, "group_by")?,
                limit: obj
                    .get("limit")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(10) as usize,
            },
            "distinct" => AggregationRequest::Distinct {
                attribute: require_attribute(obj, "distinct")?,
            },
            other => {
                return Err(QueryError::Filter(format!(
                    "unknown aggregation type: {other}"
                )));
            }
        };
        aggs.push(agg);
    }
    Ok(aggs)
}

fn require_attribute(
    obj: &serde_json::Map<String, serde_json::Value>,
    agg_type: &str,
) -> Result<String, QueryError> {
    obj.get("attribute")
        .and_then(|v| v.as_str())
        .map(String::from)
        .ok_or_else(|| {
            QueryError::Filter(format!(
                "aggregation '{agg_type}' requires an 'attribute' field"
            ))
        })
}

/// Execute aggregation requests against a set of documents.
pub fn execute_aggregations(
    docs: &[&InMemoryDoc],
    aggregations: &[AggregationRequest],
) -> HashMap<String, serde_json::Value> {
    let mut results = HashMap::new();
    for agg in aggregations {
        match agg {
            AggregationRequest::Count => {
                results.insert("count".to_string(), serde_json::json!(docs.len()));
            }
            AggregationRequest::Sum { attribute } => {
                let sum: f64 = docs
                    .iter()
                    .filter_map(|d| {
                        d.attributes.get(attribute).and_then(|v| match v {
                            AttributeValue::Int(i) => Some(*i as f64),
                            AttributeValue::UInt(u) => Some(*u as f64),
                            AttributeValue::Float(f) => Some(*f),
                            _ => None,
                        })
                    })
                    .sum();
                results.insert(format!("sum_{attribute}"), serde_json::json!(sum));
            }
            AggregationRequest::Min { attribute } => {
                let min = docs
                    .iter()
                    .filter_map(|d| {
                        d.attributes.get(attribute).and_then(|v| match v {
                            AttributeValue::Int(i) => Some(*i as f64),
                            AttributeValue::UInt(u) => Some(*u as f64),
                            AttributeValue::Float(f) => Some(*f),
                            AttributeValue::DateTime(dt) => Some(dt.timestamp() as f64),
                            _ => None,
                        })
                    })
                    .fold(f64::INFINITY, f64::min);
                if min.is_finite() {
                    results.insert(format!("min_{attribute}"), serde_json::json!(min));
                } else {
                    results.insert(
                        format!("min_{attribute}"),
                        serde_json::Value::Null,
                    );
                }
            }
            AggregationRequest::Max { attribute } => {
                let max = docs
                    .iter()
                    .filter_map(|d| {
                        d.attributes.get(attribute).and_then(|v| match v {
                            AttributeValue::Int(i) => Some(*i as f64),
                            AttributeValue::UInt(u) => Some(*u as f64),
                            AttributeValue::Float(f) => Some(*f),
                            AttributeValue::DateTime(dt) => Some(dt.timestamp() as f64),
                            _ => None,
                        })
                    })
                    .fold(f64::NEG_INFINITY, f64::max);
                if max.is_finite() {
                    results.insert(format!("max_{attribute}"), serde_json::json!(max));
                } else {
                    results.insert(
                        format!("max_{attribute}"),
                        serde_json::Value::Null,
                    );
                }
            }
            AggregationRequest::GroupBy { attribute, limit } => {
                let mut groups: HashMap<String, usize> = HashMap::new();
                for doc in docs {
                    if let Some(val) = doc.attributes.get(attribute) {
                        let key = attribute_to_json(val).to_string();
                        *groups.entry(key).or_insert(0) += 1;
                    }
                }
                // Sort by count descending, take top limit
                let mut sorted: Vec<_> = groups.into_iter().collect();
                sorted.sort_by(|a, b| b.1.cmp(&a.1));
                sorted.truncate(*limit);
                let group_list: Vec<serde_json::Value> = sorted
                    .into_iter()
                    .map(|(key, count)| serde_json::json!({"value": key, "count": count}))
                    .collect();
                results.insert(
                    format!("group_by_{attribute}"),
                    serde_json::json!(group_list),
                );
            }
            AggregationRequest::Distinct { attribute } => {
                let mut seen = std::collections::HashSet::new();
                let mut distinct_values = Vec::new();
                for doc in docs {
                    if let Some(val) = doc.attributes.get(attribute) {
                        let json_val = attribute_to_json(val);
                        let key = json_val.to_string();
                        if seen.insert(key) {
                            distinct_values.push(json_val);
                        }
                    }
                }
                results.insert(
                    format!("distinct_{attribute}"),
                    serde_json::json!(distinct_values),
                );
            }
        }
    }
    results
}

// === Cursor-based pagination ===

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
struct CursorData {
    last_id: DocumentId,
    #[serde(skip_serializing_if = "Option::is_none")]
    last_score: Option<f64>,
}

/// Decode a base64-encoded cursor string into CursorData.
pub fn decode_cursor(cursor: &str) -> Result<CursorData, QueryError> {
    let decoded = base64::engine::general_purpose::STANDARD
        .decode(cursor)
        .map_err(|_| QueryError::Filter("invalid cursor".into()))?;
    serde_json::from_slice(&decoded)
        .map_err(|_| QueryError::Filter("invalid cursor format".into()))
}

/// Encode CursorData into a base64 string.
pub fn encode_cursor(data: &CursorData) -> String {
    let json = serde_json::to_vec(data).unwrap();
    base64::engine::general_purpose::STANDARD.encode(&json)
}

/// A query result row.
#[derive(Debug, Clone, serde::Serialize)]
pub struct QueryResultRow {
    pub id: DocumentId,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "$dist")]
    pub dist: Option<f64>,
    #[serde(flatten)]
    pub attributes: HashMap<String, serde_json::Value>,
}

/// Query execution result.
#[derive(Debug, Clone, serde::Serialize)]
pub struct QueryResult {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rows: Option<Vec<QueryResultRow>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub next_cursor: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub results: Option<Vec<QueryResult>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub aggregations: Option<HashMap<String, serde_json::Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub aggregation_groups: Option<Vec<serde_json::Value>>,
    pub billing: BillingInfo,
    pub performance: PerformanceInfo,
}

/// In-memory document representation for query evaluation.
#[derive(Debug, Clone)]
pub struct InMemoryDoc {
    pub id: DocumentId,
    pub vector: Option<Vec<f32>>,
    pub attributes: HashMap<String, AttributeValue>,
}

/// Execute a query against in-memory documents.
/// This is the core query executor that handles filtering, ranking, projection,
/// aggregations, and cursor-based pagination.
pub fn execute_query(
    docs: &[InMemoryDoc],
    rank_by: Option<&serde_json::Value>,
    filters: Option<&serde_json::Value>,
    top_k: usize,
    include_attributes: Option<&serde_json::Value>,
    exclude_attributes: Option<&[String]>,
    aggregations: Option<&serde_json::Value>,
    cursor: Option<&str>,
) -> Result<QueryResult, QueryError> {
    let start = std::time::Instant::now();

    // Parse and apply filters
    let filtered: Vec<&InMemoryDoc> = if let Some(filter_json) = filters {
        let filter = parse_filter(filter_json).map_err(|e| QueryError::Filter(e.to_string()))?;
        docs.iter()
            .filter(|d| evaluate_filter(&filter, &d.attributes))
            .collect()
    } else {
        docs.iter().collect()
    };

    // Execute aggregations on filtered (pre-ranking) docs
    let agg_results = if let Some(agg_json) = aggregations {
        let agg_requests = parse_aggregations(agg_json)?;
        let result = execute_aggregations(&filtered, &agg_requests);
        if result.is_empty() {
            None
        } else {
            Some(result)
        }
    } else {
        None
    };

    // Decode cursor if provided
    let cursor_data = if let Some(c) = cursor {
        Some(decode_cursor(c)?)
    } else {
        None
    };

    // Parse rank_by and score
    let ranked = if let Some(rank_json) = rank_by {
        let rank_expr =
            parse_rank_by(rank_json).map_err(|e| QueryError::Ranking(e.to_string()))?;
        let mut scored: Vec<(&InMemoryDoc, f64)> = filtered
            .iter()
            .filter_map(|doc| {
                let score = score_document(doc, &rank_expr);
                if score > 0.0 {
                    Some((*doc, score))
                } else {
                    None
                }
            })
            .collect();

        // Sort by score descending
        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        // Apply cursor: skip past the cursor position
        if let Some(ref cd) = cursor_data {
            let skip_pos = scored.iter().position(|(doc, score)| {
                doc.id == cd.last_id
                    && cd.last_score.map_or(true, |cs| (*score - cs).abs() < f64::EPSILON)
            });
            if let Some(pos) = skip_pos {
                scored = scored.split_off(pos + 1);
            }
        }

        // Take top_k + 1 to determine if there's a next page
        scored.truncate(top_k + 1);
        scored
    } else {
        let mut collected: Vec<(&InMemoryDoc, f64)> =
            filtered.into_iter().map(|d| (d, 0.0)).collect();

        // Apply cursor: skip past the cursor position
        if let Some(ref cd) = cursor_data {
            let skip_pos = collected.iter().position(|(doc, _)| doc.id == cd.last_id);
            if let Some(pos) = skip_pos {
                collected = collected.split_off(pos + 1);
            }
        }

        collected.truncate(top_k + 1);
        collected
    };

    // Determine if there's a next page
    let has_next = ranked.len() > top_k;
    let page_results: Vec<(&InMemoryDoc, f64)> = ranked.into_iter().take(top_k).collect();

    // Build next_cursor from the last result in the page
    let next_cursor = if has_next {
        page_results.last().map(|(doc, score)| {
            encode_cursor(&CursorData {
                last_id: doc.id.clone(),
                last_score: if rank_by.is_some() {
                    Some(*score)
                } else {
                    None
                },
            })
        })
    } else {
        None
    };

    // Project attributes
    let rows: Vec<QueryResultRow> = page_results
        .into_iter()
        .map(|(doc, score)| {
            let mut attrs = HashMap::new();
            let include_all = include_attributes
                .map(|v| v.as_bool() == Some(true))
                .unwrap_or(false);

            let include_list: Option<Vec<String>> = include_attributes.and_then(|v| {
                v.as_array().map(|arr| {
                    arr.iter()
                        .filter_map(|s| s.as_str().map(String::from))
                        .collect()
                })
            });

            for (key, value) in &doc.attributes {
                let should_include = if include_all {
                    true
                } else if let Some(ref list) = include_list {
                    list.contains(key)
                } else {
                    false // Default: only id
                };

                let should_exclude = exclude_attributes
                    .map(|excl| excl.contains(key))
                    .unwrap_or(false);

                if should_include && !should_exclude {
                    attrs.insert(key.clone(), attribute_to_json(value));
                }
            }

            QueryResultRow {
                id: doc.id.clone(),
                dist: if rank_by.is_some() {
                    Some(score)
                } else {
                    None
                },
                attributes: attrs,
            }
        })
        .collect();

    let elapsed = start.elapsed();

    Ok(QueryResult {
        rows: Some(rows),
        next_cursor,
        results: None,
        aggregations: agg_results,
        aggregation_groups: None,
        billing: BillingInfo::default(),
        performance: PerformanceInfo {
            server_total_ms: elapsed.as_secs_f64() * 1000.0,
            query_execution_ms: Some(elapsed.as_secs_f64() * 1000.0),
            ..Default::default()
        },
    })
}

fn score_document(doc: &InMemoryDoc, rank: &RankBy) -> f64 {
    match rank {
        RankBy::Ann { vector } | RankBy::Knn { vector } => {
            if let Some(ref doc_vec) = doc.vector {
                // Return distance (lower = better, but we want higher score first)
                // We'll negate for sorting since we sort descending
                let dist = cosine_distance_f64(doc_vec, vector);
                if dist == 0.0 {
                    return 0.0;
                }
                1.0 / (1.0 + dist as f64)
            } else {
                0.0
            }
        }
        RankBy::Bm25 { .. } => {
            // BM25 scoring handled by inverted index
            // Placeholder: return 1.0 for now
            1.0
        }
        RankBy::OrderByAttribute { attribute, descending } => {
            if let Some(val) = doc.attributes.get(attribute) {
                attribute_to_sort_key(val, *descending)
            } else {
                f64::MIN
            }
        }
        RankBy::Sum(clauses) => clauses.iter().map(|c| score_document(doc, c)).sum(),
        RankBy::Max(clauses) => clauses
            .iter()
            .map(|c| score_document(doc, c))
            .fold(0.0f64, f64::max),
        RankBy::Product { weight, clause } => weight * score_document(doc, clause),
        RankBy::Attribute(name) => {
            if let Some(val) = doc.attributes.get(name) {
                attribute_to_f64(val)
            } else {
                0.0
            }
        }
        RankBy::Saturate {
            clause,
            midpoint,
            exponent,
        } => {
            let x = score_document(doc, clause);
            crate::ranking::saturate(x, *midpoint, *exponent)
        }
        RankBy::Decay {
            clause,
            midpoint,
            exponent,
        } => {
            let x = score_document(doc, clause);
            crate::ranking::decay(x, *midpoint, *exponent)
        }
        RankBy::FilterAsRank(filter_json) => {
            if let Ok(filter) = parse_filter(filter_json) {
                if evaluate_filter(&filter, &doc.attributes) {
                    1.0
                } else {
                    0.0
                }
            } else {
                0.0
            }
        }
        _ => 0.0,
    }
}

fn cosine_distance_f64(a: &[f32], b: &[f32]) -> f64 {
    let mut dot = 0.0f64;
    let mut norm_a = 0.0f64;
    let mut norm_b = 0.0f64;
    for i in 0..a.len().min(b.len()) {
        dot += a[i] as f64 * b[i] as f64;
        norm_a += (a[i] as f64) * (a[i] as f64);
        norm_b += (b[i] as f64) * (b[i] as f64);
    }
    let denom = norm_a.sqrt() * norm_b.sqrt();
    if denom == 0.0 {
        2.0
    } else {
        1.0 - (dot / denom)
    }
}

fn attribute_to_f64(val: &AttributeValue) -> f64 {
    match val {
        AttributeValue::Int(n) => *n as f64,
        AttributeValue::UInt(n) => *n as f64,
        AttributeValue::Float(n) => *n,
        _ => 0.0,
    }
}

fn attribute_to_sort_key(val: &AttributeValue, descending: bool) -> f64 {
    let v = attribute_to_f64(val);
    if descending { v } else { -v }
}

fn attribute_to_json(val: &AttributeValue) -> serde_json::Value {
    match val {
        AttributeValue::Null => serde_json::Value::Null,
        AttributeValue::Bool(b) => serde_json::Value::Bool(*b),
        AttributeValue::Int(n) => serde_json::json!(n),
        AttributeValue::UInt(n) => serde_json::json!(n),
        AttributeValue::Float(n) => serde_json::json!(n),
        AttributeValue::String(s) => serde_json::Value::String(s.clone()),
        AttributeValue::Uuid(u) => serde_json::Value::String(u.to_string()),
        AttributeValue::DateTime(dt) => serde_json::Value::String(dt.to_rfc3339()),
        AttributeValue::ArrayString(arr) => serde_json::json!(arr),
        AttributeValue::ArrayInt(arr) => serde_json::json!(arr),
        AttributeValue::ArrayUInt(arr) => serde_json::json!(arr),
        AttributeValue::ArrayFloat(arr) => serde_json::json!(arr),
        AttributeValue::ArrayBool(arr) => serde_json::json!(arr),
        AttributeValue::ArrayUuid(arr) => {
            serde_json::json!(arr.iter().map(|u| u.to_string()).collect::<Vec<_>>())
        }
        AttributeValue::ArrayDateTime(arr) => {
            serde_json::json!(arr.iter().map(|dt| dt.to_rfc3339()).collect::<Vec<_>>())
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum QueryError {
    #[error("filter error: {0}")]
    Filter(String),

    #[error("ranking error: {0}")]
    Ranking(String),

    #[error("internal error: {0}")]
    Internal(String),
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_docs() -> Vec<InMemoryDoc> {
        vec![
            InMemoryDoc {
                id: DocumentId::UInt(1),
                vector: Some(vec![1.0, 0.0, 0.0]),
                attributes: HashMap::from([
                    ("name".into(), AttributeValue::String("Alice".into())),
                    ("age".into(), AttributeValue::Int(30)),
                ]),
            },
            InMemoryDoc {
                id: DocumentId::UInt(2),
                vector: Some(vec![0.0, 1.0, 0.0]),
                attributes: HashMap::from([
                    ("name".into(), AttributeValue::String("Bob".into())),
                    ("age".into(), AttributeValue::Int(25)),
                ]),
            },
            InMemoryDoc {
                id: DocumentId::UInt(3),
                vector: Some(vec![0.0, 0.0, 1.0]),
                attributes: HashMap::from([
                    ("name".into(), AttributeValue::String("Charlie".into())),
                    ("age".into(), AttributeValue::Int(35)),
                ]),
            },
        ]
    }

    #[test]
    fn test_query_with_filter() {
        let docs = make_docs();
        let filter = serde_json::json!(["age", "Gt", 28]);

        let result =
            execute_query(&docs, None, Some(&filter), 10, None, None, None, None).unwrap();
        let rows = result.rows.unwrap();
        assert_eq!(rows.len(), 2); // Alice (30) and Charlie (35)
    }

    #[test]
    fn test_query_with_vector_search() {
        let docs = make_docs();
        let rank = serde_json::json!(["vector", "ANN", [0.9, 0.1, 0.0]]);

        let result =
            execute_query(&docs, Some(&rank), None, 2, None, None, None, None).unwrap();
        let rows = result.rows.unwrap();
        assert_eq!(rows.len(), 2);
        // Alice's vector [1,0,0] is closest to [0.9, 0.1, 0]
        assert_eq!(rows[0].id, DocumentId::UInt(1));
    }

    #[test]
    fn test_query_with_attribute_projection() {
        let docs = make_docs();
        let include = serde_json::json!(["name"]);

        let result =
            execute_query(&docs, None, None, 10, Some(&include), None, None, None).unwrap();
        let rows = result.rows.unwrap();
        assert!(rows[0].attributes.contains_key("name"));
        assert!(!rows[0].attributes.contains_key("age"));
    }

    #[test]
    fn test_aggregation_count_and_sum() {
        let docs = make_docs();
        let agg_json = serde_json::json!([
            {"type": "count"},
            {"type": "sum", "attribute": "age"}
        ]);
        let result =
            execute_query(&docs, None, None, 10, None, None, Some(&agg_json), None).unwrap();
        let aggs = result.aggregations.unwrap();
        assert_eq!(aggs["count"], serde_json::json!(3));
        assert_eq!(aggs["sum_age"], serde_json::json!(90.0)); // 30 + 25 + 35
    }

    #[test]
    fn test_aggregation_min_max() {
        let docs = make_docs();
        let agg_json = serde_json::json!([
            {"type": "min", "attribute": "age"},
            {"type": "max", "attribute": "age"}
        ]);
        let result =
            execute_query(&docs, None, None, 10, None, None, Some(&agg_json), None).unwrap();
        let aggs = result.aggregations.unwrap();
        assert_eq!(aggs["min_age"], serde_json::json!(25.0));
        assert_eq!(aggs["max_age"], serde_json::json!(35.0));
    }

    #[test]
    fn test_aggregation_distinct() {
        let docs = make_docs();
        let agg_json = serde_json::json!([{"type": "distinct", "attribute": "name"}]);
        let result =
            execute_query(&docs, None, None, 10, None, None, Some(&agg_json), None).unwrap();
        let aggs = result.aggregations.unwrap();
        let distinct = aggs["distinct_name"].as_array().unwrap();
        assert_eq!(distinct.len(), 3);
    }

    #[test]
    fn test_cursor_pagination() {
        let docs = make_docs();
        // Get first page of 2
        let result =
            execute_query(&docs, None, None, 2, None, None, None, None).unwrap();
        let rows = result.rows.unwrap();
        assert_eq!(rows.len(), 2);
        assert!(result.next_cursor.is_some());

        // Get second page using cursor
        let cursor = result.next_cursor.unwrap();
        let result2 =
            execute_query(&docs, None, None, 2, None, None, None, Some(&cursor)).unwrap();
        let rows2 = result2.rows.unwrap();
        assert_eq!(rows2.len(), 1); // Only 1 remaining doc
        assert!(result2.next_cursor.is_none());
    }

    #[test]
    fn test_cursor_encode_decode() {
        let data = CursorData {
            last_id: DocumentId::UInt(42),
            last_score: Some(0.95),
        };
        let encoded = encode_cursor(&data);
        let decoded = decode_cursor(&encoded).unwrap();
        assert_eq!(decoded.last_id, DocumentId::UInt(42));
        assert_eq!(decoded.last_score, Some(0.95));
    }
}
