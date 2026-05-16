from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import FakeSession, user_principal

from bigrag.db.models import InstanceSetting
from bigrag.exceptions import ServerError, UpstreamError, ValidationError
from bigrag.models.chat import ChatQuestionSuggestionsRequest, ChatQuestionSuggestionsResponse, ChatSource
from bigrag.routers import chat as chat_router
from bigrag.services import chat
from bigrag.services.chat import questions as chat_questions
from bigrag.services.chat import turn as chat_turn


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


def test_chat_message_response_parses_sources_and_skips_invalid() -> None:
    valid = {
        "id": "1",
        "text": "hi",
        "score": 0.8,
        "document_id": str(uuid.uuid4()),
    }

    response = chat._chat_message_response(
        id=str(uuid.uuid4()),
        role="assistant",
        content="answer",
        retrieval={"sources": [valid, "not-a-dict", {"missing": "fields"}]},
        created_at=datetime.now(UTC),
    )

    assert len(response.sources) == 1
    assert response.sources[0].score == 0.8


def test_resolve_provider_defaults_to_openai() -> None:
    assert chat._resolve_provider(None) == "openai"


def test_resolve_provider_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        chat._resolve_provider("claude")


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


def test_model_messages_includes_system_context_and_current_message() -> None:
    sources = [ChatSource(id="1", text="context", score=0.5)]

    messages = chat._model_messages(
        system_prompt="be brief",
        collection="docs",
        sources=sources,
        user_message="follow up",
        max_context_chars=1000,
    )

    assert messages[0]["role"] == "system"
    assert messages[1]["content"].startswith("Retrieved context")
    assert messages[-1] == {"role": "user", "content": "follow up"}


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


def test_parse_questions_requires_five_clean_questions() -> None:
    expected = [
        "What is the approval flow?",
        "Which document defines receipts?",
        "What exceptions exist?",
        "Who reviews requests?",
        "How should escalation work?",
    ]

    json_text = (
        '{"questions":["What is the approval flow?",'
        '"Which document defines receipts?","What exceptions exist?",'
        '"Who reviews requests?","How should escalation work?"]}'
    )
    line_text = "\n".join(f"{index + 1}. {value}" for index, value in enumerate(expected))

    assert chat._parse_questions(json_text) == expected
    assert chat._parse_questions(line_text) == expected

    with pytest.raises(UpstreamError):
        chat._parse_questions('{"questions":["too few"]}')


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


@pytest.mark.anyio
async def test_get_question_suggestions_reads_instance_setting(monkeypatch) -> None:
    async def get_collection(_name: str) -> dict:
        return {"id": uuid.uuid4(), "name": "docs"}

    generated_at = "2026-05-16T04:45:00+00:00"
    setting = InstanceSetting(key="chat_question_suggestions")
    setting.value = {
        "collections": {
            "docs": {
                "generated_at": generated_at,
                "model": "gpt-4o-mini",
                "questions": ["q1", "q2", "q3", "q4", "q5"],
            }
        }
    }
    session = FakeSession(get_values={"chat_question_suggestions": setting})
    monkeypatch.setattr(chat_questions, "get_collection_or_404", get_collection)

    result = await chat.get_question_suggestions(session, user_principal(), " docs ")

    assert result.collection == "docs"
    assert result.questions == ["q1", "q2", "q3", "q4", "q5"]
    assert result.generated_at == datetime.fromisoformat(generated_at)
    assert result.model == "gpt-4o-mini"


@pytest.mark.anyio
async def test_generate_question_suggestions_uses_saved_key_and_persists(monkeypatch) -> None:
    user = user_principal()
    collection_id = uuid.uuid4()
    document_id = uuid.uuid4()
    document = SimpleNamespace(
        chunk_count=6,
        filename="Handbook.pdf",
        id=document_id,
    )
    session = FakeSession(
        scalar_values=[{"chat": {"openai_key": "sk-playground"}}],
        scalars_values=[[document]],
    )

    async def get_runtime_values(_keys: list[str]) -> dict:
        return {
            "chat_base_url": None,
            "chat_model": "gpt-4o-mini",
            "chat_temperature": 0.2,
        }

    async def get_collection(_name: str) -> dict:
        return {
            "id": collection_id,
            "name": "docs",
            "vector_store_provider": "qdrant",
        }

    async def get_chunks(*_args, **_kwargs) -> tuple[list[dict], int]:
        return (
            [
                {
                    "document_id": str(document_id),
                    "id": "chunk_1",
                    "metadata": {},
                    "text": "Expense approvals require receipts and manager review.",
                }
            ],
            1,
        )

    async def generate_text(**kwargs) -> str:
        assert kwargs["credentials"] == [
            chat.ProviderCredential(api_key="sk-playground", source="saved chat key")
        ]
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["temperature"] == 0.6
        assert kwargs["chunks"][0]["document_filename"] == "Handbook.pdf"
        return (
            '{"questions":["What approval flow is described?",'
            '"Which receipts are required?","Who reviews expenses?",'
            '"What evidence should be cited?","What exceptions are mentioned?"]}'
        )

    monkeypatch.setattr(chat_turn, "decrypt_preferences", lambda data: data)
    monkeypatch.setattr(chat_questions, "get_values", get_runtime_values)
    monkeypatch.setattr(chat_questions, "get_collection_or_404", get_collection)
    monkeypatch.setattr(chat_questions.vector_store, "get_chunks", get_chunks)
    monkeypatch.setattr(chat_questions, "_generate_questions_text", generate_text)

    result = await chat.generate_question_suggestions(
        session,
        user,
        ChatQuestionSuggestionsRequest(collection="docs", model="gpt-4o", temperature=0.6),
    )

    assert result.collection == "docs"
    assert len(result.questions) == 5
    assert result.model == "gpt-4o"
    assert session.commits == 1
    setting = session.added[0]
    saved = setting.value["collections"]["docs"]
    assert saved["questions"] == result.questions
    assert saved["document_ids"] == [str(document_id)]
    assert setting.updated_by == uuid.UUID(user["id"])


def test_question_suggestions_route_uses_specific_handler(route_client, monkeypatch) -> None:
    async def get_suggestions(_session, _user, collection: str) -> ChatQuestionSuggestionsResponse:
        return ChatQuestionSuggestionsResponse(
            collection=collection,
            model="gpt-4o-mini",
            questions=["q1", "q2", "q3", "q4", "q5"],
        )

    monkeypatch.setattr(chat_router, "get_question_suggestions", get_suggestions)

    response = route_client().get("/v1/chat/question-suggestions?collection=docs")

    assert response.status_code == 200
    assert response.json()["collection"] == "docs"
    assert response.json()["questions"] == ["q1", "q2", "q3", "q4", "q5"]
