from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import FakeSession, user_principal

from bigrag.exceptions import NotFoundError, ServerError, UpstreamError, ValidationError
from bigrag.models.chat import ChatSource
from bigrag.services import chat
from bigrag.services.chat import turn as chat_turn


def _conversation(**overrides):
    base = {
        "id": uuid.uuid4(),
        "owner_id": uuid.UUID(user_principal()["id"]),
        "title": "Hi",
        "collection_name": "docs",
        "model_provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "default_top_k": 5,
        "default_search_mode": "semantic",
        "default_min_score": None,
        "default_rerank": False,
        "system_prompt": "be brief",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _message(**overrides):
    base = {
        "id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "role": "user",
        "content": "hello",
        "status": "complete",
        "error_message": None,
        "model_provider": "openai",
        "model": "gpt-4o-mini",
        "retrieval": {},
        "created_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_safe_chat_error_redacts_keys() -> None:
    exc = Exception("API call failed for sk-abcdef1234567890")
    result = chat._safe_chat_error(exc)
    assert "sk-abcdef1234567890" not in result
    assert "sk-[REDACTED]" in result


def test_safe_chat_error_truncates_at_500() -> None:
    exc = Exception("x" * 1000)
    result = chat._safe_chat_error(exc)
    assert len(result) <= 500


def test_safe_chat_error_uses_validation_error_directly() -> None:
    exc = ValidationError("bad")
    assert chat._safe_chat_error(exc) == "bad"


def test_sse_includes_event_and_data() -> None:
    payload = chat._sse("delta", {"x": 1})
    assert "event: delta" in payload
    assert '"x":1' in payload
    assert payload.endswith("\n\n")


def test_done_sse_returns_done_marker() -> None:
    assert chat._done_sse() == "data: [DONE]\n\n"


def test_as_uuid_parses_valid_values() -> None:
    target = uuid.uuid4()
    assert chat._as_uuid(target) == target
    assert chat._as_uuid(str(target)) == target


def test_as_uuid_returns_none_for_invalid() -> None:
    assert chat._as_uuid(None) is None
    assert chat._as_uuid("garbage") is None


def test_title_from_message_handles_short_text() -> None:
    assert chat._title_from_message("Hello there") == "Hello there"


def test_title_from_message_truncates_long_text() -> None:
    long = "x" * 200
    title = chat._title_from_message(long)
    assert title.endswith("...")
    assert len(title) <= 80


def test_title_from_message_handles_empty() -> None:
    assert chat._title_from_message("   ") == "New chat"


def test_conversation_response_serializes_fields() -> None:
    conv = _conversation()
    response = chat._conversation_response(conv, message_count=3)
    assert response.id == str(conv.id)
    assert response.message_count == 3
    assert response.collection == "docs"


def test_message_response_parses_sources_and_skips_invalid() -> None:
    valid = {
        "id": "1",
        "text": "hi",
        "score": 0.8,
        "document_id": str(uuid.uuid4()),
    }
    msg = _message(retrieval={"sources": [valid, "not-a-dict", {"missing": "fields"}]})

    response = chat._message_response(msg)

    assert len(response.sources) == 1
    assert response.sources[0].score == 0.8


def test_resolve_provider_defaults_to_openai() -> None:
    assert chat._resolve_provider(None) == "openai"


def test_resolve_provider_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        chat._resolve_provider("claude")


def test_apply_turn_overrides_uses_body_values() -> None:
    conv = _conversation(default_top_k=0, default_search_mode="")
    body = SimpleNamespace(
        model_provider="openai_compatible",
        model="gpt-4o",
        system_prompt="custom",
        temperature=0.2,
        top_k=10,
        search_mode="hybrid",
        min_score=0.4,
        rerank=True,
    )

    chat._apply_turn_overrides(conv, body, {"default_top_k": 5}, default_provider="openai")

    assert conv.model_provider == "openai_compatible"
    assert conv.model == "gpt-4o"
    assert conv.temperature == 0.2
    assert conv.default_top_k == 10


def test_apply_turn_overrides_falls_back_to_collection_defaults() -> None:
    conv = _conversation(default_top_k=0, default_search_mode="")
    body = SimpleNamespace(
        model_provider=None,
        model=None,
        system_prompt=None,
        temperature=None,
        top_k=None,
        search_mode=None,
        min_score=None,
        rerank=None,
    )

    chat._apply_turn_overrides(
        conv,
        body,
        {"default_top_k": 7, "default_search_mode": "hybrid"},
        default_provider="openai",
    )

    assert conv.default_top_k == 7
    assert conv.default_search_mode == "hybrid"


def test_int_or_none_parses_or_returns_none() -> None:
    assert chat._int_or_none(None) is None
    assert chat._int_or_none("5") == 5
    assert chat._int_or_none("abc") is None
    assert chat._int_or_none(7) == 7


def test_context_block_no_sources_returns_placeholder() -> None:
    assert chat._context_block([], 1000) == "(no matching chunks were found)"


def test_context_block_includes_filenames_and_pages() -> None:
    sources = [
        ChatSource(
            id="a",
            text="hello world",
            score=0.9,
            document_filename="doc.pdf",
            page_no=3,
        ),
    ]
    block = chat._context_block(sources, max_context_chars=10_000)
    assert "doc.pdf" in block
    assert "page 3" in block
    assert "hello world" in block


def test_context_block_truncates_at_budget() -> None:
    sources = [ChatSource(id=str(i), text="x" * 2000, score=0.5) for i in range(5)]
    block = chat._context_block(sources, max_context_chars=200)
    assert len(block) < 5000


def test_model_messages_includes_system_and_context_and_history() -> None:
    sources = [ChatSource(id="1", text="context", score=0.5)]
    prior = [
        _message(role="user", content="hi"),
        _message(role="tool", content="should be skipped"),
        _message(role="assistant", content="hello"),
    ]

    messages = chat._model_messages(
        system_prompt="be brief",
        collection="docs",
        sources=sources,
        prior_messages=prior,
        user_message="follow up",
        max_context_chars=1000,
    )

    assert messages[0]["role"] == "system"
    assert messages[1]["content"].startswith("Retrieved context")
    assert messages[-1] == {"role": "user", "content": "follow up"}
    roles = [m["role"] for m in messages]
    assert "tool" not in roles


def test_append_credential_skips_blanks() -> None:
    creds: list = []
    chat._append_credential(creds, "  ", "saved chat key")
    chat._append_credential(creds, None, "saved chat key")
    assert creds == []


def test_append_credential_rejects_encrypted_value() -> None:
    from bigrag.services import crypto

    creds: list = []
    with pytest.raises(ServerError):
        chat._append_credential(creds, f"{crypto._FERNET_PREFIX}abc", "saved chat key")


def test_append_credential_deduplicates() -> None:
    creds: list = []
    chat._append_credential(creds, "sk-1", "request")
    chat._append_credential(creds, "sk-1", "fallback")
    assert len(creds) == 1


def test_should_try_next_credential_only_when_more_remain() -> None:
    creds = [
        chat.ProviderCredential(api_key="a", source="x"),
        chat.ProviderCredential(api_key="b", source="y"),
    ]
    prepared = SimpleNamespace(credentials=creds)
    auth_exc = SimpleNamespace(status_code=401)

    assert chat._should_try_next_credential(auth_exc, prepared, creds[0]) is True
    assert chat._should_try_next_credential(auth_exc, prepared, creds[1]) is False


def test_should_try_next_credential_returns_false_on_non_auth_error() -> None:
    creds = [
        chat.ProviderCredential(api_key="a", source="x"),
        chat.ProviderCredential(api_key="b", source="y"),
    ]
    prepared = SimpleNamespace(credentials=creds)
    other_exc = Exception("network down")

    assert chat._should_try_next_credential(other_exc, prepared, creds[0]) is False


def test_is_provider_auth_error_detects_status_and_message() -> None:
    exc1 = SimpleNamespace(status_code=401)
    exc2 = Exception("Server returned invalid_api_key")
    exc3 = Exception("rate limited")

    assert chat._is_provider_auth_error(exc1) is True
    assert chat._is_provider_auth_error(exc2) is True
    assert chat._is_provider_auth_error(exc3) is False


def test_provider_error_uses_special_message_for_saved_key() -> None:
    exc = SimpleNamespace(status_code=401)
    cred = chat.ProviderCredential(api_key="x", source="saved chat key")
    error = chat._provider_error(exc, cred)
    assert "cleared" in str(error)
    assert isinstance(error, UpstreamError)


def test_provider_error_uses_request_specific_message() -> None:
    exc = SimpleNamespace(status_code=401)
    cred = chat.ProviderCredential(api_key="x", source="request")
    error = chat._provider_error(exc, cred)
    assert "request" in str(error)


def test_is_saved_key_auth_error_only_for_upstream() -> None:
    saved = UpstreamError("OpenAI rejected the saved chat key. ...")
    assert chat._is_saved_key_auth_error(saved) is True
    assert chat._is_saved_key_auth_error(Exception("nope")) is False
    assert chat._is_saved_key_auth_error(UpstreamError("other")) is False


@pytest.mark.anyio
async def test_list_conversations_returns_paginated() -> None:
    user = user_principal()
    conv = _conversation()
    session = FakeSession(
        execute_values=[[(conv, 2, datetime.now(UTC))]],
        scalar_values=[1],
    )

    result = await chat.list_conversations(session, user, limit=10, offset=0)

    assert result.total == 1
    assert result.conversations[0].id == str(conv.id)


@pytest.mark.anyio
async def test_get_conversation_detail_raises_when_missing() -> None:
    user = user_principal()
    session = FakeSession(scalar_values=[None])

    with pytest.raises(NotFoundError):
        await chat.get_conversation_detail(session, user, uuid.uuid4())


@pytest.mark.anyio
async def test_get_conversation_detail_returns_messages() -> None:
    user = user_principal()
    conv = _conversation(owner_id=uuid.UUID(user["id"]))
    msg = _message(conversation_id=conv.id, content="hi")
    session = FakeSession(scalar_values=[conv], scalars_values=[[msg]])

    conversation, messages = await chat.get_conversation_detail(session, user, conv.id)

    assert conversation.id == str(conv.id)
    assert len(messages) == 1


@pytest.mark.anyio
async def test_update_conversation_title_persists_change() -> None:
    user = user_principal()
    conv = _conversation(owner_id=uuid.UUID(user["id"]))
    session = FakeSession(scalar_values=[conv])

    await chat.update_conversation_title(session, user, conv.id, "  Renamed  ")

    assert conv.title == "Renamed"
    assert session.commits == 1


@pytest.mark.anyio
async def test_delete_conversation_removes_row() -> None:
    user = user_principal()
    conv = _conversation(owner_id=uuid.UUID(user["id"]))
    session = FakeSession(scalar_values=[conv])

    await chat.delete_conversation(session, user, conv.id)

    assert conv in session.deleted
    assert session.commits == 1


@pytest.mark.anyio
async def test_recent_history_limit_zero_returns_empty() -> None:
    session = FakeSession()
    result = await chat._recent_history(session, uuid.uuid4(), 0)
    assert result == []


@pytest.mark.anyio
async def test_recent_history_reverses_order() -> None:
    newest = _message(content="3", created_at=datetime(2026, 5, 9, 3, tzinfo=UTC))
    oldest = _message(content="1", created_at=datetime(2026, 5, 9, 1, tzinfo=UTC))
    session = FakeSession(scalars_values=[[newest, oldest]])

    result = await chat._recent_history(session, uuid.uuid4(), 5)

    assert [m.content for m in result] == ["1", "3"]


@pytest.mark.anyio
async def test_resolve_base_url_returns_none_when_empty() -> None:
    assert await chat._resolve_base_url(None, None) is None


@pytest.mark.anyio
async def test_resolve_base_url_validates(monkeypatch) -> None:
    async def fake_validate(value):
        return value

    monkeypatch.setattr(chat_turn, "validate_chat_base_url", fake_validate)
    result = await chat._resolve_base_url("https://api.example.com", None)
    assert result == "https://api.example.com"


@pytest.mark.anyio
async def test_resolve_base_url_wraps_unsafe_error(monkeypatch) -> None:
    from bigrag.services.url_security import UnsafeOutboundUrlError

    async def fake_validate(_value):
        raise UnsafeOutboundUrlError("blocked")

    monkeypatch.setattr(chat_turn, "validate_chat_base_url", fake_validate)
    with pytest.raises(ValidationError):
        await chat._resolve_base_url("https://internal", None)


@pytest.mark.anyio
async def test_clear_saved_chat_key_skips_when_no_data() -> None:
    user = user_principal()
    session = FakeSession(scalar_values=[None])

    await chat._clear_saved_chat_key(session, user)

    assert session.commits == 0


@pytest.mark.anyio
async def test_clear_saved_chat_key_removes_entry() -> None:
    user = user_principal()
    data = {"chat": {"openai_key": "saved", "other": "keep"}, "outside": "untouched"}
    session = FakeSession(scalar_values=[data])

    await chat._clear_saved_chat_key(session, user)

    assert session.commits == 1


@pytest.mark.anyio
async def test_resolve_api_credentials_uses_request_key_when_present() -> None:
    user = user_principal()
    body = SimpleNamespace(provider_api_key="sk-from-request")
    session = FakeSession()

    result = await chat._resolve_api_credentials(session, user, body)
    assert result == [chat.ProviderCredential(api_key="sk-from-request", source="request")]


@pytest.mark.anyio
async def test_resolve_api_credentials_uses_saved_key(monkeypatch) -> None:
    user = user_principal()
    body = SimpleNamespace(provider_api_key=None)
    session = FakeSession(scalar_values=[{"chat": {"openai_key": "sk-saved"}}])
    monkeypatch.setattr(chat_turn, "decrypt_preferences", lambda data: data)

    result = await chat._resolve_api_credentials(session, user, body)
    assert result[0].source == "saved chat key"


@pytest.mark.anyio
async def test_resolve_api_credentials_raises_when_no_key(monkeypatch) -> None:
    user = user_principal()
    body = SimpleNamespace(provider_api_key=None)
    session = FakeSession(scalar_values=[None])
    monkeypatch.setattr(chat_turn, "decrypt_preferences", lambda data: {})

    with pytest.raises(ValidationError):
        await chat._resolve_api_credentials(session, user, body)
