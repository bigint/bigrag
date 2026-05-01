from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PlaygroundMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=200_000)


class PlaygroundChatRequest(BaseModel):
    model: str = Field(default="gpt-4o-mini", min_length=1, max_length=100)
    messages: list[PlaygroundMessage] = Field(min_length=1, max_length=20)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    @model_validator(mode="after")
    def cap_prompt_size(self) -> PlaygroundChatRequest:
        total_chars = sum(len(message.content) for message in self.messages)
        if total_chars > 250_000:
            raise ValueError("Playground prompt is too large")
        return self
