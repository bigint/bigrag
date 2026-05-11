from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from rag_computer.db.models import ChatMessage
from rag_computer.exceptions import ServerError, UpstreamError, ValidationError
from rag_computer.models.chat import ChatSource
from rag_computer.services import chat


def run(coro):
    return asyncio.run(coro)


def message(role: str, content: str) -> ChatMessage:
    return ChatMessage(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        role=role,
        content=content,
        status="complete",
        retrieval={},
        created_at=chat.datetime.now(chat.UTC),
    )


def test_safe_chat_error_redacts_secret_and_truncates() -> None:
    error = RuntimeError(f"provider rejected sk-12345678_SECRET {'x' * 600}")

    safe = chat._safe_chat_error(error)

    assert "sk-[REDACTED]" in safe
    assert "sk-12345678_SECRET" not in safe
    assert len(safe) == 500


def test_title_from_message_compacts_and_truncates() -> None:
    assert chat._title_from_message(" \n  ") == "New chat"

    title = chat._title_from_message("  hello   world  " + "x" * 100)

    assert title == "hello world " + ("x" * 65) + "..."
    assert len(title) == 80


def test_provider_resolution_validates_supported_values() -> None:
    assert chat._resolve_provider(" OPENAI_COMPATIBLE ") == "openai_compatible"
    assert chat._resolve_provider(None, None) == "openai"

    with pytest.raises(ValidationError, match="Only openai"):
        chat._resolve_provider("cohere")


def test_append_credential_strips_dedupes_and_rejects_encrypted_values() -> None:
    credentials: list[chat.ProviderCredential] = []

    chat._append_credential(credentials, " sk-live ", "request")
    chat._append_credential(credentials, "sk-live", "saved chat key")
    chat._append_credential(credentials, "", "empty")

    assert credentials == [chat.ProviderCredential(api_key="sk-live", source="request")]

    with pytest.raises(ServerError, match="cannot be decrypted"):
        chat._append_credential(credentials, "gAAAAencrypted", "saved chat key")


def test_model_messages_include_context_and_complete_history_only() -> None:
    sources = [
        ChatSource(
            id="chunk-1",
            text="The answer is in this paragraph.",
            score=0.9,
            document_filename="manual.pdf",
            page_no=3,
        )
    ]

    messages = chat._model_messages(
        system_prompt="Use context",
        collection="docs",
        sources=sources,
        prior_messages=[
            message("system", "ignored"),
            message("user", "previous question"),
            message("assistant", "previous answer"),
        ],
        user_message="current question",
        max_context_chars=50,
    )

    assert messages == [
        {"role": "system", "content": "Use context"},
        {
            "role": "system",
            "content": (
                'Retrieved context from collection "docs":\n\n'
                "[1] (manual.pdf, page 3) The answer is in this paragraph."
            ),
        },
        {"role": "user", "content": "previous question"},
        {"role": "assistant", "content": "previous answer"},
        {"role": "user", "content": "current question"},
    ]


def test_context_block_reports_empty_sources() -> None:
    assert chat._context_block([], 1) == "(no matching chunks were found)"


def test_sources_from_results_resolves_filenames_and_metadata_offsets() -> None:
    document_id = uuid.uuid4()

    class FakeSession:
        async def execute(self, _stmt):
            return [(document_id, "manual.pdf")]

    sources = run(
        chat._sources_from_results(
            FakeSession(),
            [
                {
                    "id": "chunk",
                    "text": "hello",
                    "score": "0.75",
                    "document_id": str(document_id),
                    "chunk_index": "2",
                    "metadata": {"page_no": "4", "char_start": "10", "char_end": "15"},
                    "embedding": [0.1],
                },
                {"text": None, "score": None, "document_id": "not-a-uuid", "metadata": []},
            ],
        )
    )

    assert sources[0].document_filename == "manual.pdf"
    assert sources[0].page_no == 4
    assert sources[0].char_start == 10
    assert sources[0].char_end == 15
    assert sources[0].metadata == {"page_no": "4", "char_start": "10", "char_end": "15"}
    assert sources[1].id == "2"
    assert sources[1].text == ""
    assert sources[1].metadata == {}


def test_provider_error_maps_auth_failures_by_credential_source() -> None:
    auth_error = SimpleNamespace(status_code=401)

    saved = chat._provider_error(
        auth_error,
        chat.ProviderCredential(api_key="sk", source="saved chat key"),
    )
    request = chat._provider_error(
        auth_error,
        chat.ProviderCredential(api_key="sk", source="request"),
    )

    assert isinstance(saved, UpstreamError)
    assert chat._is_saved_key_auth_error(saved) is True
    assert str(saved).startswith("OpenAI rejected the saved chat key")
    assert str(request) == (
        "OpenAI rejected the request. Use a fresh key generated from the OpenAI API keys page."
    )


def test_should_try_next_credential_only_for_nonfinal_auth_errors() -> None:
    credentials = [
        chat.ProviderCredential(api_key="bad", source="saved chat key"),
        chat.ProviderCredential(api_key="good", source="request"),
    ]
    prepared = SimpleNamespace(credentials=credentials)
    auth_error = SimpleNamespace(status_code=401)

    assert chat._should_try_next_credential(auth_error, prepared, credentials[0]) is True
    assert chat._should_try_next_credential(auth_error, prepared, credentials[1]) is False
    assert chat._should_try_next_credential(RuntimeError("boom"), prepared, credentials[0]) is False


def test_clear_saved_chat_key_removes_key_when_preferences_exist() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.executed = []
            self.commits = 0

        async def scalar(self, _stmt):
            return {"chat": {"openai_key": "sk-old", "model": "gpt"}, "theme": "dark"}

        async def execute(self, stmt):
            self.executed.append(stmt)

        async def commit(self) -> None:
            self.commits += 1

    session = FakeSession()

    run(chat._clear_saved_chat_key(session, {"id": str(uuid.uuid4())}))

    assert len(session.executed) == 1
    assert session.commits == 1
