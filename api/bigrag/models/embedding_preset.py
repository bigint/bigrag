from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateEmbeddingPresetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    provider: str = Field(pattern=r"^(openai|openai_compatible|cohere|voyage)$")
    model: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=1)
    base_url: str | None = Field(default=None, max_length=500)
    dimension: int = Field(ge=64, le=4096)


class UpdateEmbeddingPresetRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    provider: str | None = Field(
        default=None,
        pattern=r"^(openai|openai_compatible|cohere|voyage)$",
    )
    model: str | None = Field(default=None, min_length=1, max_length=120)
    api_key: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, max_length=500)
    dimension: int | None = Field(default=None, ge=64, le=4096)


class TestEmbeddingPresetRequest(BaseModel):
    provider: str = Field(pattern=r"^(openai|openai_compatible|cohere|voyage)$")
    model: str = Field(min_length=1, max_length=120)
    api_key: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, max_length=500)


class EmbeddingPresetResponse(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    base_url: str | None = None
    dimension: int
    has_api_key: bool
    created_at: datetime
    updated_at: datetime


class EmbeddingPresetListResponse(BaseModel):
    presets: list[EmbeddingPresetResponse]
    total: int
