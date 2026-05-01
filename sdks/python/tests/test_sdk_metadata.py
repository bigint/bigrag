from __future__ import annotations

import asyncio
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

from bigrag._core import USER_AGENT

from bigrag import BigRAG, __version__

CALVER_RE = re.compile(r"^[0-9]{4}\.[1-9][0-9]?\.[1-9][0-9]?$")


def test_version_is_calver_and_matches_project_metadata() -> None:
    with open("pyproject.toml", "rb") as f:
        metadata = tomllib.load(f)

    assert CALVER_RE.match(__version__)
    assert metadata["project"]["version"] == __version__
    assert USER_AGENT == f"bigrag-python/{__version__}"


def test_client_exposes_current_resource_namespaces() -> None:
    client = BigRAG(api_key="test")
    try:
        assert client.collections is not None
        assert client.documents is not None
        assert client.queries is not None
        assert client.vectors is not None
        assert client.webhooks is not None
        assert client.auth is not None
        assert client.admin.users is not None
        assert client.admin.api_keys is not None
        assert client.admin.audit is not None
        assert client.admin.embedding_presets is not None
        assert client.admin.mcp_servers is not None
        assert client.evaluations is not None
    finally:
        asyncio.run(client.aclose())
