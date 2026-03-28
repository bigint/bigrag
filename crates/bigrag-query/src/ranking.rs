
/// Parsed rank_by expression.
#[derive(Debug, Clone)]
pub enum RankBy {
    /// ANN vector search: ["vector", "ANN", [0.1, 0.2, ...]]
    Ann { vector: Vec<f32> },
    /// Exact kNN: ["vector", "kNN", [0.1, 0.2, ...]]
    Knn { vector: Vec<f32> },
    /// BM25 full-text: ["field", "BM25", "query"]
    Bm25 {
        field: String,
        query: String,
        last_as_prefix: bool,
    },
    /// Order by attribute: ["attr", "asc"|"desc"]
    OrderByAttribute {
        attribute: String,
        descending: bool,
    },
    /// Sum of clauses: ["Sum", [clause1, clause2, ...]]
    Sum(Vec<RankBy>),
    /// Max of clauses: ["Max", [clause1, clause2, ...]]
    Max(Vec<RankBy>),
    /// Product (weighted): ["Product", weight, clause]
    Product { weight: f64, clause: Box<RankBy> },
    /// Attribute value: ["Attribute", "attr_name"]
    Attribute(String),
    /// Saturate: maps score to [0, 1)
    Saturate {
        clause: Box<RankBy>,
        midpoint: f64,
        exponent: f64,
    },
    /// Decay: inverse of saturate
    Decay {
        clause: Box<RankBy>,
        midpoint: f64,
        exponent: f64,
    },
    /// Distance between attribute and origin
    Dist {
        clause: Box<RankBy>,
        origin: serde_json::Value,
    },
    /// Filter as rank: score 1 if match, else 0
    FilterAsRank(serde_json::Value),
}

/// Parse a rank_by expression from JSON.
pub fn parse_rank_by(value: &serde_json::Value) -> Result<RankBy, RankByError> {
    let arr = value
        .as_array()
        .ok_or_else(|| RankByError::InvalidFormat("rank_by must be an array".into()))?;

    if arr.is_empty() {
        return Err(RankByError::InvalidFormat("empty rank_by array".into()));
    }

    let first = arr[0].as_str().unwrap_or("");

    match first {
        "Sum" => {
            let clauses = arr
                .get(1)
                .and_then(|v| v.as_array())
                .ok_or_else(|| RankByError::InvalidFormat("Sum needs array of clauses".into()))?;
            let parsed: Result<Vec<RankBy>, _> = clauses.iter().map(parse_rank_by).collect();
            Ok(RankBy::Sum(parsed?))
        }
        "Max" => {
            if arr.len() == 2 {
                if let Some(clauses) = arr[1].as_array() {
                    let parsed: Result<Vec<RankBy>, _> = clauses.iter().map(parse_rank_by).collect();
                    return Ok(RankBy::Max(parsed?));
                }
            }
            // ["Max", 0, clause] form for clamping
            if arr.len() == 3 {
                let clause = parse_rank_by(&arr[2])?;
                return Ok(RankBy::Max(vec![clause]));
            }
            Err(RankByError::InvalidFormat("invalid Max format".into()))
        }
        "Product" => {
            if arr.len() != 3 {
                return Err(RankByError::InvalidFormat("Product needs weight and clause".into()));
            }
            let weight = arr[1]
                .as_f64()
                .ok_or_else(|| RankByError::InvalidFormat("Product weight must be a number".into()))?;
            let clause = parse_rank_by(&arr[2])?;
            Ok(RankBy::Product {
                weight,
                clause: Box::new(clause),
            })
        }
        "Attribute" => {
            let attr = arr
                .get(1)
                .and_then(|v| v.as_str())
                .ok_or_else(|| RankByError::InvalidFormat("Attribute needs name".into()))?;
            Ok(RankBy::Attribute(attr.to_string()))
        }
        "Saturate" => {
            if arr.len() != 3 {
                return Err(RankByError::InvalidFormat("Saturate needs clause and config".into()));
            }
            let clause = parse_rank_by(&arr[1])?;
            let config = &arr[2];
            let midpoint = config
                .get("midpoint")
                .and_then(|v| v.as_f64())
                .ok_or_else(|| RankByError::InvalidFormat("Saturate needs midpoint".into()))?;
            let exponent = config
                .get("exponent")
                .and_then(|v| v.as_f64())
                .unwrap_or(1.0);
            Ok(RankBy::Saturate {
                clause: Box::new(clause),
                midpoint,
                exponent,
            })
        }
        "Decay" => {
            if arr.len() != 3 {
                return Err(RankByError::InvalidFormat("Decay needs clause and config".into()));
            }
            let clause = parse_rank_by(&arr[1])?;
            let config = &arr[2];
            let midpoint = config
                .get("midpoint")
                .and_then(|v| v.as_f64())
                .ok_or_else(|| RankByError::InvalidFormat("Decay needs midpoint".into()))?;
            let exponent = config
                .get("exponent")
                .and_then(|v| v.as_f64())
                .unwrap_or(1.0);
            Ok(RankBy::Decay {
                clause: Box::new(clause),
                midpoint,
                exponent,
            })
        }
        "Dist" => {
            if arr.len() != 3 {
                return Err(RankByError::InvalidFormat("Dist needs clause and origin".into()));
            }
            let clause = parse_rank_by(&arr[1])?;
            let origin = arr[2].clone();
            Ok(RankBy::Dist {
                clause: Box::new(clause),
                origin,
            })
        }
        _ => {
            // Check for vector search: ["vector", "ANN"|"kNN", [...]]
            if arr.len() >= 3 {
                let op = arr[1].as_str().unwrap_or("");
                match op {
                    "ANN" => {
                        let vector = parse_vector(&arr[2])?;
                        return Ok(RankBy::Ann { vector });
                    }
                    "kNN" => {
                        let vector = parse_vector(&arr[2])?;
                        return Ok(RankBy::Knn { vector });
                    }
                    "BM25" => {
                        let query = arr[2]
                            .as_str()
                            .ok_or_else(|| RankByError::InvalidFormat("BM25 query must be string".into()))?
                            .to_string();
                        let last_as_prefix = arr
                            .get(3)
                            .and_then(|v| v.get("last_as_prefix"))
                            .and_then(|v| v.as_bool())
                            .unwrap_or(false);
                        return Ok(RankBy::Bm25 {
                            field: first.to_string(),
                            query,
                            last_as_prefix,
                        });
                    }
                    _ => {}
                }
            }

            // Order by attribute: ["attr", "asc"|"desc"]
            if arr.len() == 2 {
                let dir = arr[1].as_str().unwrap_or("");
                match dir {
                    "asc" => {
                        return Ok(RankBy::OrderByAttribute {
                            attribute: first.to_string(),
                            descending: false,
                        });
                    }
                    "desc" => {
                        return Ok(RankBy::OrderByAttribute {
                            attribute: first.to_string(),
                            descending: true,
                        });
                    }
                    _ => {}
                }
            }

            // Filter-as-rank
            Ok(RankBy::FilterAsRank(value.clone()))
        }
    }
}

