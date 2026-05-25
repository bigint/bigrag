from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bigrag.db.models import ApiKey

_ENDPOINT_SCOPES: list[tuple[str, str, str]] = [
    ("GET", "/v1/chat/question-suggestions", "chat:read"),
    ("POST", "/v1/chat/question-suggestions", "chat:write"),
    ("POST", "/v1/chat", "chat:write"),
    ("POST", "/v1/collections/{name}/query", "query:read"),
    ("POST", "/v1/query", "query:read"),
    ("POST", "/v1/batch/query", "query:read"),
    ("POST", "/v1/collections/{name}/documents/batch/upload", "document:upload"),
    ("POST", "/v1/collections/{name}/documents/batch/status", "document:read"),
    ("POST", "/v1/collections/{name}/documents/batch/get", "document:read"),
    ("POST", "/v1/collections/{name}/documents/batch/delete", "document:delete"),
    ("POST", "/v1/collections/{name}/upload-sessions/{id}/files", "document:upload"),
    ("POST", "/v1/collections/{name}/upload-sessions/{id}/complete", "document:upload"),
    ("POST", "/v1/collections/{name}/upload-sessions/{id}/cancel", "document:delete"),
    ("POST", "/v1/collections/{name}/upload-sessions", "document:upload"),
    ("GET", "/v1/collections/{name}/upload-sessions/{id}", "document:read"),
    ("POST", "/v1/collections/{name}/documents", "document:upload"),
    ("GET", "/v1/collections/{name}/documents", "document:read"),
    ("GET", "/v1/collections/{name}/documents/{id}", "document:read"),
    ("DELETE", "/v1/collections/{name}/documents/{id}", "document:delete"),
    ("GET", "/v1/collections/{name}/documents/{id}/elements", "document:read"),
    ("GET", "/v1/collections/{name}/documents/{id}/chunks", "document:read"),
    ("POST", "/v1/collections/{name}/truncate", "collection:delete"),
    ("POST", "/v1/collections/{name}/vectors/upsert", "vector:write"),
    ("POST", "/v1/collections/{name}/vectors/delete", "vector:delete"),
    ("GET", "/v1/collections/{name}/analytics", "collection:read"),
    ("GET", "/v1/documents/{id}/chunks", "document:read"),
    ("GET", "/v1/documents/{id}", "document:read"),
    ("GET", "/v1/documents/", "document:read"),
    ("POST", "/v1/evaluation", "query:read"),
    ("POST", "/v1/admin/webhooks", "webhook:write"),
    ("PUT", "/v1/admin/webhooks/{id}", "webhook:write"),
    ("DELETE", "/v1/admin/webhooks/{id}", "webhook:write"),
    ("POST", "/v1/admin/webhooks/{id}/test", "webhook:write"),
    ("POST", "/v1/admin/webhooks/{id}/deliveries/{delivery_id}/replay", "webhook:write"),
    ("GET", "/v1/admin/webhooks", "webhook:read"),
    ("GET", "/v1/admin/webhooks/{id}", "webhook:read"),
    ("GET", "/v1/admin/webhooks/{id}/deliveries", "webhook:read"),
    ("GET", "/v1/usage", "audit:read"),
    ("GET", "/v1/status/overview", "collection:read"),
    ("GET", "/v1/status/collections", "collection:read"),
    ("GET", "/v1/status/usage", "audit:read"),
    ("GET", "/v1/admin/audit", "audit:read"),
    ("GET", "/v1/admin/status/access", "audit:read"),
    ("GET", "/v1/admin/access/overview", "audit:read"),
    ("GET", "/v1/admin/access/logs", "audit:read"),
    ("POST", "/v1/collections", "collection:write"),
    ("PUT", "/v1/collections/", "collection:write"),
    ("DELETE", "/v1/collections/", "collection:delete"),
    ("GET", "/v1/collections", "collection:read"),
]


def required_scope(method: str, path: str) -> str | None:

    for rule_method, prefix, scope in _ENDPOINT_SCOPES:
        if rule_method != method:
            continue
        if _path_matches(path, prefix):
            return scope
    return None


def _path_matches(path: str, pattern: str) -> bool:
    if "{" not in pattern:
        if path == pattern:
            return True
        prefix = pattern.rstrip("/")
        return path.startswith(prefix + "/")
    p_parts = pattern.rstrip("/").split("/")
    a_parts = path.rstrip("/").split("/")
    if len(a_parts) < len(p_parts):
        return False
    if len(a_parts) != len(p_parts):
        return False
    for pp, ap in zip(p_parts, a_parts, strict=False):
        if pp.startswith("{") and pp.endswith("}"):
            continue
        if pp != ap:
            return False
    return True


def scope_matches(granted: str, required: str) -> bool:

    g_res, _, g_act = granted.partition(":")
    r_res, _, r_act = required.partition(":")
    if not g_res or not g_act:
        return False
    if g_res not in ("*", r_res):
        return False
    if g_act not in ("*", r_act):
        return False
    return True


def has_scope(granted_scopes: list[str] | None, required: str) -> bool:

    if not granted_scopes:
        return True
    return any(scope_matches(g, required) for g in granted_scopes)


def is_mcp_key(key: ApiKey | None) -> bool:
    if key is None:
        return False
    permissions = key.permissions or {}
    return isinstance(permissions, dict) and isinstance(permissions.get("mcp"), dict)


def mcp_permissions_filter():
    from bigrag.db.models import ApiKey

    return ApiKey.permissions.op("?")("mcp")


def validate_scope_string(s: str) -> None:

    from bigrag.models.auth import VALID_ACTIONS, VALID_RESOURCES

    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(f"Scope must be 'resource:action', got {s!r}")
    resource, action = parts
    if resource not in VALID_RESOURCES:
        raise ValueError(f"Unknown scope resource {resource!r}. Valid: {sorted(VALID_RESOURCES)}")
    if action not in VALID_ACTIONS:
        raise ValueError(f"Unknown scope action {action!r}. Valid: {sorted(VALID_ACTIONS)}")
