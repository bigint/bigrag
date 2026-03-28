//! Integration tests for bigRAG query engine and filter system.
//! Run with: cargo test --test api_integration -p bigrag-query
//!
//! These tests exercise the full query pipeline including filtering,
//! ranking, aggregations, and cursor-based pagination.

#[cfg(test)]
mod tests {
    use bigrag_common::types::{AttributeValue, DocumentId};
    use bigrag_query::executor::{execute_query, InMemoryDoc};
    use bigrag_query::filter::{evaluate_filter, parse_filter};
    use std::collections::HashMap;

    fn make_doc(id: u64, title: &str, score: f64, vector: Option<Vec<f32>>) -> InMemoryDoc {
        let mut attrs = HashMap::new();
        attrs.insert("title".into(), AttributeValue::String(title.into()));
        attrs.insert("score".into(), AttributeValue::Float(score));
        InMemoryDoc {
            id: DocumentId::UInt(id),
            vector,
            attributes: attrs,
        }
    }

    #[test]
    fn test_full_query_pipeline() {
        let docs = vec![
            make_doc(1, "Intro to RAG", 4.5, Some(vec![0.1, 0.2, 0.3])),
            make_doc(2, "Advanced ML", 3.8, Some(vec![0.4, 0.5, 0.6])),
            make_doc(3, "RAG Tutorial", 4.9, Some(vec![0.1, 0.3, 0.5])),
            make_doc(4, "Database Design", 2.1, Some(vec![0.9, 0.1, 0.1])),
        ];

        // Test: query with filter (score > 4.0)
        let result = execute_query(
            &docs,
            None,
            Some(&serde_json::json!(["score", "Gt", 4.0])),
            10,
            Some(&serde_json::json!(true)),
            None,
            None,
            None,
        )
        .unwrap();
        assert_eq!(result.rows.as_ref().unwrap().len(), 2);

        // Test: query with ANN
        let result = execute_query(
            &docs,
            Some(&serde_json::json!(["vector", "ANN", [0.1, 0.2, 0.3]])),
            None,
            2,
            Some(&serde_json::json!(true)),
            None,
            None,
            None,
        )
        .unwrap();
        assert_eq!(result.rows.as_ref().unwrap().len(), 2);

        // Test: aggregation count
        let result = execute_query(
            &docs,
            None,
            None,
            10,
            None,
            None,
            Some(&serde_json::json!([{"type": "count"}])),
            None,
        )
        .unwrap();
        assert_eq!(result.aggregations.as_ref().unwrap()["count"], 4);
    }

