from __future__ import annotations

import asyncio

import httpx
from bigrag import BigRAG
from bigrag.resources import (
    AdminResource,
    AuthResource,
    ChatResource,
    CollectionsResource,
    ConnectorsResource,
    DocumentsResource,
    EvaluationsResource,
    QueryResource,
    VectorsResource,
    WebhooksResource,
)


def run(coro):
    return asyncio.run(coro)


class SpyClient:
    base_url = "http://api.local"

    def __init__(self) -> None:
        self.calls = []
        self.form_calls = []

    async def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return {"status": "ok"}

    async def _request_form(self, path, **kwargs):
        self.form_calls.append((path, kwargs))
        return {"status": "ok"}


def test_admin_resource_builds_requests() -> None:
    async def scenario() -> SpyClient:
        client = SpyClient()
        admin = AdminResource(client)
        await admin.users.list(limit=2, offset=4)
        await admin.users.create(
            {"email": "a@example.com", "password": "secret123", "role": "admin"}
        )
        await admin.users.update(
            "user/1", {"email": "new@example.com", "role": "member"}
        )
        await admin.users.delete("user/1")
        await admin.api_keys.list(limit=3)
        await admin.api_keys.create({"name": "ci", "scopes": ["collections:read"]})
        await admin.api_keys.update("key/1", {"name": "prod"})
        await admin.api_keys.delete("key/1")
        await admin.access.logs(
            action="query",
            actor_id="actor",
            collection="docs",
            method="POST",
            path="/v1/query",
            status_family="2xx",
            success=False,
            limit=10,
            offset=20,
        )
        await admin.access.overview(window_days=14)
        await admin.audit.list(
            action="create", actor_id="actor", resource_type="collection"
        )
        await admin.settings.list()
        await admin.settings.test({"values": {"qdrant_url": "http://qdrant:6333"}})
        await admin.settings.update({"values": {"session_cookie_secure": True}})
        await admin.settings.reset({"keys": ["session_cookie_secure"]})
        await admin.settings.purge_embedding_cache()
        await admin.backups.list(limit=5, offset=10)
        await admin.backups.get("backup/1")
        await admin.backups.create({"label": "before migration"})
        await admin.connectors.google.get()
        await admin.connectors.google.update({"enabled": True})
        await admin.embedding_presets.list(offset=1)
        await admin.embedding_presets.create(
            {
                "name": "preset",
                "provider": "openai",
                "model": "text-embedding-3-small",
                "api_key": "sk-test",
                "dimension": 1536,
            }
        )
        await admin.embedding_presets.update("preset/1", {"name": "renamed"})
        await admin.embedding_presets.delete("preset/1")
        await admin.mcp_servers.list()
        await admin.mcp_servers.create({"title": "Local", "server_name": "local"})
        await admin.mcp_servers.update("srv/1", {"title": "Renamed"})
        await admin.mcp_servers.rotate("srv/1")
        await admin.mcp_servers.delete("srv/1")
        return client

    assert run(scenario()).calls == [
        ("GET", "/v1/admin/users", {"params": {"limit": "2", "offset": "4"}}),
        (
            "POST",
            "/v1/admin/users",
            {
                "json": {
                    "email": "a@example.com",
                    "password": "secret123",
                    "role": "admin",
                }
            },
        ),
        (
            "PATCH",
            "/v1/admin/users/user%2F1",
            {"json": {"email": "new@example.com", "role": "member"}},
        ),
        ("DELETE", "/v1/admin/users/user%2F1", {}),
        ("GET", "/v1/admin/api-keys", {"params": {"limit": "3"}}),
        (
            "POST",
            "/v1/admin/api-keys",
            {"json": {"name": "ci", "scopes": ["collections:read"]}},
        ),
        ("PATCH", "/v1/admin/api-keys/key%2F1", {"json": {"name": "prod"}}),
        ("DELETE", "/v1/admin/api-keys/key%2F1", {}),
        (
            "GET",
            "/v1/admin/access/logs",
            {
                "params": {
                    "limit": "10",
                    "offset": "20",
                    "action": "query",
                    "actor_id": "actor",
                    "collection": "docs",
                    "method": "POST",
                    "path": "/v1/query",
                    "status_family": "2xx",
                    "success": "false",
                }
            },
        ),
        ("GET", "/v1/admin/access/overview", {"params": {"window_days": "14"}}),
        (
            "GET",
            "/v1/admin/audit",
            {
                "params": {
                    "action": "create",
                    "actor_id": "actor",
                    "resource_type": "collection",
                }
            },
        ),
        ("GET", "/v1/admin/settings", {}),
        (
            "POST",
            "/v1/admin/settings/test",
            {"json": {"values": {"qdrant_url": "http://qdrant:6333"}}},
        ),
        (
            "PUT",
            "/v1/admin/settings",
            {"json": {"values": {"session_cookie_secure": True}}},
        ),
        (
            "POST",
            "/v1/admin/settings/reset",
            {"json": {"keys": ["session_cookie_secure"]}},
        ),
        ("POST", "/v1/admin/settings/embedding-cache/purge", {}),
        ("GET", "/v1/admin/backups", {"params": {"limit": "5", "offset": "10"}}),
        ("GET", "/v1/admin/backups/backup%2F1", {}),
        (
            "POST",
            "/v1/admin/backups",
            {"json": {"label": "before migration"}},
        ),
        ("GET", "/v1/admin/connectors/google", {}),
        ("PUT", "/v1/admin/connectors/google", {"json": {"enabled": True}}),
        ("GET", "/v1/admin/embedding-presets", {"params": {"offset": "1"}}),
        (
            "POST",
            "/v1/admin/embedding-presets",
            {
                "json": {
                    "name": "preset",
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "api_key": "sk-test",
                    "dimension": 1536,
                }
            },
        ),
        (
            "PATCH",
            "/v1/admin/embedding-presets/preset%2F1",
            {"json": {"name": "renamed"}},
        ),
        ("DELETE", "/v1/admin/embedding-presets/preset%2F1", {}),
        ("GET", "/v1/admin/mcp-servers", {}),
        (
            "POST",
            "/v1/admin/mcp-servers",
            {"json": {"title": "Local", "server_name": "local"}},
        ),
        ("PATCH", "/v1/admin/mcp-servers/srv%2F1", {"json": {"title": "Renamed"}}),
        ("POST", "/v1/admin/mcp-servers/srv%2F1/rotate", {}),
        ("DELETE", "/v1/admin/mcp-servers/srv%2F1", {}),
    ]


