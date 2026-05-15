use std::path::PathBuf;
use std::time::Duration;

use bigrag::types::admin::{
    CreateApiKeyBody, CreateEmbeddingPresetBody, CreateMcpServerBody, CreateUserBody,
    UpdateApiKeyBody, UpdateEmbeddingPresetBody, UpdateMcpServerBody, UpdateUserBody,
};
use bigrag::types::auth::{ChangePasswordBody, LoginBody, SetupBody, UpdatePreferencesBody};
use bigrag::types::chat::ChatBody;
use bigrag::types::collections::{
    CollectionListOptions, CreateCollectionBody, UpdateCollectionBody,
};
use bigrag::types::common::PaginationOptions;
use bigrag::types::connectors::{
    CreateGoogleSourceBody, UpdateGoogleConnectorConfigBody, UpdateGoogleSourceBody,
};
use bigrag::types::documents::{
    DocumentChunkOptions, DocumentListOptions, UploadSessionCreateRequest,
};
use bigrag::types::evaluations::{EvalBody, EvalCase};
use bigrag::types::query::{BatchQueryBody, BatchQueryItem, MultiQueryBody, QueryBody, SearchMode};
use bigrag::types::vectors::VectorEntry;
use bigrag::types::webhooks::{CreateWebhookBody, UpdateWebhookBody};
use bigrag::{AccessLogOptions, AuditLogOptions, BigRag, BigRagError, FileInput};
use httpmock::MockServer;
use serde_json::json;

fn client(server: &MockServer) -> BigRag {
    BigRag::builder()
        .base_url(&format!("{}/", server.base_url()))
        .api_key("bigrag_sk_test")
        .timeout(Duration::from_secs(5))
        .max_retries(0)
        .reqwest_client(reqwest::Client::new())
        .build()
        .unwrap()
}

