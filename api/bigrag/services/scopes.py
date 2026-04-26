"""API-key scope resolution.

Scopes are strings of the form ``resource:action``. A key carrying
``['collection:read', 'document:upload']`` may list collections and
upload documents, nothing else. Wildcards cut the tedium:
``collection:*`` means all actions on collections, ``*:*`` is legacy
full-access, ``*:read`` grants read on everything.

A key with **no** scopes (the pre-cluster default) is treated as
full-access so existing keys don't break when this rolls out.
"""

from __future__ import annotations

# Minimum scopes required per endpoint pattern. Middleware walks this
# list in order and the first match wins. Leave legacy endpoints off
# the list to grant them to every key.
# Specific paths first — first match wins, so nested endpoints must
# appear before their containing prefix.
_ENDPOINT_SCOPES: list[tuple[str, str, str]] = [
    ("POST", "/v1/collections/{name}/query", "query:read"),
    ("POST", "/v1/query", "query:read"),
    ("POST", "/v1/batch/query", "query:read"),
    ("POST", "/v1/collections/{name}/documents/batch/upload", "document:upload"),
    ("POST", "/v1/collections/{name}/documents/batch/status", "document:read"),
    ("POST", "/v1/collections/{name}/documents/batch/get", "document:read"),
    ("POST", "/v1/collections/{name}/documents/batch/delete", "document:delete"),
    ("POST", "/v1/collections/{name}/documents", "document:upload"),
    ("GET", "/v1/collections/{name}/documents", "document:read"),
    ("DELETE", "/v1/collections/{name}/documents", "document:delete"),
    ("POST", "/v1/collections/{name}/reembed", "collection:write"),
    ("POST", "/v1/collections/{name}/truncate", "collection:delete"),
    ("GET", "/v1/documents/{id}/chunks", "document:read"),
    ("GET", "/v1/documents/{id}", "document:read"),
    ("GET", "/v1/documents/", "document:read"),
    ("POST", "/v1/admin/webhooks", "webhook:write"),
    ("GET", "/v1/admin/webhooks", "webhook:read"),
    ("GET", "/v1/usage", "audit:read"),
    ("GET", "/v1/admin/audit", "audit:read"),
    # Collection CRUD — generic, must come AFTER nested endpoints above.
    ("POST", "/v1/collections", "collection:write"),
    ("PUT", "/v1/collections/", "collection:write"),
    ("DELETE", "/v1/collections/", "collection:delete"),
    ("GET", "/v1/collections", "collection:read"),
]


def required_scope(method: str, path: str) -> str | None:
    """Return the scope needed for ``(method, path)``, or None if the
    endpoint is unscoped (available to every authenticated caller)."""
    for rule_method, prefix, scope in _ENDPOINT_SCOPES:
        if rule_method != method:
            continue
        if _path_matches(path, prefix):
            return scope
    return None


def _path_matches(path: str, pattern: str) -> bool:
    if "{" not in pattern:
        return path.startswith(pattern)
    p_parts = pattern.rstrip("/").split("/")
    a_parts = path.rstrip("/").split("/")
    if len(a_parts) < len(p_parts):
        return False
    for pp, ap in zip(p_parts, a_parts, strict=False):
        if pp.startswith("{") and pp.endswith("}"):
            continue
        if pp != ap:
            return False
    return True


def scope_matches(granted: str, required: str) -> bool:
    """Does ``granted`` (one entry from the key's scope list) satisfy
    ``required`` (one endpoint demand)?"""
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
    """True if the key carrying ``granted_scopes`` has ``required``.

    A caller with no scopes defined (``None`` or empty list) is treated
    as full-access — that matches the pre-scope behaviour so existing
    keys keep working after the migration.
    """
    if not granted_scopes:
        return True
    return any(scope_matches(g, required) for g in granted_scopes)


def validate_scope_string(s: str) -> None:
    """Raise ValueError if ``s`` isn't a well-formed scope string."""
    from bigrag.models.auth import VALID_ACTIONS, VALID_RESOURCES

    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(f"Scope must be 'resource:action', got {s!r}")
    resource, action = parts
    if resource not in VALID_RESOURCES:
        raise ValueError(f"Unknown scope resource {resource!r}. Valid: {sorted(VALID_RESOURCES)}")
    if action not in VALID_ACTIONS:
        raise ValueError(f"Unknown scope action {action!r}. Valid: {sorted(VALID_ACTIONS)}")
