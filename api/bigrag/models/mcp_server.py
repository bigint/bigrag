from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class McpServerBase(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    server_name: str = Field(
        min_length=1,
        max_length=60,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        description="mcpServers object key in the client config; lowercase, alphanumeric + dashes.",
    )
    collection: str | None = Field(
        default=None,
        max_length=80,
        description="Optional collection to pin the server to.",
    )


class UpdateMcpServerRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    server_name: str | None = Field(
        default=None, min_length=1, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$"
    )
    collection: str | None = Field(
        default=None,
        max_length=80,
        description="Empty string clears the scope; a name pins to that collection.",
    )


class McpServerResponse(BaseModel):
    id: str
    title: str
    server_name: str
    collection: str | None = None
    key_prefix: str
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateMcpServerResponse(McpServerResponse):
    api_key: str = Field(description="Plaintext API key — shown once.")


class McpServerListResponse(BaseModel):
    servers: list[McpServerResponse]
    total: int