def test_admin_realtime_streams_snapshots() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            content=(
                "event: snapshot\n"
                'data: {"topic":"backups","payload":{"jobs":[],"total":0},"generated_at":"2026-05-15T00:00:00Z"}\n\n'
            ),
        )

    async def scenario() -> list[dict]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with BigRAG(
                base_url="http://api.local", http_client=http_client
            ) as client:
                return [event async for event in client.admin.realtime.backups(limit=2)]

    assert run(scenario()) == [
        {
            "event": "snapshot",
            "data": {
                "topic": "backups",
                "payload": {"jobs": [], "total": 0},
                "generated_at": "2026-05-15T00:00:00Z",
            },
        }
    ]
    assert str(requests[0].url) == "http://api.local/v1/admin/realtime/backups?limit=2"


def test_auth_and_platform_resources_build_requests() -> None:
    async def scenario() -> SpyClient:
        client = SpyClient()
        auth = AuthResource(client)
        evaluations = EvaluationsResource(client)
        await auth.setup_status()
        await auth.setup(
            {"email": "a@example.com", "password": "secret123", "name": "Admin"}
        )
        await auth.login({"email": "a@example.com", "password": "secret123"})
        await auth.logout()
        await auth.logout_all()
        await auth.me()
        await auth.whoami()
        await auth.change_password(
            {"current_password": "old", "new_password": "new-secret"}
        )
        await auth.get_preferences()
        await auth.update_preferences({"theme": "dark"})
        await evaluations.run({"collection": "docs", "questions": []})
        return client

    assert run(scenario()).calls == [
        ("GET", "/v1/auth/setup-status", {}),
        (
            "POST",
            "/v1/auth/setup",
            {
                "json": {
                    "email": "a@example.com",
                    "password": "secret123",
                    "name": "Admin",
                }
            },
        ),
        (
            "POST",
            "/v1/auth/login",
            {"json": {"email": "a@example.com", "password": "secret123"}},
        ),
        ("POST", "/v1/auth/logout", {}),
        ("POST", "/v1/auth/logout-all", {}),
        ("GET", "/v1/auth/me", {}),
        ("GET", "/v1/auth/whoami", {}),
        (
            "POST",
            "/v1/auth/password",
            {"json": {"current_password": "old", "new_password": "new-secret"}},
        ),
        ("GET", "/v1/auth/preferences", {}),
        ("PUT", "/v1/auth/preferences", {"json": {"data": {"theme": "dark"}}}),
        ("POST", "/v1/evaluation", {"json": {"collection": "docs", "questions": []}}),
    ]


def test_chat_resource_builds_non_streaming_requests() -> None:
    async def scenario() -> SpyClient:
        client = SpyClient()
        chat = ChatResource(client)
        await chat.create({"message": "hello", "collection": "docs"})
        return client

    assert run(scenario()).calls == [
        (
            "POST",
            "/v1/chat",
            {"json": {"message": "hello", "collection": "docs", "stream": False}},
        ),
    ]