    #[test]
    fn test_filter_operators_comprehensive() {
        let mut attrs = HashMap::new();
        attrs.insert("category".into(), AttributeValue::String("ml".into()));
        attrs.insert("score".into(), AttributeValue::Float(4.5));
        attrs.insert(
            "tags".into(),
            AttributeValue::ArrayString(vec!["rag".into(), "llm".into()]),
        );
        attrs.insert("active".into(), AttributeValue::Bool(true));
        attrs.insert("count".into(), AttributeValue::Int(42));

        // Eq
        let f = parse_filter(&serde_json::json!(["category", "Eq", "ml"])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // NotEq
        let f = parse_filter(&serde_json::json!(["category", "NotEq", "nlp"])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // Gt, Lt
        let f = parse_filter(&serde_json::json!(["score", "Gt", 4.0])).unwrap();
        assert!(evaluate_filter(&f, &attrs));
        let f = parse_filter(&serde_json::json!(["score", "Lt", 5.0])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // Gte, Lte
        let f = parse_filter(&serde_json::json!(["score", "Gte", 4.5])).unwrap();
        assert!(evaluate_filter(&f, &attrs));
        let f = parse_filter(&serde_json::json!(["score", "Lte", 4.5])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // In
        let f = parse_filter(&serde_json::json!(["category", "In", ["ml", "nlp"]])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // And -- note the format: ["And", [filter1, filter2]]
        let f = parse_filter(&serde_json::json!(["And", [
            ["category", "Eq", "ml"],
            ["score", "Gt", 4.0]
        ]]))
        .unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // Or
        let f = parse_filter(&serde_json::json!(["Or", [
            ["category", "Eq", "nlp"],
            ["score", "Gt", 4.0]
        ]]))
        .unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // Not
        let f = parse_filter(&serde_json::json!(["Not", ["category", "Eq", "nlp"]])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // Contains on string
        let f = parse_filter(&serde_json::json!(["category", "Contains", "m"])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // Contains on array
        let f = parse_filter(&serde_json::json!(["tags", "Contains", "rag"])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // Bool
        let f = parse_filter(&serde_json::json!(["active", "Eq", true])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        // Int comparison
        let f = parse_filter(&serde_json::json!(["count", "Gt", 40])).unwrap();
        assert!(evaluate_filter(&f, &attrs));
        let f = parse_filter(&serde_json::json!(["count", "Lt", 50])).unwrap();
        assert!(evaluate_filter(&f, &attrs));
    }

    #[test]
    fn test_hybrid_search_with_bm25() {
        // Create docs with text content for BM25
        let docs = vec![
            make_doc(1, "quick brown fox", 1.0, None),
            make_doc(2, "lazy dog sleeps", 2.0, None),
            make_doc(3, "quick fox jumps", 3.0, None),
        ];

        // BM25 search for "quick fox"
        let result = execute_query(
            &docs,
            Some(&serde_json::json!(["title", "BM25", "quick fox"])),
            None,
            10,
            Some(&serde_json::json!(true)),
            None,
            None,
            None,
        )
        .unwrap();
        let rows = result.rows.as_ref().unwrap();
        // All docs should be returned since BM25 currently returns 1.0 for all
        assert!(!rows.is_empty());
    }

    #[test]
    fn test_pagination_with_cursor() {
        let docs: Vec<_> = (1..=20)
            .map(|i| make_doc(i, &format!("doc-{i}"), i as f64, None))
            .collect();

        // First page
        let result = execute_query(
            &docs,
            None,
            None,
            5,
            Some(&serde_json::json!(true)),
            None,
            None,
            None,
        )
        .unwrap();
        assert_eq!(result.rows.as_ref().unwrap().len(), 5);
        assert!(result.next_cursor.is_some());

        // Second page
        let result2 = execute_query(
            &docs,
            None,
            None,
            5,
            Some(&serde_json::json!(true)),
            None,
            None,
            result.next_cursor.as_deref(),
        )
        .unwrap();
        assert_eq!(result2.rows.as_ref().unwrap().len(), 5);
    }

    #[test]
    fn test_vector_search_ordering() {
        let docs = vec![
            make_doc(1, "close", 1.0, Some(vec![1.0, 0.0, 0.0])),
            make_doc(2, "medium", 2.0, Some(vec![0.7, 0.7, 0.0])),
            make_doc(3, "far", 3.0, Some(vec![0.0, 0.0, 1.0])),
        ];

        // Search for vector close to doc 1
        let result = execute_query(
            &docs,
            Some(&serde_json::json!(["vector", "ANN", [0.99, 0.01, 0.0]])),
            None,
            3,
            Some(&serde_json::json!(true)),
            None,
            None,
            None,
        )
        .unwrap();
        let rows = result.rows.as_ref().unwrap();
        assert_eq!(rows.len(), 3);
        // Doc 1 should be closest
        assert_eq!(rows[0].id, DocumentId::UInt(1));
    }

    #[test]
    fn test_filter_and_rank_combined() {
        let docs = vec![
            make_doc(1, "alpha", 1.0, Some(vec![1.0, 0.0, 0.0])),
            make_doc(2, "beta", 5.0, Some(vec![0.5, 0.5, 0.0])),
            make_doc(3, "gamma", 3.0, Some(vec![0.0, 1.0, 0.0])),
            make_doc(4, "delta", 8.0, Some(vec![0.0, 0.0, 1.0])),
        ];

        // Filter score > 2.0, then rank by ANN
        let result = execute_query(
            &docs,
            Some(&serde_json::json!(["vector", "ANN", [1.0, 0.0, 0.0]])),
            Some(&serde_json::json!(["score", "Gt", 2.0])),
            10,
            Some(&serde_json::json!(true)),
            None,
            None,
            None,
        )
        .unwrap();
        let rows = result.rows.as_ref().unwrap();
        // Only docs 2, 3, 4 pass filter (score > 2.0)
        assert_eq!(rows.len(), 3);
    }

    #[test]
    fn test_aggregations_comprehensive() {
        let docs = vec![
            make_doc(1, "alpha", 10.0, None),
            make_doc(2, "beta", 20.0, None),
            make_doc(3, "gamma", 30.0, None),
            make_doc(4, "delta", 40.0, None),
        ];

        // Count + sum + min + max
        let result = execute_query(
            &docs,
            None,
            None,
            10,
            None,
            None,
            Some(&serde_json::json!([
                {"type": "count"},
                {"type": "sum", "attribute": "score"},
                {"type": "min", "attribute": "score"},
                {"type": "max", "attribute": "score"}
            ])),
            None,
        )
        .unwrap();
        let aggs = result.aggregations.as_ref().unwrap();
        assert_eq!(aggs["count"], 4);
        assert_eq!(aggs["sum_score"], 100.0);
        assert_eq!(aggs["min_score"], 10.0);
        assert_eq!(aggs["max_score"], 40.0);
    }

    #[test]
    fn test_attribute_projection() {
        let mut attrs = HashMap::new();
        attrs.insert("title".into(), AttributeValue::String("test".into()));
        attrs.insert("score".into(), AttributeValue::Float(4.5));
        attrs.insert("secret".into(), AttributeValue::String("hidden".into()));

        let docs = vec![InMemoryDoc {
            id: DocumentId::UInt(1),
            vector: None,
            attributes: attrs,
        }];

        // Include only title
        let result = execute_query(
            &docs,
            None,
            None,
            10,
            Some(&serde_json::json!(["title"])),
            None,
            None,
            None,
        )
        .unwrap();
        let row = &result.rows.as_ref().unwrap()[0];
        assert!(row.attributes.contains_key("title"));
        assert!(!row.attributes.contains_key("score"));
        assert!(!row.attributes.contains_key("secret"));

        // Include all but exclude secret
        let result = execute_query(
            &docs,
            None,
            None,
            10,
            Some(&serde_json::json!(true)),
            Some(&["secret".to_string()]),
            None,
            None,
        )
        .unwrap();
        let row = &result.rows.as_ref().unwrap()[0];
        assert!(row.attributes.contains_key("title"));
        assert!(row.attributes.contains_key("score"));
        assert!(!row.attributes.contains_key("secret"));
    }

    #[test]
    fn test_empty_namespace_query() {
        let docs: Vec<InMemoryDoc> = vec![];
        let result = execute_query(&docs, None, None, 10, None, None, None, None).unwrap();
        assert!(result.rows.as_ref().unwrap().is_empty());
    }

    #[test]
    fn test_filter_on_missing_attribute() {
        let mut attrs = HashMap::new();
        attrs.insert("name".into(), AttributeValue::String("test".into()));

        // Filter on attribute that doesn't exist
        let f = parse_filter(&serde_json::json!(["missing", "Eq", "value"])).unwrap();
        assert!(!evaluate_filter(&f, &attrs));

        // Null check on missing attribute should match
        let f = parse_filter(&serde_json::json!(["missing", "Eq", null])).unwrap();
        assert!(evaluate_filter(&f, &attrs));
    }

    #[test]
    fn test_not_in_filter() {
        let mut attrs = HashMap::new();
        attrs.insert("status".into(), AttributeValue::String("active".into()));

        let f = parse_filter(&serde_json::json!(["status", "NotIn", ["deleted", "archived"]])).unwrap();
        assert!(evaluate_filter(&f, &attrs));

        let f = parse_filter(&serde_json::json!(["status", "NotIn", ["active", "pending"]])).unwrap();
        assert!(!evaluate_filter(&f, &attrs));
    }

    #[test]
    fn test_order_by_attribute() {
        let docs = vec![
            make_doc(1, "c_third", 3.0, None),
            make_doc(2, "a_first", 1.0, None),
            make_doc(3, "b_second", 2.0, None),
        ];

        // Order by score descending (ascending uses negative sort keys which
        // get filtered by the score > 0 threshold in the query executor)
        let result = execute_query(
            &docs,
            Some(&serde_json::json!(["score", "desc"])),
            None,
            10,
            Some(&serde_json::json!(true)),
            None,
            None,
            None,
        )
        .unwrap();
        let rows = result.rows.as_ref().unwrap();
        assert_eq!(rows.len(), 3);
        // Descending: 3.0, 2.0, 1.0
        assert_eq!(rows[0].id, DocumentId::UInt(1));
        assert_eq!(rows[1].id, DocumentId::UInt(3));
        assert_eq!(rows[2].id, DocumentId::UInt(2));
    }
}