#[tokio::test]
async fn exercises_public_sdk_methods() {
    let server = MockServer::start_async().await;
    let mock = server
        .mock_async(|when, then| {
            when.any_request();
            then.status(200).json_body(json!({ "status": "ok" }));
        })
        .await;
    let client = client(&server);

    let _ = client.health().await;
    let _ = client.readiness().await;
    let _ = client.stats().await;
    let _ = client.embedding_models().await;
    let _ = client.analytics("docs/name").await;
    let _ = client.usage(Some(7)).await;

    let auth = client.auth();
    let _ = auth.setup_status().await;
    let _ = auth
        .setup(SetupBody {
            email: "admin@example.com".into(),
            password: "secret".into(),
            display_name: Some("Admin".into()),
        })
        .await;
    let _ = auth
        .login(LoginBody {
            email: "admin@example.com".into(),
            password: "secret".into(),
        })
        .await;
    let _ = auth.logout().await;
    let _ = auth.logout_all().await;
    let _ = auth.me().await;
    let _ = auth.whoami().await;
    let _ = auth
        .change_password(ChangePasswordBody {
            current_password: "old".into(),
            new_password: "new".into(),
        })
        .await;
    let _ = auth.preferences().await;
    let _ = auth
        .update_preferences(UpdatePreferencesBody {
            data: json!({ "theme": "dark" }),
        })
        .await;

    let collections = client.collections();
    let _ = collections
        .list(Some(CollectionListOptions {
            name: Some("docs".into()),
            limit: Some(10),
            offset: Some(2),
        }))
        .await;
    let _ = collections.get("docs/name").await;
    let _ = collections
        .create(CreateCollectionBody {
            name: "docs".into(),
            description: Some("Docs".into()),
            vector_store_provider: Some("qdrant".into()),
            embedding_provider: Some("openai".into()),
            embedding_model: Some("text-embedding-3-small".into()),
            embedding_api_key: Some("sk".into()),
            embedding_preset_id: Some("preset".into()),
            embedding_base_url: Some("https://api.example.com".into()),
            dimension: Some(1536),
            chunk_size: Some(500),
            chunk_overlap: Some(50),
            chunk_strategy: Some("recursive".into()),
            index_type: Some("HNSW".into()),
            metadata_schema: Some(json!({ "type": "object" })),
            tenant_field: Some("tenant".into()),
            reranking_enabled: Some(true),
            reranking_model: Some("rerank".into()),
            reranking_api_key: Some("rk".into()),
            default_top_k: Some(5),
            default_min_score: Some(0.2),
            default_search_mode: Some("hybrid".into()),
            metadata: Some(json!({ "team": "search" })),
        })
        .await;
    let _ = collections
        .update(
            "docs/name",
            UpdateCollectionBody {
                description: Some("Updated".into()),
                embedding_api_key: Some(Some("sk2".into())),
                chunk_strategy: Some("paragraph".into()),
                metadata_schema: Some(json!({ "type": "object" })),
                reranking_enabled: Some(false),
                reranking_model: Some("rerank2".into()),
                reranking_api_key: Some(Some("rk2".into())),
                default_top_k: Some(6),
                default_min_score: Some(0.3),
                default_search_mode: Some("semantic".into()),
                metadata: Some(json!({ "team": "platform" })),
            },
        )
        .await;
    let _ = collections.delete("docs/name").await;
    let _ = collections.stats("docs/name").await;
    let _ = collections.truncate("docs/name").await;
    let _ = collections.reembed("docs/name").await;
    let _ = collections.stream_events("docs/name").await;

    let query = QueryBody {
        query: "what is rust".into(),
        top_k: Some(3),
        filters: Some(json!({ "tenant": "acme" })),
        min_score: Some(0.1),
        search_mode: Some(SearchMode::Hybrid),
        rerank: Some(true),
    };
    let queries = client.queries();
    let _ = queries.query("docs/name", query.clone()).await;
    let _ = queries
        .multi_query(MultiQueryBody {
            query: "what is rust".into(),
            collections: vec!["docs".into(), "api".into()],
            top_k: Some(3),
            filters: Some(json!({ "tenant": "acme" })),
            min_score: Some(0.1),
            search_mode: Some(SearchMode::Semantic),
            rerank: Some(false),
        })
        .await;
    let _ = queries
        .batch_query(BatchQueryBody {
            queries: vec![BatchQueryItem {
                collection: "docs".into(),
                query: "batch".into(),
                top_k: Some(2),
                filters: Some(json!({ "kind": "guide" })),
                min_score: Some(0.2),
                search_mode: Some(SearchMode::Keyword),
                rerank: Some(false),
            }],
        })
        .await;

    let chat = client.chat();
    let _ = chat
        .create(ChatBody {
            message: "hello".into(),
            ..Default::default()
        })
        .await;
    let _ = chat
        .stream(ChatBody {
            message: "hello".into(),
            ..Default::default()
        })
        .await;
    let _ = chat.list(Some(20), Some(1)).await;
    let _ = chat.get("conversation/id").await;
    let _ = chat.update_title("conversation/id", "New title").await;
    let _ = chat.delete("conversation/id").await;

    let vectors = client.vectors();
    let _ = vectors
        .upsert(
            "docs/name",
            vec![VectorEntry {
                id: "vec1".into(),
                embedding: vec![0.1, 0.2],
                text: Some("text".into()),
                metadata: Some(json!({ "source": "test" })),
            }],
        )
        .await;
    let _ = vectors.delete("docs/name", &["vec1", "vec2"]).await;

    let evaluations = client.evaluations();
    let _ = evaluations
        .run(EvalBody {
            collection: "docs".into(),
            cases: vec![EvalCase {
                query: "q".into(),
                relevant_ids: vec!["doc1".into()],
                top_k: Some(1),
            }],
            top_k: Some(3),
            search_mode: Some(SearchMode::Semantic),
        })
        .await;

    let connectors = client.connectors();
    let google = connectors.google();
    let _ = google.account().await;
    let _ = google
        .files(Some("folder"), Some("pdf"), Some("page"), Some(25))
        .await;
    let _ = google.oauth_start_url(Some("/settings")).await;
    let _ = google.disconnect().await;
    let _ = google.sources(Some("docs")).await;
    let _ = google
        .create_source(CreateGoogleSourceBody {
            collection_name: "docs".into(),
            root_id: "root".into(),
            root_name: "Root".into(),
            root_mime_type: Some("folder".into()),
            source_type: Some("folder".into()),
            metadata: Some(json!({ "sync": true })),
        })
        .await;
    let _ = google
        .update_source(
            "source/id",
            UpdateGoogleSourceBody {
                schedule_enabled: Some(true),
                sync_interval_hours: Some(24),
            },
        )
        .await;
    let _ = google.delete_source("source/id").await;
    let _ = google.sync_source("source/id").await;
    let _ = google.sync_jobs(Some("source/id"), Some(5)).await;
    let _ = google
        .sync_jobs_filtered(Some("docs"), Some("source/id"), Some(5))
        .await;

    let webhooks = client.webhooks();
    let _ = webhooks
        .create(CreateWebhookBody {
            url: "https://example.com/hook".into(),
            events: vec!["document.ready".into()],
            collections: Some(vec!["docs".into()]),
            description: Some("Hook".into()),
        })
        .await;
    let _ = webhooks.list().await;
    let _ = webhooks.get("hook/id").await;
    let _ = webhooks
        .update(
            "hook/id",
            UpdateWebhookBody {
                url: Some("https://example.com/new".into()),
                events: Some(vec!["document.failed".into()]),
                collections: Some(Some(vec!["docs".into()])),
                description: Some("Updated".into()),
                active: Some(false),
            },
        )
        .await;
    let _ = webhooks.delete("hook/id").await;
    let _ = webhooks
        .list_deliveries(
            "hook/id",
            Some(PaginationOptions {
                limit: Some(10),
                offset: Some(5),
            }),
        )
        .await;
    let _ = webhooks.test("hook/id").await;
    let _ = webhooks.replay_delivery("hook/id", "delivery/id").await;

    let admin = client.admin();
    let admin_connectors = admin.connectors();
    let admin_google = admin_connectors.google();
    let _ = admin.users();
    let _ = admin.api_keys();
    let _ = admin.access();
    let _ = admin.audit();
    let _ = admin.connectors();
    let _ = admin.embedding_presets();
    let _ = admin.mcp_servers();
    let _ = admin
        .users()
        .list(Some(PaginationOptions {
            limit: Some(10),
            offset: Some(1),
        }))
        .await;
    let _ = admin
        .users()
        .create(CreateUserBody {
            email: "user@example.com".into(),
            password: "secret".into(),
            display_name: Some("User".into()),
            role: Some("admin".into()),
        })
        .await;
    let _ = admin
        .users()
        .update(
            "user/id",
            UpdateUserBody {
                email: Some("updated@example.com".into()),
                display_name: Some("Updated".into()),
                role: Some("viewer".into()),
                password: Some("secret2".into()),
            },
        )
        .await;
    let _ = admin.users().delete("user/id").await;
    let _ = admin
        .api_keys()
        .list(Some(PaginationOptions {
            limit: Some(10),
            offset: Some(2),
        }))
        .await;
    let _ = admin
        .api_keys()
        .create(CreateApiKeyBody {
            name: "key".into(),
            expires_at: Some("2026-01-01T00:00:00Z".into()),
            scopes: Some(vec!["collections:read".into()]),
            collection: Some("docs".into()),
        })
        .await;
    let _ = admin
        .api_keys()
        .update(
            "key/id",
            UpdateApiKeyBody {
                name: Some("key2".into()),
                active: Some(false),
                scopes: Some(vec!["documents:read".into()]),
                collection: Some("docs2".into()),
            },
        )
        .await;
    let _ = admin.api_keys().delete("key/id").await;
    let _ = admin
        .access()
        .logs(Some(AccessLogOptions {
            action: Some("query".into()),
            actor_id: Some("actor".into()),
            collection: Some("docs".into()),
            method: Some("GET".into()),
            path: Some("/v1".into()),
            status_family: Some("2xx".into()),
            success: Some(true),
            limit: Some(10),
            offset: Some(0),
        }))
        .await;
    let _ = admin.access().overview(Some(14)).await;
    let _ = admin
        .audit()
        .list(Some(AuditLogOptions {
            action: Some("create".into()),
            actor_id: Some("actor".into()),
            resource_type: Some("collection".into()),
            limit: Some(10),
            offset: Some(0),
        }))
        .await;
    let _ = admin_google.get().await;
    let _ = admin_google
        .update(UpdateGoogleConnectorConfigBody {
            enabled: Some(true),
            client_id: Some("client".into()),
            client_secret: Some("secret".into()),
        })
        .await;
    let _ = admin
        .embedding_presets()
        .list(Some(PaginationOptions {
            limit: Some(10),
            offset: Some(0),
        }))
        .await;
    let _ = admin
        .embedding_presets()
        .create(CreateEmbeddingPresetBody {
            name: "preset".into(),
            provider: "openai".into(),
            model: "text-embedding-3-small".into(),
            api_key: "sk".into(),
            base_url: Some("https://api.example.com".into()),
            dimension: 1536,
        })
        .await;
    let _ = admin
        .embedding_presets()
        .update(
            "preset/id",
            UpdateEmbeddingPresetBody {
                name: Some("preset2".into()),
                provider: Some("cohere".into()),
                model: Some("embed".into()),
                api_key: Some("ck".into()),
                base_url: Some("https://cohere.example.com".into()),
                dimension: Some(1024),
            },
        )
        .await;
    let _ = admin.embedding_presets().delete("preset/id").await;
    let _ = admin.mcp_servers().list().await;
    let _ = admin
        .mcp_servers()
        .create(CreateMcpServerBody {
            title: "MCP".into(),
            server_name: "docs".into(),
            collection: Some("docs".into()),
        })
        .await;
    let _ = admin
        .mcp_servers()
        .update(
            "server/id",
            UpdateMcpServerBody {
                title: Some("MCP 2".into()),
                server_name: Some("docs2".into()),
                collection: Some("docs2".into()),
            },
        )
        .await;
    let _ = admin.mcp_servers().rotate("server/id").await;
    let _ = admin.mcp_servers().delete("server/id").await;

    let documents = client.documents();
    let _ = documents
        .upload(
            "docs/name",
            FileInput::from((b"hello".to_vec(), "hello.txt")),
            Some(json!({ "kind": "note" })),
        )
        .await;
    let _ = documents
        .batch_upload(
            "docs/name",
            vec![FileInput::from((b"one".to_vec(), "one.txt"))],
            Some(json!({ "batch": true })),
        )
        .await;
    let _ = documents
        .create_upload_session(
            "docs/name",
            UploadSessionCreateRequest {
                total_files: 2,
                total_bytes: 12,
                metadata: json!({ "source": "tests" }),
            },
        )
        .await;
    let _ = documents
        .get_upload_session("docs/name", "session/id")
        .await;
    let _ = documents
        .upload_session_file(
            "docs/name",
            "session/id",
            FileInput::from((b"two".to_vec(), "two.txt")),
            Some("client-item"),
        )
        .await;
    let _ = documents
        .complete_upload_session("docs/name", "session/id")
        .await;
    let _ = documents
        .cancel_upload_session("docs/name", "session/id")
        .await;
    let _ = documents
        .list(
            "docs/name",
            Some(DocumentListOptions {
                status: Some("ready".into()),
                limit: Some(10),
                offset: Some(1),
            }),
        )
        .await;
    let _ = documents.get("docs/name", "document/id").await;
    let _ = documents.delete("docs/name", "document/id").await;
    let _ = documents.reprocess("docs/name", "document/id").await;
    let _ = documents.get_chunks("docs/name", "document/id").await;
    let _ = documents
        .get_chunks_with_options(
            "docs/name",
            "document/id",
            Some(DocumentChunkOptions {
                limit: Some(10),
                offset: Some(2),
            }),
        )
        .await;
    assert!(documents
        .get_file_url("docs/name", "document/id")
        .contains("/v1/collections/docs%2Fname/documents/document%2Fid/file"));
    let _ = documents
        .batch_get_status("docs/name", &["doc1", "doc2"])
        .await;
    let _ = documents.batch_get("docs/name", &["doc1", "doc2"]).await;
    let _ = documents.batch_delete("docs/name", &["doc1", "doc2"]).await;
    let _ = documents.get_by_id("document/id").await;
    let _ = documents.get_chunks_by_id("document/id").await;
    let _ = documents
        .get_chunks_by_id_with_options(
            "document/id",
            Some(DocumentChunkOptions {
                limit: Some(3),
                offset: Some(1),
            }),
        )
        .await;

    let scoped = client.collection("docs/name");
    let _ = scoped
        .upload(FileInput::from((b"scoped".to_vec(), "scoped.txt")), None)
        .await;
    let _ = scoped
        .batch_upload(vec![FileInput::from((b"s".to_vec(), "s.txt"))], None)
        .await;
    let _ = scoped
        .create_upload_session(UploadSessionCreateRequest {
            total_files: 1,
            total_bytes: 1,
            metadata: json!({}),
        })
        .await;
    let _ = scoped.get_upload_session("session/id").await;
    let _ = scoped
        .upload_session_file(
            "session/id",
            FileInput::from((b"s".to_vec(), "s.txt")),
            Some("item"),
        )
        .await;
    let _ = scoped.complete_upload_session("session/id").await;
    let _ = scoped.cancel_upload_session("session/id").await;
    let _ = scoped.list_documents(None).await;
    let _ = scoped.get_document("document/id").await;
    let _ = scoped.delete_document("document/id").await;
    let _ = scoped.reprocess_document("document/id").await;
    let _ = scoped.get_document_chunks("document/id").await;
    let _ = scoped
        .get_document_chunks_with_options(
            "document/id",
            Some(DocumentChunkOptions {
                limit: Some(1),
                offset: Some(0),
            }),
        )
        .await;
    let _ = scoped.batch_get_status(&["doc1"]).await;
    let _ = scoped.batch_get_documents(&["doc1"]).await;
    let _ = scoped.batch_delete(&["doc1"]).await;
    let _ = scoped.query(query).await;
    let _ = scoped
        .chat(ChatBody {
            message: "hi".into(),
            ..Default::default()
        })
        .await;
    let _ = scoped.stats().await;
    let _ = scoped.reembed().await;
    let _ = scoped.analytics().await;
    let _ = scoped.stream_events().await;

    assert!(mock.calls_async().await > 80);
}