def test_collection_connector_query_vector_and_webhook_resources_build_requests() -> (
    None
):
    async def scenario() -> SpyClient:
        client = SpyClient()
        collections = CollectionsResource(client)
        connectors = ConnectorsResource(client)
        queries = QueryResource(client)
        vectors = VectorsResource(client)
        webhooks = WebhooksResource(client)
        await collections.list(name="docs", limit=2, offset=4)
        await collections.get("team docs")
        await collections.create({"name": "docs"})
        await collections.update("team docs", {"metadata": {"owner": "search"}})
        await collections.delete("team docs")
        await collections.stats("team docs")
        await collections.truncate("team docs")
        await collections.reembed("team docs")
        await collections.stream_events("team docs").aclose()
        await connectors.google.account()
        await connectors.google.files(
            parent_id="folder", query="pdf", page_token="next", page_size=50
        )
        await connectors.google.oauth_start_url(redirect_path="/settings")
        await connectors.google.disconnect()
        await connectors.google.sources(collection="docs")
        await connectors.google.create_source(
            {"collection": "docs", "folder_id": "folder"}
        )
        await connectors.google.update_source("source/1", {"enabled": False})
        await connectors.google.delete_source("source/1")
        await connectors.google.sync_source("source/1")
        await connectors.google.sync_jobs(
            collection="docs", source_id="source/1", limit=5
        )
        await queries.query("team docs", {"query": "hello"})
        await queries.multi_query({"collections": ["docs"], "query": "hello"})
        await queries.batch_query(
            {"queries": [{"collection": "docs", "query": "hello"}]}
        )
        await vectors.upsert(
            "team docs", [{"id": "vec/1", "vector": [0.1], "metadata": {"a": 1}}]
        )
        await vectors.delete("team docs", ["vec/1"])
        await webhooks.create(
            {"url": "https://example.com/hook", "events": ["document.created"]}
        )
        await webhooks.list()
        await webhooks.get("hook/1")
        await webhooks.update("hook/1", {"enabled": False})
        await webhooks.delete("hook/1")
        await webhooks.list_deliveries("hook/1", limit=2, offset=4)
        await webhooks.test("hook/1")
        await webhooks.replay_delivery("hook/1", "delivery/1")
        return client

    assert run(scenario()).calls == [
        (
            "GET",
            "/v1/collections",
            {"params": {"name": "docs", "limit": "2", "offset": "4"}},
        ),
        ("GET", "/v1/collections/team%20docs", {}),
        ("POST", "/v1/collections", {"json": {"name": "docs"}}),
        (
            "PUT",
            "/v1/collections/team%20docs",
            {"json": {"metadata": {"owner": "search"}}},
        ),
        ("DELETE", "/v1/collections/team%20docs", {}),
        ("GET", "/v1/collections/team%20docs/stats", {}),
        ("POST", "/v1/collections/team%20docs/truncate", {}),
        ("POST", "/v1/collections/team%20docs/reembed", {}),
        ("GET", "/v1/connectors/google/account", {}),
        (
            "GET",
            "/v1/connectors/google/files",
            {
                "params": {
                    "parent_id": "folder",
                    "query": "pdf",
                    "page_token": "next",
                    "page_size": "50",
                }
            },
        ),
        (
            "GET",
            "/v1/connectors/google/oauth/start-url",
            {"params": {"redirect_path": "/settings"}},
        ),
        ("POST", "/v1/connectors/google/disconnect", {}),
        ("GET", "/v1/connectors/google/sources", {"params": {"collection": "docs"}}),
        (
            "POST",
            "/v1/connectors/google/sources",
            {"json": {"collection": "docs", "folder_id": "folder"}},
        ),
        (
            "PATCH",
            "/v1/connectors/google/sources/source%2F1",
            {"json": {"enabled": False}},
        ),
        ("DELETE", "/v1/connectors/google/sources/source%2F1", {}),
        ("POST", "/v1/connectors/google/sources/source%2F1/sync", {}),
        (
            "GET",
            "/v1/connectors/google/sync-jobs",
            {"params": {"collection": "docs", "source_id": "source/1", "limit": "5"}},
        ),
        ("POST", "/v1/collections/team%20docs/query", {"json": {"query": "hello"}}),
        ("POST", "/v1/query", {"json": {"collections": ["docs"], "query": "hello"}}),
        (
            "POST",
            "/v1/batch/query",
            {"json": {"queries": [{"collection": "docs", "query": "hello"}]}},
        ),
        (
            "POST",
            "/v1/collections/team%20docs/vectors/upsert",
            {
                "json": {
                    "vectors": [{"id": "vec/1", "vector": [0.1], "metadata": {"a": 1}}]
                }
            },
        ),
        (
            "POST",
            "/v1/collections/team%20docs/vectors/delete",
            {"json": {"ids": ["vec/1"]}},
        ),
        (
            "POST",
            "/v1/admin/webhooks",
            {
                "json": {
                    "url": "https://example.com/hook",
                    "events": ["document.created"],
                }
            },
        ),
        ("GET", "/v1/admin/webhooks", {}),
        ("GET", "/v1/admin/webhooks/hook%2F1", {}),
        ("PUT", "/v1/admin/webhooks/hook%2F1", {"json": {"enabled": False}}),
        ("DELETE", "/v1/admin/webhooks/hook%2F1", {}),
        (
            "GET",
            "/v1/admin/webhooks/hook%2F1/deliveries",
            {"params": {"limit": "2", "offset": "4"}},
        ),
        ("POST", "/v1/admin/webhooks/hook%2F1/test", {}),
        ("POST", "/v1/admin/webhooks/hook%2F1/deliveries/delivery%2F1/replay", {}),
    ]


