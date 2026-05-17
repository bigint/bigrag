from __future__ import annotations

import time

from starlette.requests import Request
from starlette.types import Receive, Scope, Send

from bigrag.logging import REQUEST_ID_HEADER
from bigrag.services.access_log.context import build_row
from bigrag.services.access_log.flusher import enqueue
from bigrag.services.client_ip import client_ip, client_ip_from_scope

RAG_ACCESS_ACTIONS = frozenset(
    {
        "evaluation.run",
        "chat.generate",
        "query.batch",
        "query.multi",
        "query.run",
        "vectors.delete",
        "vectors.upsert",
    }
)


def _infer_action(method: str, path: str) -> tuple[str, str]:
    if path == "/v1/chat" and method == "POST":
        return "chat.generate", "chat"
    if path == "/v1/query" and method == "POST":
        return "query.multi", "collections"
    if path == "/v1/batch/query" and method == "POST":
        return "query.batch", "collections"
    if path == "/v1/evaluation" and method == "POST":
        return "evaluation.run", "collection"
    if path.endswith("/query") and method == "POST":
        return "query.run", "collection"
    if "/vectors/upsert" in path and method == "POST":
        return "vectors.upsert", "collection"
    if "/vectors/delete" in path and method == "POST":
        return "vectors.delete", "collection"
    return "http.request", "http"


def _should_record(scope: Scope) -> bool:
    if scope.get("method") == "OPTIONS":
        return False
    method = str(scope.get("method") or "")
    path = str(scope.get("path") or "")
    action, _ = _infer_action(method, path)
    return action in RAG_ACCESS_ACTIONS


class AccessLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _should_record(scope):
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        method = str(scope.get("method") or "")
        path = str(scope.get("path") or "")
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            request = Request(scope)
            principal = getattr(request.state, "user", None) or {}
            context = getattr(request.state, "access_log_context", None) or {}
            inferred_action, inferred_resource = _infer_action(method, path)
            route = getattr(scope.get("route"), "path", None)

            metadata = dict(context.get("metadata") or {})
            metadata.setdefault("route", route)
            request_id = getattr(request.state, "request_id", None) or request.headers.get(
                REQUEST_ID_HEADER
            )

            enqueue(
                build_row(
                    actor_id=principal.get("id"),
                    actor_email=principal.get("email"),
                    api_key_id=principal.get("api_key_id"),
                    api_key_name=principal.get("api_key_name"),
                    auth_method=principal.get("auth_method"),
                    action=context.get("action") or inferred_action,
                    resource_type=context.get("resource_type") or inferred_resource,
                    resource_id=context.get("resource_id"),
                    collection_name=context.get("collection_name"),
                    method=method,
                    path=path,
                    route=route,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    request_id=request_id,
                    metadata=metadata,
                    ip=client_ip(request) or client_ip_from_scope(scope),
                    user_agent=request.headers.get("user-agent"),
                )
            )
