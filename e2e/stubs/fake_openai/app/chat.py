from __future__ import annotations

from collections.abc import Iterator


def _last_user_message(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                parts = [p.get("text", "") for p in content if isinstance(p, dict)]
                return " ".join(p for p in parts if p)
            return str(content)
    return ""


def canned_response(messages: list[dict]) -> str:
    last = _last_user_message(messages).strip() or "your question"
    return f"Based on the provided context, {last} (answered by fake-openai)."


def stream_response(text: str, chunk_size: int = 5) -> Iterator[str]:
    """Yield text in ~chunk_size-character pieces to mimic OpenAI SSE chunks."""
    if not text:
        yield ""
        return
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