fn parse_vector(value: &serde_json::Value) -> Result<Vec<f32>, RankByError> {
    value
        .as_array()
        .ok_or_else(|| RankByError::InvalidFormat("vector must be an array".into()))?
        .iter()
        .map(|v| {
            v.as_f64()
                .map(|f| f as f32)
                .ok_or_else(|| RankByError::InvalidFormat("vector element must be a number".into()))
        })
        .collect()
}

/// Compute the saturate function: x^exp / (x^exp + mid^exp).
pub fn saturate(x: f64, midpoint: f64, exponent: f64) -> f64 {
    let x = x.max(0.0);
    let x_pow = x.powf(exponent);
    let mid_pow = midpoint.powf(exponent);
    x_pow / (x_pow + mid_pow)
}

/// Compute the decay function: mid^exp / (x^exp + mid^exp).
pub fn decay(x: f64, midpoint: f64, exponent: f64) -> f64 {
    let x = x.max(0.0);
    let x_pow = x.powf(exponent);
    let mid_pow = midpoint.powf(exponent);
    mid_pow / (x_pow + mid_pow)
}

#[derive(Debug, thiserror::Error)]
pub enum RankByError {
    #[error("invalid format: {0}")]
    InvalidFormat(String),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_ann() {
        let json = serde_json::json!(["vector", "ANN", [0.1, 0.2, 0.3]]);
        match parse_rank_by(&json).unwrap() {
            RankBy::Ann { vector } => {
                assert_eq!(vector.len(), 3);
                assert!((vector[0] - 0.1).abs() < f32::EPSILON);
            }
            _ => panic!("expected Ann"),
        }
    }

    #[test]
    fn test_parse_bm25() {
        let json = serde_json::json!(["title", "BM25", "quick fox"]);
        match parse_rank_by(&json).unwrap() {
            RankBy::Bm25 { field, query, last_as_prefix } => {
                assert_eq!(field, "title");
                assert_eq!(query, "quick fox");
                assert!(!last_as_prefix);
            }
            _ => panic!("expected Bm25"),
        }
    }

    #[test]
    fn test_parse_order_by() {
        let json = serde_json::json!(["created_at", "desc"]);
        match parse_rank_by(&json).unwrap() {
            RankBy::OrderByAttribute { attribute, descending } => {
                assert_eq!(attribute, "created_at");
                assert!(descending);
            }
            _ => panic!("expected OrderByAttribute"),
        }
    }

    #[test]
    fn test_parse_sum() {
        let json = serde_json::json!(["Sum", [
            ["Product", 2.0, ["title", "BM25", "fox"]],
            ["content", "BM25", "fox"]
        ]]);
        match parse_rank_by(&json).unwrap() {
            RankBy::Sum(clauses) => assert_eq!(clauses.len(), 2),
            _ => panic!("expected Sum"),
        }
    }

    #[test]
    fn test_saturate_fn() {
        let s = saturate(50.0, 100.0, 1.0);
        assert!((s - 0.333).abs() < 0.01);

        let s = saturate(100.0, 100.0, 1.0);
        assert!((s - 0.5).abs() < f64::EPSILON);
    }

    #[test]
    fn test_decay_fn() {
        let d = decay(100.0, 100.0, 1.0);
        assert!((d - 0.5).abs() < f64::EPSILON);

        let d = decay(0.0, 100.0, 1.0);
        assert!((d - 1.0).abs() < f64::EPSILON);
    }
}
