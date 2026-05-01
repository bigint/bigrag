from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterator

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from bigrag.db.models import UserPreference
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_session
from bigrag.models.playground import PlaygroundChatRequest
from bigrag.routers.preferences import decrypt_preferences
from bigrag.services import crypto

logger = get_logger("bigrag.routers.playground")

router = APIRouter(prefix="/v1/playground", tags=["playground"])

_SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, separators=(',', ':'))}\n\n"


def _safe_openai_error(exc: Exception) -> str:
    message = getattr(exc, "message", None) or str(exc) or "OpenAI request failed"
    return _SECRET_RE.sub("sk-[REDACTED]", message)[:500]


async def _get_playground_openai_key(user_id: str, session: AsyncSession) -> str:
    data = await session.scalar(
        sa.select(UserPreference.data).where(UserPreference.user_id == uuid.UUID(user_id))
    )
    prefs = decrypt_preferences(dict(data)) if isinstance(data, dict) else {}
    playground = prefs.get("playground") if isinstance(prefs.get("playground"), dict) else {}
    api_key = playground.get("openai_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise HTTPException(status_code=400, detail="Add an OpenAI API key first")
    if api_key.startswith(crypto._FERNET_PREFIX):
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key cannot be decrypted. Configure BIGRAG_MASTER_KEY.",
        )
    return api_key.strip()


async def _stream_openai_chat(
    body: PlaygroundChatRequest,
    *,
    api_key: str,
) -> AsyncIterator[str]:
    try:
        import openai
    except ImportError:
        yield _sse({"error": "openai package is required for playground chat"})
        return

    client = openai.AsyncOpenAI(api_key=api_key)
    try:
        stream = await client.chat.completions.create(
            model=body.model,
            messages=[message.model_dump() for message in body.messages],
            temperature=body.temperature,
            stream=True,
        )
        async for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0].delta, "content", None)
            if delta:
                yield _sse({"delta": delta})
        yield "data: [DONE]\n\n"
    except Exception as exc:
        logger.warning(
            "playground OpenAI stream failed",
            error=f"{exc.__class__.__name__}: {_safe_openai_error(exc)}",
        )
        yield _sse({"error": _safe_openai_error(exc)})
    finally:
        await client.close()


@router.post("/chat")
async def stream_playground_chat(
    body: PlaygroundChatRequest,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    api_key = await _get_playground_openai_key(user["id"], session)
    return StreamingResponse(
        _stream_openai_chat(body, api_key=api_key),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
