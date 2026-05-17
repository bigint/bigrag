from __future__ import annotations

import json
import re
from types import SimpleNamespace

from bigrag.db.models import Document
from bigrag.exceptions import UpstreamError
from bigrag.services.chat.provider import (
    _openai_client,
    _provider_error,
    _should_try_next_credential,
)
from bigrag.services.chat.types import ProviderCredential

QUESTION_COUNT = 5
DOCUMENT_LIMIT = 6
CHUNK_LIMIT = 4
CHUNK_CHARS = 900


async def generate_questions_text(
    *,
    model: str,
    temperature: float,
    credentials: list[ProviderCredential],
    base_url: str | None,
    collection_name: str,
    documents: list[Document],
    chunks: list[dict],
) -> str:
    try:
        import openai
    except ImportError as exc:
        raise UpstreamError(
            "openai package is required to generate questions",
            public_message="openai package is required to generate questions",
        ) from exc

    prompt = question_prompt(collection_name, documents, chunks)
    prepared = SimpleNamespace(
        model=model,
        temperature=temperature,
        credentials=credentials,
        base_url=base_url,
    )
    last_error: Exception | None = None
    for credential in credentials:
        client = await _openai_client(openai, prepared, credential)
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate concise, specific test questions for retrieval "
                            "evaluation. Return JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=max(temperature, 0.7),
                response_format={"type": "json_object"},
            )
            choices = getattr(response, "choices", None) or []
            if not choices:
                raise UpstreamError(
                    "Question generation returned no choices",
                    public_message="Question generation returned no choices",
                )
            return getattr(choices[0].message, "content", None) or ""
        except Exception as exc:
            last_error = exc
            if not _should_try_next_credential(exc, prepared, credential):
                raise _provider_error(exc, credential) from exc
    if last_error is not None:
        raise _provider_error(last_error, credentials[-1]) from last_error
    return ""


def question_prompt(collection_name: str, documents: list[Document], chunks: list[dict]) -> str:
    filenames = "\n".join(f"- {document.filename}" for document in documents)
    chunk_lines = "\n\n".join(
        (
            f"[{index + 1}] "
            f"{chunk.get('document_filename') or chunk.get('document_id')}\n"
            f"{str(chunk.get('text') or '')[:CHUNK_CHARS]}"
        )
        for index, chunk in enumerate(chunks[:12])
    )
    shape = '{"questions":["question 1","question 2","question 3","question 4","question 5"]}'
    return (
        f'Collection: "{collection_name}"\n\n'
        f"Ready documents:\n{filenames}\n\n"
        f"Sampled chunks:\n{chunk_lines or '(no chunks available)'}\n\n"
        f"Return exactly this JSON shape: {shape}. "
        "Each question must be answerable from the collection, varied, and useful for "
        "testing retrieval."
    )


def parse_questions(text: str) -> list[str]:
    try:
        raw = json.loads(_json_object_text(text))
        questions = raw.get("questions") if isinstance(raw, dict) else None
    except (json.JSONDecodeError, ValueError):
        questions = _line_questions(text)
    cleaned = _clean_questions(questions or [])
    if len(cleaned) != QUESTION_COUNT:
        raise UpstreamError(
            "Question generation did not return five questions",
            public_message="Question generation did not return five questions",
        )
    return cleaned


def _json_object_text(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("missing JSON object")
    return text[start : end + 1]


def _line_questions(text: str) -> list[str]:
    return [
        re.sub(r"^\s*[-*\d.)]+\s*", "", line).strip() for line in text.splitlines() if line.strip()
    ]


def _clean_questions(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = re.sub(r"\s+", " ", value).strip().strip('"')
        if not cleaned or cleaned in out:
            continue
        out.append(cleaned)
        if len(out) == QUESTION_COUNT:
            break
    return out
