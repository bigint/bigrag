use std::collections::HashSet;

use bigrag_common::types::AttributeValue;
use serde::{Deserialize, Serialize};

/// Filter expression AST.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Filter {
    And(AndFilter),
    Or(OrFilter),
    Not(NotFilter),
    Comparison(ComparisonFilter),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AndFilter {
    #[serde(rename = "And")]
    pub filters: Vec<Filter>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrFilter {
    #[serde(rename = "Or")]
    pub filters: Vec<Filter>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotFilter {
    #[serde(rename = "Not")]
    pub filter: Box<Filter>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComparisonFilter {
    pub attribute: String,
    pub operator: FilterOperator,
    pub value: serde_json::Value,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum FilterOperator {
    Eq,
    NotEq,
    Lt,
    Lte,
    Gt,
    Gte,
    In,
    NotIn,
    Contains,
    NotContains,
    ContainsAny,
    NotContainsAny,
    ContainsAll,
    Glob,
    NotGlob,
    IGlob,
    NotIGlob,
    Regex,
    ContainsAllTokens,
    ContainsAnyToken,
    ContainsTokenSequence,
    AnyLt,
    AnyLte,
    AnyGt,
    AnyGte,
}

/// Parse a filter expression from the turbopuffer JSON format.
/// Format: ["attr", "Op", value] or ["And", [...]] etc.
pub fn parse_filter(value: &serde_json::Value) -> Result<Filter, FilterError> {
    let arr = value
        .as_array()
        .ok_or_else(|| FilterError::InvalidFormat("filter must be an array".into()))?;

    if arr.is_empty() {
        return Err(FilterError::InvalidFormat("empty filter array".into()));
    }

    let first = arr[0]
        .as_str()
        .ok_or_else(|| FilterError::InvalidFormat("first element must be a string".into()))?;

    match first {
        "And" => {
            if arr.len() != 2 {
                return Err(FilterError::InvalidFormat("And requires exactly 2 elements".into()));
            }
            let sub_filters = arr[1]
                .as_array()
                .ok_or_else(|| FilterError::InvalidFormat("And value must be an array".into()))?;
            let filters: Result<Vec<Filter>, _> = sub_filters.iter().map(parse_filter).collect();
            Ok(Filter::And(AndFilter {
                filters: filters?,
            }))
        }
        "Or" => {
            if arr.len() != 2 {
                return Err(FilterError::InvalidFormat("Or requires exactly 2 elements".into()));
            }
            let sub_filters = arr[1]
                .as_array()
                .ok_or_else(|| FilterError::InvalidFormat("Or value must be an array".into()))?;
            let filters: Result<Vec<Filter>, _> = sub_filters.iter().map(parse_filter).collect();
            Ok(Filter::Or(OrFilter {
                filters: filters?,
            }))
        }
        "Not" => {
            if arr.len() != 2 {
                return Err(FilterError::InvalidFormat("Not requires exactly 2 elements".into()));
            }
            let inner = parse_filter(&arr[1])?;
            Ok(Filter::Not(NotFilter {
                filter: Box::new(inner),
            }))
        }
        _ => {
            // Comparison: ["attr", "Op", value]
            if arr.len() < 3 {
                return Err(FilterError::InvalidFormat(
                    "comparison filter needs at least 3 elements".into(),
                ));
            }
            let attribute = first.to_string();
            let op_str = arr[1]
                .as_str()
                .ok_or_else(|| FilterError::InvalidFormat("operator must be a string".into()))?;
            let operator = parse_operator(op_str)?;
            let value = arr[2].clone();

            Ok(Filter::Comparison(ComparisonFilter {
                attribute,
                operator,
                value,
            }))
        }
    }
}

fn parse_operator(s: &str) -> Result<FilterOperator, FilterError> {
    match s {
        "Eq" => Ok(FilterOperator::Eq),
        "NotEq" => Ok(FilterOperator::NotEq),
        "Lt" => Ok(FilterOperator::Lt),
        "Lte" => Ok(FilterOperator::Lte),
        "Gt" => Ok(FilterOperator::Gt),
        "Gte" => Ok(FilterOperator::Gte),
        "In" => Ok(FilterOperator::In),
        "NotIn" => Ok(FilterOperator::NotIn),
        "Contains" => Ok(FilterOperator::Contains),
        "NotContains" => Ok(FilterOperator::NotContains),
        "ContainsAny" => Ok(FilterOperator::ContainsAny),
        "NotContainsAny" => Ok(FilterOperator::NotContainsAny),
        "ContainsAll" => Ok(FilterOperator::ContainsAll),
        "Glob" => Ok(FilterOperator::Glob),
        "NotGlob" => Ok(FilterOperator::NotGlob),
        "IGlob" => Ok(FilterOperator::IGlob),
        "NotIGlob" => Ok(FilterOperator::NotIGlob),
        "Regex" => Ok(FilterOperator::Regex),
        "ContainsAllTokens" => Ok(FilterOperator::ContainsAllTokens),
        "ContainsAnyToken" => Ok(FilterOperator::ContainsAnyToken),
        "ContainsTokenSequence" => Ok(FilterOperator::ContainsTokenSequence),
        "AnyLt" => Ok(FilterOperator::AnyLt),
        "AnyLte" => Ok(FilterOperator::AnyLte),
        "AnyGt" => Ok(FilterOperator::AnyGt),
        "AnyGte" => Ok(FilterOperator::AnyGte),
        _ => Err(FilterError::UnknownOperator(s.to_string())),
    }
}

/// Evaluate a filter against a document's attributes.
pub fn evaluate_filter(
    filter: &Filter,
    attributes: &std::collections::HashMap<String, AttributeValue>,
) -> bool {
    match filter {
        Filter::And(and) => and.filters.iter().all(|f| evaluate_filter(f, attributes)),
        Filter::Or(or) => or.filters.iter().any(|f| evaluate_filter(f, attributes)),
        Filter::Not(not) => !evaluate_filter(&not.filter, attributes),
        Filter::Comparison(cmp) => evaluate_comparison(cmp, attributes),
    }
}

fn evaluate_comparison(
    cmp: &ComparisonFilter,
    attributes: &std::collections::HashMap<String, AttributeValue>,
) -> bool {
    let attr_val = attributes.get(&cmp.attribute);

    match cmp.operator {
        FilterOperator::Eq => {
            if cmp.value.is_null() {
                return attr_val.is_none() || matches!(attr_val, Some(AttributeValue::Null));
            }
            match attr_val {
                Some(val) => json_value_matches(val, &cmp.value),
                None => false,
            }
        }
        FilterOperator::NotEq => {
            if cmp.value.is_null() {
                return attr_val.is_some() && !matches!(attr_val, Some(AttributeValue::Null));
            }
            match attr_val {
                Some(val) => !json_value_matches(val, &cmp.value),
                None => true,
            }
        }
        FilterOperator::Lt => compare_scalar(attr_val, &cmp.value, |ord| ord == std::cmp::Ordering::Less),
        FilterOperator::Lte => compare_scalar(attr_val, &cmp.value, |ord| ord != std::cmp::Ordering::Greater),
        FilterOperator::Gt => compare_scalar(attr_val, &cmp.value, |ord| ord == std::cmp::Ordering::Greater),
        FilterOperator::Gte => compare_scalar(attr_val, &cmp.value, |ord| ord != std::cmp::Ordering::Less),
        FilterOperator::In => {
            if let Some(arr) = cmp.value.as_array() {
                match attr_val {
                    Some(val) => arr.iter().any(|v| json_value_matches(val, v)),
                    None => arr.iter().any(|v| v.is_null()),
                }
            } else {
                false
            }
        }
        FilterOperator::NotIn => {
            if let Some(arr) = cmp.value.as_array() {
                match attr_val {
                    Some(val) => !arr.iter().any(|v| json_value_matches(val, v)),
                    None => !arr.iter().any(|v| v.is_null()),
                }
            } else {
                true
            }
        }
        FilterOperator::Contains => {
            match attr_val {
                Some(AttributeValue::String(s)) => {
                    if let Some(needle) = cmp.value.as_str() {
                        s.contains(needle)
                    } else {
                        false
                    }
                }
                Some(AttributeValue::ArrayString(arr)) => {
                    if let Some(s) = cmp.value.as_str() {
                        arr.contains(&s.to_string())
                    } else {
                        false
                    }
                }
                Some(AttributeValue::ArrayInt(arr)) => {
                    if let Some(n) = cmp.value.as_i64() {
                        arr.contains(&n)
                    } else {
                        false
                    }
                }
                _ => false,
            }
        }
        FilterOperator::NotContains => {
            !evaluate_comparison(
                &ComparisonFilter {
                    attribute: cmp.attribute.clone(),
                    operator: FilterOperator::Contains,
                    value: cmp.value.clone(),
                },
                attributes,
            )
        }
        FilterOperator::ContainsAny => {
            if let Some(query_arr) = cmp.value.as_array() {
                match attr_val {
                    Some(AttributeValue::ArrayString(arr)) => query_arr.iter().any(|v| {
                        v.as_str()
                            .map(|s| arr.contains(&s.to_string()))
                            .unwrap_or(false)
                    }),
                    Some(AttributeValue::ArrayInt(arr)) => query_arr
                        .iter()
                        .any(|v| v.as_i64().map(|n| arr.contains(&n)).unwrap_or(false)),
                    Some(AttributeValue::ArrayUInt(arr)) => query_arr
                        .iter()
                        .any(|v| v.as_u64().map(|n| arr.contains(&n)).unwrap_or(false)),
                    _ => false,
                }
            } else {
                false
            }
        }
        FilterOperator::NotContainsAny => {
            !evaluate_comparison(
                &ComparisonFilter {
                    attribute: cmp.attribute.clone(),
                    operator: FilterOperator::ContainsAny,
                    value: cmp.value.clone(),
                },
                attributes,
            )
        }
        FilterOperator::ContainsAll => {
            if let Some(query_arr) = cmp.value.as_array() {
                match attr_val {
                    Some(AttributeValue::ArrayString(arr)) => query_arr.iter().all(|v| {
                        v.as_str()
                            .map(|s| arr.contains(&s.to_string()))
                            .unwrap_or(false)
                    }),
                    Some(AttributeValue::ArrayInt(arr)) => query_arr
                        .iter()
                        .all(|v| v.as_i64().map(|n| arr.contains(&n)).unwrap_or(false)),
                    Some(AttributeValue::ArrayUInt(arr)) => query_arr
                        .iter()
                        .all(|v| v.as_u64().map(|n| arr.contains(&n)).unwrap_or(false)),
                    _ => false,
                }
            } else {
                false
            }
        }
        FilterOperator::Glob => match (attr_val, cmp.value.as_str()) {
            (Some(AttributeValue::String(s)), Some(pattern)) => globset::Glob::new(pattern)
                .ok()
                .map(|g| g.compile_matcher().is_match(s))
                .unwrap_or(false),
            _ => false,
        },
        FilterOperator::NotGlob => match (attr_val, cmp.value.as_str()) {
            (Some(AttributeValue::String(s)), Some(pattern)) => globset::Glob::new(pattern)
                .ok()
                .map(|g| !g.compile_matcher().is_match(s))
                .unwrap_or(false),
            _ => false,
        },
        FilterOperator::IGlob => match (attr_val, cmp.value.as_str()) {
            (Some(AttributeValue::String(s)), Some(pattern)) => {
                globset::Glob::new(&pattern.to_lowercase())
                    .ok()
                    .map(|g| g.compile_matcher().is_match(&s.to_lowercase()))
                    .unwrap_or(false)
            }
            _ => false,
        },
        FilterOperator::NotIGlob => match (attr_val, cmp.value.as_str()) {
            (Some(AttributeValue::String(s)), Some(pattern)) => {
                globset::Glob::new(&pattern.to_lowercase())
                    .ok()
                    .map(|g| !g.compile_matcher().is_match(&s.to_lowercase()))
                    .unwrap_or(false)
            }
            _ => false,
        },
        FilterOperator::Regex => match (attr_val, cmp.value.as_str()) {
            (Some(AttributeValue::String(s)), Some(pattern)) => regex::Regex::new(pattern)
                .map(|re| re.is_match(s))
                .unwrap_or(false),
            _ => false,
        },
        FilterOperator::ContainsAllTokens => match (attr_val, cmp.value.as_str()) {
            (Some(AttributeValue::String(s)), Some(query)) => {
                let attr_tokens: HashSet<String> = tokenize(s).into_iter().collect();
                let query_tokens = tokenize(query);
                query_tokens.iter().all(|t| attr_tokens.contains(t))
            }
            _ => false,
        },
        FilterOperator::ContainsAnyToken => match (attr_val, cmp.value.as_str()) {
            (Some(AttributeValue::String(s)), Some(query)) => {
                let attr_tokens: HashSet<String> = tokenize(s).into_iter().collect();
                let query_tokens = tokenize(query);
                query_tokens.iter().any(|t| attr_tokens.contains(t))
            }
            _ => false,
        },
        FilterOperator::ContainsTokenSequence => match (attr_val, cmp.value.as_str()) {
            (Some(AttributeValue::String(s)), Some(query)) => {
                let attr_tokens = tokenize(s);
                let query_tokens = tokenize(query);
                if query_tokens.is_empty() {
                    return true;
                }
                attr_tokens
                    .windows(query_tokens.len())
                    .any(|w| w == query_tokens.as_slice())
            }
            _ => false,
        },
        FilterOperator::AnyLt => match attr_val {
            Some(AttributeValue::ArrayInt(arr)) => {
                if let Some(n) = cmp.value.as_i64() {
                    arr.iter().any(|v| *v < n)
                } else {
                    false
                }
            }
            Some(AttributeValue::ArrayUInt(arr)) => {
                if let Some(n) = cmp.value.as_u64() {
                    arr.iter().any(|v| *v < n)
                } else {
                    false
                }
            }
            Some(AttributeValue::ArrayFloat(arr)) => {
                if let Some(n) = cmp.value.as_f64() {
                    arr.iter().any(|v| *v < n)
                } else {
                    false
                }
            }
            _ => false,
        },
        FilterOperator::AnyLte => match attr_val {
            Some(AttributeValue::ArrayInt(arr)) => {
                if let Some(n) = cmp.value.as_i64() {
                    arr.iter().any(|v| *v <= n)
                } else {
                    false
                }
            }
            Some(AttributeValue::ArrayUInt(arr)) => {
                if let Some(n) = cmp.value.as_u64() {
                    arr.iter().any(|v| *v <= n)
                } else {
                    false
                }
            }
            Some(AttributeValue::ArrayFloat(arr)) => {
                if let Some(n) = cmp.value.as_f64() {
                    arr.iter().any(|v| *v <= n)
                } else {
                    false
                }
            }
            _ => false,
        },
        FilterOperator::AnyGt => match attr_val {
            Some(AttributeValue::ArrayInt(arr)) => {
                if let Some(n) = cmp.value.as_i64() {
                    arr.iter().any(|v| *v > n)
                } else {
                    false
                }
            }
            Some(AttributeValue::ArrayUInt(arr)) => {
                if let Some(n) = cmp.value.as_u64() {
                    arr.iter().any(|v| *v > n)
                } else {
                    false
                }
            }
            Some(AttributeValue::ArrayFloat(arr)) => {
                if let Some(n) = cmp.value.as_f64() {
                    arr.iter().any(|v| *v > n)
                } else {
                    false
                }
            }
            _ => false,
        },
        FilterOperator::AnyGte => match attr_val {
            Some(AttributeValue::ArrayInt(arr)) => {
                if let Some(n) = cmp.value.as_i64() {
                    arr.iter().any(|v| *v >= n)
                } else {
                    false
                }
            }
            Some(AttributeValue::ArrayUInt(arr)) => {
                if let Some(n) = cmp.value.as_u64() {
                    arr.iter().any(|v| *v >= n)
                } else {
                    false
                }
            }
            Some(AttributeValue::ArrayFloat(arr)) => {
                if let Some(n) = cmp.value.as_f64() {
                    arr.iter().any(|v| *v >= n)
                } else {
                    false
                }
            }
            _ => false,
        },
    }
}

fn json_value_matches(attr: &AttributeValue, json: &serde_json::Value) -> bool {
    match (attr, json) {
        (AttributeValue::String(a), serde_json::Value::String(b)) => a == b,
        (AttributeValue::Int(a), serde_json::Value::Number(b)) => b.as_i64() == Some(*a),
        (AttributeValue::UInt(a), serde_json::Value::Number(b)) => b.as_u64() == Some(*a),
        (AttributeValue::Float(a), serde_json::Value::Number(b)) => {
            b.as_f64().map(|f| (f - a).abs() < f64::EPSILON) == Some(true)
        }
        (AttributeValue::Bool(a), serde_json::Value::Bool(b)) => a == b,
        (AttributeValue::Null, serde_json::Value::Null) => true,
        _ => false,
    }
}

fn compare_scalar(
    attr_val: Option<&AttributeValue>,
    json: &serde_json::Value,
    pred: impl Fn(std::cmp::Ordering) -> bool,
) -> bool {
    match (attr_val, json) {
        (Some(AttributeValue::Int(a)), serde_json::Value::Number(b)) => {
            if let Some(b) = b.as_i64() {
                pred(a.cmp(&b))
            } else {
                false
            }
        }
        (Some(AttributeValue::UInt(a)), serde_json::Value::Number(b)) => {
            if let Some(b) = b.as_u64() {
                pred(a.cmp(&b))
            } else {
                false
            }
        }
        (Some(AttributeValue::Float(a)), serde_json::Value::Number(b)) => {
            if let Some(b) = b.as_f64() {
                pred(a.partial_cmp(&b).unwrap_or(std::cmp::Ordering::Equal))
            } else {
                false
            }
        }
        (Some(AttributeValue::String(a)), serde_json::Value::String(b)) => {
            pred(a.as_str().cmp(b.as_str()))
        }
        _ => false,
    }
}

/// Simple whitespace tokenizer that lowercases tokens.
fn tokenize(text: &str) -> Vec<String> {
    text.split_whitespace()
        .map(|t| t.to_lowercase())
        .filter(|t| !t.is_empty())
        .collect()
}

#[derive(Debug, thiserror::Error)]
pub enum FilterError {
    #[error("invalid filter format: {0}")]
    InvalidFormat(String),

    #[error("unknown operator: {0}")]
    UnknownOperator(String),
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[test]
    fn test_parse_eq_filter() {
        let json = serde_json::json!(["color", "Eq", "red"]);
        let filter = parse_filter(&json).unwrap();
        match filter {
            Filter::Comparison(c) => {
                assert_eq!(c.attribute, "color");
                assert_eq!(c.operator, FilterOperator::Eq);
            }
            _ => panic!("expected comparison"),
        }
    }

    #[test]
    fn test_parse_and_filter() {
        let json = serde_json::json!(["And", [["a", "Eq", 1], ["b", "Gt", 2]]]);
        let filter = parse_filter(&json).unwrap();
        match filter {
            Filter::And(and) => assert_eq!(and.filters.len(), 2),
            _ => panic!("expected And"),
        }
    }

    #[test]
    fn test_evaluate_eq() {
        let json = serde_json::json!(["color", "Eq", "red"]);
        let filter = parse_filter(&json).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("color".into(), AttributeValue::String("red".into()));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("color".into(), AttributeValue::String("blue".into()));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_null_eq() {
        let json = serde_json::json!(["missing", "Eq", null]);
        let filter = parse_filter(&json).unwrap();

        let attrs = HashMap::new();
        assert!(evaluate_filter(&filter, &attrs)); // Missing = null match
    }

    #[test]
    fn test_evaluate_gt() {
        let json = serde_json::json!(["score", "Gt", 50]);
        let filter = parse_filter(&json).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("score".into(), AttributeValue::Int(75));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("score".into(), AttributeValue::Int(25));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_in() {
        let json = serde_json::json!(["status", "In", ["active", "pending"]]);
        let filter = parse_filter(&json).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("status".into(), AttributeValue::String("active".into()));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("status".into(), AttributeValue::String("deleted".into()));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_and() {
        let json = serde_json::json!(["And", [["age", "Gte", 18], ["age", "Lt", 65]]]);
        let filter = parse_filter(&json).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("age".into(), AttributeValue::Int(30));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("age".into(), AttributeValue::Int(10));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_not() {
        let json = serde_json::json!(["Not", ["deleted", "Eq", true]]);
        let filter = parse_filter(&json).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("deleted".into(), AttributeValue::Bool(false));
        assert!(evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_contains() {
        let json = serde_json::json!(["tags", "Contains", "rust"]);
        let filter = parse_filter(&json).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["rust".into(), "search".into()]),
        );
        assert!(evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_glob() {
        let filter = parse_filter(&serde_json::json!(["path", "Glob", "*.rs"])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("path".into(), AttributeValue::String("filter.rs".into()));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("path".into(), AttributeValue::String("filter.py".into()));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_not_glob() {
        let filter = parse_filter(&serde_json::json!(["path", "NotGlob", "*.rs"])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("path".into(), AttributeValue::String("filter.py".into()));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("path".into(), AttributeValue::String("filter.rs".into()));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_iglob() {
        let filter = parse_filter(&serde_json::json!(["name", "IGlob", "*.TXT"])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("name".into(), AttributeValue::String("readme.txt".into()));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("name".into(), AttributeValue::String("README.TXT".into()));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("name".into(), AttributeValue::String("readme.md".into()));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_not_iglob() {
        let filter = parse_filter(&serde_json::json!(["name", "NotIGlob", "*.TXT"])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("name".into(), AttributeValue::String("readme.md".into()));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("name".into(), AttributeValue::String("readme.txt".into()));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_regex() {
        let filter =
            parse_filter(&serde_json::json!(["email", "Regex", r"^\w+@\w+\.\w+$"])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "email".into(),
            AttributeValue::String("user@example.com".into()),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "email".into(),
            AttributeValue::String("not-an-email".into()),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_contains_all_tokens() {
        let filter = parse_filter(&serde_json::json!([
            "text",
            "ContainsAllTokens",
            "hello world"
        ]))
        .unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "text".into(),
            AttributeValue::String("Hello World foo bar".into()),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "text".into(),
            AttributeValue::String("Hello foo bar".into()),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_contains_any_token() {
        let filter =
            parse_filter(&serde_json::json!(["text", "ContainsAnyToken", "rust python"]))
                .unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "text".into(),
            AttributeValue::String("I love Rust programming".into()),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "text".into(),
            AttributeValue::String("I love Java programming".into()),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_contains_token_sequence() {
        let filter = parse_filter(&serde_json::json!([
            "text",
            "ContainsTokenSequence",
            "hello world"
        ]))
        .unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "text".into(),
            AttributeValue::String("say Hello World now".into()),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "text".into(),
            AttributeValue::String("world hello".into()),
        );
        assert!(!evaluate_filter(&filter, &attrs));

        // Empty query matches everything
        let empty_filter =
            parse_filter(&serde_json::json!(["text", "ContainsTokenSequence", ""])).unwrap();
        attrs.insert("text".into(), AttributeValue::String("anything".into()));
        assert!(evaluate_filter(&empty_filter, &attrs));
    }

    #[test]
    fn test_evaluate_any_lt() {
        let filter = parse_filter(&serde_json::json!(["scores", "AnyLt", 50])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("scores".into(), AttributeValue::ArrayInt(vec![60, 30, 80]));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("scores".into(), AttributeValue::ArrayInt(vec![60, 70, 80]));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_any_lte() {
        let filter = parse_filter(&serde_json::json!(["scores", "AnyLte", 50])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("scores".into(), AttributeValue::ArrayInt(vec![60, 50, 80]));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("scores".into(), AttributeValue::ArrayInt(vec![60, 70, 80]));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_any_gt() {
        let filter = parse_filter(&serde_json::json!(["scores", "AnyGt", 50])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("scores".into(), AttributeValue::ArrayInt(vec![10, 20, 60]));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("scores".into(), AttributeValue::ArrayInt(vec![10, 20, 30]));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_any_gte() {
        let filter = parse_filter(&serde_json::json!(["scores", "AnyGte", 50])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("scores".into(), AttributeValue::ArrayInt(vec![10, 50, 30]));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("scores".into(), AttributeValue::ArrayInt(vec![10, 20, 30]));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_any_lt_float() {
        let filter = parse_filter(&serde_json::json!(["values", "AnyLt", 2.5])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "values".into(),
            AttributeValue::ArrayFloat(vec![1.0, 3.0, 5.0]),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "values".into(),
            AttributeValue::ArrayFloat(vec![3.0, 4.0, 5.0]),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_contains_any() {
        let filter =
            parse_filter(&serde_json::json!(["tags", "ContainsAny", ["rust", "go"]])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["rust".into(), "search".into()]),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["python".into(), "ml".into()]),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_not_contains_any() {
        let filter =
            parse_filter(&serde_json::json!(["tags", "NotContainsAny", ["rust", "go"]])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["python".into(), "ml".into()]),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["rust".into(), "search".into()]),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_contains_all() {
        let filter =
            parse_filter(&serde_json::json!(["tags", "ContainsAll", ["rust", "search"]])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["rust".into(), "search".into(), "fast".into()]),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["rust".into(), "fast".into()]),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_contains_all_int() {
        let filter =
            parse_filter(&serde_json::json!(["ids", "ContainsAll", [1, 2]])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("ids".into(), AttributeValue::ArrayInt(vec![1, 2, 3]));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("ids".into(), AttributeValue::ArrayInt(vec![1, 3, 4]));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_not_contains() {
        let filter =
            parse_filter(&serde_json::json!(["tags", "NotContains", "rust"])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["python".into(), "ml".into()]),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["rust".into(), "search".into()]),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_not_contains_string() {
        let filter =
            parse_filter(&serde_json::json!(["text", "NotContains", "error"])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "text".into(),
            AttributeValue::String("all good here".into()),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "text".into(),
            AttributeValue::String("found an error".into()),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_tokenize() {
        assert_eq!(tokenize("Hello World"), vec!["hello", "world"]);
        assert_eq!(tokenize("  spaced  out  "), vec!["spaced", "out"]);
        assert!(tokenize("").is_empty());
        assert!(tokenize("   ").is_empty());
    }

    #[test]
    fn test_evaluate_contains_any_int() {
        let filter =
            parse_filter(&serde_json::json!(["ids", "ContainsAny", [1, 5]])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert("ids".into(), AttributeValue::ArrayInt(vec![1, 2, 3]));
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert("ids".into(), AttributeValue::ArrayInt(vec![4, 6, 7]));
        assert!(!evaluate_filter(&filter, &attrs));
    }

    #[test]
    fn test_evaluate_any_gte_float() {
        let filter = parse_filter(&serde_json::json!(["values", "AnyGte", 5.0])).unwrap();

        let mut attrs = HashMap::new();
        attrs.insert(
            "values".into(),
            AttributeValue::ArrayFloat(vec![1.0, 5.0, 3.0]),
        );
        assert!(evaluate_filter(&filter, &attrs));

        attrs.insert(
            "values".into(),
            AttributeValue::ArrayFloat(vec![1.0, 2.0, 3.0]),
        );
        assert!(!evaluate_filter(&filter, &attrs));
    }
}
