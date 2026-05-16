use std::path::PathBuf;
use std::time::Duration;

use bigrag::types::chat::ChatBody;
use bigrag::{BigRag, BigRagError, FileInput};
use httpmock::Method::POST;
use httpmock::MockServer;
use serde_json::{json, Value};

fn client(server: &MockServer) -> BigRag {
    BigRag::builder()
        .base_url(&server.base_url())
        .api_key("bigrag_sk_test")
        .timeout(Duration::from_secs(5))
        .max_retries(0)
        .reqwest_client(reqwest::Client::new())
        .build()
        .unwrap()
}

fn message(id: &str, role: &str, content: &str) -> Value {
    json!({
        "id": id,
        "role": role,
        "content": content,
        "status": "complete",
        "error_message": null,
        "model_provider": null,
        "model": null,
        "retrieval": {},
        "sources": [],
        "created_at": "2026-05-09T00:00:00Z"
    })
}

fn document() -> Value {
    json!({
        "id": "doc",
        "collection_id": "col",
        "filename": "note.txt",
        "file_type": "txt",
        "file_size": 5,
        "chunk_count": 0,
        "status": "pending",
        "error_message": null,
        "metadata": {},
        "content_hash": null,
        "deduped": false,
        "progress": null,
        "created_at": "2026-05-09T00:00:00Z",
        "updated_at": "2026-05-09T00:00:00Z"
    })
}

#[tokio::test]
async fn chat_methods_send_expected_requests() {
    let server = MockServer::start_async().await;
    let create = server
        .mock_async(|when, then| {
            when.method(POST)
                .path("/v1/chat")
                .header("authorization", "Bearer bigrag_sk_test")
                .json_body(json!({
                    "message": "hello",
                    "collection": "docs",
                    "stream": false
                }));
            then.status(200).json_body(json!({
                "message": message("user-message", "user", "hello"),
                "assistant_message": message("assistant-message", "assistant", "hi"),
                "sources": [],
                "timings": null
            }));
        })
        .await;
    let client = client(&server);
    let chat = client.chat();

    let created = chat
        .create(ChatBody {
            message: "hello".into(),
            collection: "docs".into(),
            ..Default::default()
        })
        .await
        .unwrap();

    assert_eq!(created.assistant_message.content, "hi");
    create.assert_calls_async(1).await;
}

#[test]
fn file_input_reports_upload_filenames() {
    assert_eq!(FileInput::from("/tmp/note.txt").filename(), "note.txt");
    assert_eq!(
        FileInput::PathWithName {
            path: PathBuf::from("/tmp/source.bin"),
            name: "renamed.txt".into()
        }
        .filename(),
        "renamed.txt"
    );
    assert_eq!(
        FileInput::Bytes {
            data: b"hello".to_vec(),
            name: "bytes.txt".into()
        }
        .filename(),
        "bytes.txt"
    );
}

#[tokio::test]
async fn upload_uses_multipart_filename_and_body() {
    let server = MockServer::start_async().await;
    let path =
        std::env::temp_dir().join(format!("bigrag-rust-sdk-{}-note.txt", std::process::id()));
    tokio::fs::write(&path, b"hello").await.unwrap();
    let mock = server
        .mock_async(|when, then| {
            when.method(POST)
                .path("/v1/collections/docs/documents")
                .body_includes("filename=\"renamed.txt\"")
                .body_includes("hello");
            then.status(200).json_body(document());
        })
        .await;
    let client = client(&server);

    let uploaded = client
        .documents()
        .upload(
            "docs",
            FileInput::PathWithName {
                path: path.clone(),
                name: "renamed.txt".into(),
            },
            None,
        )
        .await
        .unwrap();

    tokio::fs::remove_file(path).await.unwrap();
    assert_eq!(uploaded.filename, "note.txt");
    mock.assert_calls_async(1).await;
}

#[tokio::test]
async fn upload_reports_missing_file_errors_before_request() {
    let server = MockServer::start_async().await;
    let client = client(&server);
    let missing = std::env::temp_dir().join(format!(
        "bigrag-rust-sdk-{}-missing.txt",
        std::process::id()
    ));

    let error = client
        .documents()
        .upload("docs", missing, None)
        .await
        .unwrap_err();

    assert!(matches!(error, BigRagError::FileRead(_)));
}
