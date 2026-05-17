from __future__ import annotations

import json
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


def _wants_json(response_format: object) -> bool:
    if not isinstance(response_format, dict):
        return False
    fmt_type = response_format.get("type")
    return fmt_type in {"json_object", "json_schema"}


def _json_response_for(messages: list[dict]) -> str:
    """Pick a deterministic JSON shape based on what the prompt asks for.

    bigRAG's chat-suggestions service asks for `{"questions":[...5 strings...]}`.
    Default to that shape; anything else is unused today.
    """
    blob = " ".join(str(m.get("content", "")) for m in messages).lower()
    if "questions" in blob or "question" in blob:
        return json.dumps(
            {
                "questions": [
                    "What is described in the documents?",
                    "Which key facts appear most often?",
                    "Who is referenced in the source material?",
                    "What dates or numbers are mentioned?",
                    "What are the main conclusions?",
                ]
            }
        )
    return json.dumps({"result": "ok"})


def canned_response(messages: list[dict], response_format: object = None) -> str:
    if _wants_json(response_format):
        return _json_response_for(messages)
    last = _last_user_message(messages).strip() or "your question"
    return f"Based on the provided context, {last} (answered by fake-openai)."


def stream_response(text: str, chunk_size: int = 5) -> Iterator[str]:
    """Yield text in ~chunk_size-character pieces to mimic OpenAI SSE chunks."""
    if not text:
        yield ""
        return
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
