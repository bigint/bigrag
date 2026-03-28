use bigrag_common::types::{AttributeValue, BillingInfo, DocumentId, PerformanceInfo};
use std::collections::HashMap;

use crate::filter::{evaluate_filter, parse_filter, Filter};
use crate::ranking::{parse_rank_by, RankBy};

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
/// This is the core query executor that handles filtering, ranking, and projection.
pub fn execute_query(
    docs: &[InMemoryDoc],
    rank_by: Option<&serde_json::Value>,
    filters: Option<&serde_json::Value>,
    top_k: usize,
    include_attributes: Option<&serde_json::Value>,
    exclude_attributes: Option<&[String]>,
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
        scored.truncate(top_k);
        scored
    } else {
        filtered
            .into_iter()
            .take(top_k)
            .map(|d| (d, 0.0))
            .collect()
    };

    // Project attributes
    let rows: Vec<QueryResultRow> = ranked
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
        results: None,
        aggregations: None,
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

        let result = execute_query(&docs, None, Some(&filter), 10, None, None).unwrap();
        let rows = result.rows.unwrap();
        assert_eq!(rows.len(), 2); // Alice (30) and Charlie (35)
    }

    #[test]
    fn test_query_with_vector_search() {
        let docs = make_docs();
        let rank = serde_json::json!(["vector", "ANN", [0.9, 0.1, 0.0]]);

        let result = execute_query(&docs, Some(&rank), None, 2, None, None).unwrap();
        let rows = result.rows.unwrap();
        assert_eq!(rows.len(), 2);
        // Alice's vector [1,0,0] is closest to [0.9, 0.1, 0]
        assert_eq!(rows[0].id, DocumentId::UInt(1));
    }

    #[test]
    fn test_query_with_attribute_projection() {
        let docs = make_docs();
        let include = serde_json::json!(["name"]);

        let result = execute_query(&docs, None, None, 10, Some(&include), None).unwrap();
        let rows = result.rows.unwrap();
        assert!(rows[0].attributes.contains_key("name"));
        assert!(!rows[0].attributes.contains_key("age"));
    }
}