def test_documents_resource_builds_all_request_shapes() -> None:
    async def scenario() -> SpyClient:
        client = SpyClient()
        documents = DocumentsResource(client)
        await documents.upload(
            "team docs", ("note.txt", b"hello"), metadata={"tenant": "acme"}
        )
        await documents.batch_upload("team docs", [("a.txt", b"a"), ("b.txt", b"b")])
        await documents.create_upload_session(
            "team docs", total_files=2, total_bytes=10
        )
        await documents.get_upload_session("team docs", "session/1")
        await documents.upload_session_file(
            "team docs",
            "session/1",
            ("original.txt", b"hello"),
            client_item_id="item-1",
            filename="note.txt",
        )
        await documents.complete_upload_session("team docs", "session/1")
        await documents.cancel_upload_session("team docs", "session/1")
        await documents.list("team docs", status="ready", limit=5, offset=10)
        await documents.get("team docs", "doc/1")
        await documents.get_by_id("doc/1")
        await documents.delete("team docs", "doc/1")
        await documents.reprocess("team docs", "doc/1")
        await documents.get_chunks("team docs", "doc/1", limit=3, offset=6)
        await documents.get_chunks_by_id("doc/1", limit=1)
        await documents.batch_get_status("team docs", ["doc/1"])
        await documents.batch_get("team docs", ["doc/1"])
        await documents.batch_delete("team docs", ["doc/1"])
        return client

    client = run(scenario())
    assert [path for path, _kwargs in client.form_calls] == [
        "/v1/collections/team%20docs/documents",
        "/v1/collections/team%20docs/documents/batch/upload",
        "/v1/collections/team%20docs/upload-sessions/session%2F1/files",
    ]
    assert client.calls == [
        (
            "POST",
            "/v1/collections/team%20docs/upload-sessions",
            {"json": {"total_files": 2, "total_bytes": 10, "metadata": {}}},
        ),
        ("GET", "/v1/collections/team%20docs/upload-sessions/session%2F1", {}),
        (
            "POST",
            "/v1/collections/team%20docs/upload-sessions/session%2F1/complete",
            {},
        ),
        ("POST", "/v1/collections/team%20docs/upload-sessions/session%2F1/cancel", {}),
        (
            "GET",
            "/v1/collections/team%20docs/documents",
            {"params": {"status": "ready", "limit": "5", "offset": "10"}},
        ),
        ("GET", "/v1/collections/team%20docs/documents/doc%2F1", {}),
        ("GET", "/v1/documents/doc%2F1", {}),
        ("DELETE", "/v1/collections/team%20docs/documents/doc%2F1", {}),
        ("POST", "/v1/collections/team%20docs/documents/doc%2F1/reprocess", {}),
        (
            "GET",
            "/v1/collections/team%20docs/documents/doc%2F1/chunks",
            {"params": {"limit": "3", "offset": "6"}},
        ),
        ("GET", "/v1/documents/doc%2F1/chunks", {"params": {"limit": "1"}}),
        (
            "POST",
            "/v1/collections/team%20docs/documents/batch/status",
            {"json": {"document_ids": ["doc/1"]}},
        ),
        (
            "POST",
            "/v1/collections/team%20docs/documents/batch/get",
            {"json": {"document_ids": ["doc/1"]}},
        ),
        (
            "POST",
            "/v1/collections/team%20docs/documents/batch/delete",
            {"json": {"document_ids": ["doc/1"]}},
        ),
    ]
