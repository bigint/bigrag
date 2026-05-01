from __future__ import annotations

import asyncio
from typing import Any

from bigrag.resources import AdminResource, AuthResource, EvaluationsResource


class RecordingClient:
    base_url = "https://bigrag.example"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, str]:
        self.calls.append((method, path, {"json": json, "params": params}))
        return {"status": "ok"}


def run(coro):
    return asyncio.run(coro)


def test_auth_resource_routes() -> None:
    client = RecordingClient()
    auth = AuthResource(client)  # type: ignore[arg-type]

    run(auth.setup_status())
    run(auth.login({"email": "admin@example.com", "password": "password123"}))
    run(auth.whoami())
    run(auth.update_preferences({"theme": "dark"}))

    assert client.calls == [
        ("GET", "/v1/auth/setup-status", {"json": None, "params": None}),
        (
            "POST",
            "/v1/auth/login",
            {
                "json": {"email": "admin@example.com", "password": "password123"},
                "params": None,
            },
        ),
        ("GET", "/v1/auth/whoami", {"json": None, "params": None}),
        (
            "PUT",
            "/v1/auth/preferences",
            {"json": {"data": {"theme": "dark"}}, "params": None},
        ),
    ]


def test_admin_resource_routes() -> None:
    client = RecordingClient()
    admin = AdminResource(client)  # type: ignore[arg-type]

    run(admin.users.list(limit=10, offset=5))
    run(admin.api_keys.create({"name": "ingest"}))
    run(admin.audit.list(action="api_key.create", resource_type="api_key"))
    run(admin.embedding_presets.update("preset id", {"name": "prod"}))
    run(admin.mcp_servers.rotate("server id"))

    assert client.calls == [
        ("GET", "/v1/admin/users", {"json": None, "params": {"limit": "10", "offset": "5"}}),
        ("POST", "/v1/admin/api-keys", {"json": {"name": "ingest"}, "params": None}),
        (
            "GET",
            "/v1/admin/audit",
            {
                "json": None,
                "params": {"action": "api_key.create", "resource_type": "api_key"},
            },
        ),
        (
            "PATCH",
            "/v1/admin/embedding-presets/preset%20id",
            {"json": {"name": "prod"}, "params": None},
        ),
        (
            "POST",
            "/v1/admin/mcp-servers/server%20id/rotate",
            {"json": None, "params": None},
        ),
    ]


def test_evaluation_resource_route() -> None:
    client = RecordingClient()
    evaluations = EvaluationsResource(client)  # type: ignore[arg-type]

    body = {"collection": "docs", "cases": [{"query": "q", "relevant_ids": ["doc-1"]}]}
    run(evaluations.run(body))

    assert client.calls == [
        ("POST", "/v1/evaluation", {"json": body, "params": None}),
    ]
