mod common;

use bigrag::types::*;
use wiremock::matchers::{header, method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

#[tokio::test]
async fn test_list_collections() {
    let mock_server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/collections"))
        .and(header("Authorization", "Bearer test-key"))
        .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
            "collections": [{
                "id": "col-1", "name": "docs", "description": "",
                "embedding_provider": "openai", "embedding_model": "m",
                "dimension": 1536, "chunk_size": 512, "chunk_overlap": 50,
                "document_count": 0, "has_api_key": true,
                "reranking_enabled": false, "reranking_model": "",
                "has_reranking_api_key": false, "default_top_k": 10,
                "default_min_score": null, "default_search_mode": "semantic",
                "metadata": {}, "created_at": "", "updated_at": ""
            }],
            "total": 1
        })))
        .mount(&mock_server)
        .await;

    let client = common::test_client(&mock_server).await;
    let resp = client.collections().list(None).await.unwrap();
    assert_eq!(resp.total, 1);
    assert_eq!(resp.collections[0].name, "docs");
}

#[tokio::test]
async fn test_create_collection() {
    let mock_server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/collections"))
        .respond_with(ResponseTemplate::new(201).set_body_json(serde_json::json!({
            "id": "new-col", "name": "test", "description": "",
            "embedding_provider": "openai", "embedding_model": "text-embedding-3-small",
            "dimension": 1536, "chunk_size": 512, "chunk_overlap": 50,
            "document_count": 0, "has_api_key": false,
            "reranking_enabled": false, "reranking_model": "",
            "has_reranking_api_key": false, "default_top_k": 10,
            "default_min_score": null, "default_search_mode": "semantic",
            "metadata": {}, "created_at": "", "updated_at": ""
        })))
        .mount(&mock_server)
        .await;

    let client = common::test_client(&mock_server).await;
    let col = client
        .collections()
        .create(CreateCollectionBody {
            name: "test".into(),
            ..Default::default()
        })
        .await
        .unwrap();
    assert_eq!(col.name, "test");
}

#[tokio::test]
async fn test_query_collection() {
    let mock_server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/collections/docs/query"))
        .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
            "results": [{"id": "r1", "text": "hello world", "score": 0.95, "document_id": "d1", "chunk_index": 0, "metadata": {}}],
            "query": "hello",
            "collection": "docs",
            "total": 1
        })))
        .mount(&mock_server)
        .await;

    let client = common::test_client(&mock_server).await;
    let resp = client
        .queries()
        .query(
            "docs",
            QueryBody {
                query: "hello".into(),
                ..Default::default()
            },
        )
        .await
        .unwrap();
    assert_eq!(resp.total, 1);
    assert_eq!(resp.results[0].score, 0.95);
}

#[tokio::test]
async fn test_health_check() {
    let mock_server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/health"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_json(serde_json::json!({"status": "ok", "version": "1.0.0"})),
        )
        .mount(&mock_server)
        .await;

    let client = common::test_client(&mock_server).await;
    let resp = client.health().await.unwrap();
    assert_eq!(resp.status, "ok");
    assert_eq!(resp.version, "1.0.0");
}

#[tokio::test]
async fn test_not_found_error() {
    let mock_server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/v1/collections/missing"))
        .respond_with(
            ResponseTemplate::new(404)
                .set_body_json(serde_json::json!({"detail": "Collection not found"})),
        )
        .mount(&mock_server)
        .await;

    let client = common::test_client(&mock_server).await;
    let err = client.collections().get("missing").await.unwrap_err();
    assert!(matches!(err, bigrag::BigRagError::NotFound { .. }));
    assert_eq!(err.status(), Some(404));
}

#[tokio::test]
async fn test_collection_client_delegates() {
    let mock_server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/v1/collections/my-col/query"))
        .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
            "results": [], "query": "test", "collection": "my-col", "total": 0
        })))
        .mount(&mock_server)
        .await;

    let client = common::test_client(&mock_server).await;
    let col = client.collection("my-col");
    let resp = col
        .query(QueryBody {
            query: "test".into(),
            ..Default::default()
        })
        .await
        .unwrap();
    assert_eq!(resp.collection, "my-col");
    assert_eq!(resp.total, 0);
}