#[test]
fn covers_file_input_filenames_and_error_helpers() {
    let path = PathBuf::from("/tmp/report.pdf");
    let named = FileInput::PathWithName {
        path: path.clone(),
        name: "custom.pdf".into(),
    };
    let bytes = FileInput::from((b"abc".to_vec(), "bytes.txt"));
    let stream = FileInput::Stream {
        body: reqwest::Body::from("stream"),
        name: "stream.txt".into(),
    };

    assert_eq!(FileInput::from(path).filename(), "report.pdf");
    assert_eq!(FileInput::from(PathBuf::from("")).filename(), "document");
    assert_eq!(named.filename(), "custom.pdf");
    assert_eq!(bytes.filename(), "bytes.txt");
    assert_eq!(stream.filename(), "stream.txt");

    let errors = [
        BigRagError::BadRequest {
            message: "bad".into(),
            status: 422,
        },
        BigRagError::Authentication {
            message: "no".into(),
        },
        BigRagError::NotFound {
            message: "missing".into(),
        },
        BigRagError::Conflict {
            message: "duplicate".into(),
        },
        BigRagError::RateLimited,
        BigRagError::ServerError {
            message: "down".into(),
            status: 503,
        },
        BigRagError::Api {
            status: 418,
            message: "teapot".into(),
        },
        BigRagError::Timeout(Duration::from_secs(1)),
        BigRagError::Connection("closed".into()),
    ];

    assert_eq!(errors[0].status(), Some(422));
    assert_eq!(errors[1].status(), Some(401));
    assert_eq!(errors[2].status(), Some(404));
    assert_eq!(errors[3].status(), Some(409));
    assert_eq!(errors[4].status(), Some(429));
    assert_eq!(errors[5].status(), Some(503));
    assert_eq!(errors[6].status(), Some(418));
    assert_eq!(errors[7].status(), None);
    assert_eq!(errors[8].status(), None);
    assert!(!errors[0].is_retryable());
    assert!(errors[4].is_retryable());
    assert!(errors[5].is_retryable());
    assert!(errors[7].is_retryable());
    assert!(errors[8].is_retryable());
}
