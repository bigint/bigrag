from __future__ import annotations

import time
import uuid
from typing import Any

import orjson
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .chat import canned_response, stream_response
from .embeddings import count_tokens, deterministic_vector

app = FastAPI(title="fake-openai", version="0.1.0")

_DEFAULT_EMBEDDING_DIMS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    now = int(time.time())
    ids = [
        "text-embedding-3-small",
        "text-embedding-3-large",
        "text-embedding-ada-002",
        "gpt-4o-mini",
        "gpt-4o",
    ]
    return {
        "object": "list",
        "data": [
            {"id": model_id, "object": "model", "created": now, "owned_by": "fake-openai"}
            for model_id in ids
        ],
    }


@app.post("/v1/embeddings")
async def embeddings(request: Request) -> JSONResponse:
    body = await request.json()
    model = body.get("model", "text-embedding-3-small")
    raw_input = body.get("input", "")
    dim = int(body.get("dimensions") or _DEFAULT_EMBEDDING_DIMS.get(model, 1536))

    if isinstance(raw_input, str):
        inputs = [raw_input]
    elif isinstance(raw_input, list):
        inputs = [str(x) for x in raw_input]
    else:
        inputs = [str(raw_input)]

    data = [
        {
            "object": "embedding",
            "index": i,
            "embedding": deterministic_vector(text, dim),
        }
        for i, text in enumerate(inputs)
    ]
    total_tokens = sum(count_tokens(text) for text in inputs)
    payload = {
        "object": "list",
        "data": data,
        "model": model,
        "usage": {"prompt_tokens": total_tokens, "total_tokens": total_tokens},
    }
    return JSONResponse(content=payload)


def _completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


def _non_stream_completion(model: str, text: str, prompt_tokens: int) -> dict[str, Any]:
    completion_tokens = max(1, len(text.split()))
    return {
        "id": _completion_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _sse_chunk(payload: dict[str, Any]) -> bytes:
    return b"data: " + orjson.dumps(payload) + b"\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "gpt-4o-mini")
    messages = body.get("messages") or []
    stream = bool(body.get("stream", False))
    response_format = body.get("response_format")
    text = canned_response(messages, response_format=response_format)
    prompt_tokens = sum(count_tokens(str(m.get("content", ""))) for m in messages)

    if not stream:
        return JSONResponse(content=_non_stream_completion(model, text, prompt_tokens))

    completion_id = _completion_id()
    created = int(time.time())

    async def event_stream():
        first = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
            ],
        }
        yield _sse_chunk(first)

        for piece in stream_response(text):
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {"index": 0, "delta": {"content": piece}, "finish_reason": None}
                ],
            }
            yield _sse_chunk(chunk)

        final = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield _sse_chunk(final)
        yield b"data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
