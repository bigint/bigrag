from __future__ import annotations

import asyncio
import io
import zipfile

import httpx
import pytest
from starlette.requests import Request

from bigrag.services import (
    client_ip,
    credential_check,
    file_validation,
    metadata_schema,
    redis_cache,
)
from bigrag.services.url_security import UnsafeOutboundUrlError


class FakeAsyncClient:
    def __init__(self, responses=None, exc=None) -> None:
        self.responses = list(responses or [])
        self.exc = exc
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers):
        self.requests.append(("GET", url, headers, None))
        if self.exc:
            raise self.exc
        return self.responses.pop(0)

    async def post(self, url, headers, json):
        self.requests.append(("POST", url, headers, json))
        if self.exc:
            raise self.exc
        return self.responses.pop(0)


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.expired = []
        self.deleted = []
        self.count = 0

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value
        self.expired.append((key, ex))

    async def delete(self, key):
        self.deleted.append(key)
        self.values.pop(key, None)

    async def scan_iter(self, pattern):
        for key in list(self.values):
            if key.startswith(pattern.rstrip("*")):
                yield key

    async def incr(self, key):
        self.count += 1
        self.values[key] = self.count
        return self.count

    async def expire(self, key, ttl):
        self.expired.append((key, ttl))

    async def ttl(self, key):
        return 7

    async def aclose(self):
        self.closed = True


def zip_bytes(files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return out.getvalue()


def test_metadata_schema_validates_types_constraints_and_errors() -> None:
    schema = {
        "type": "object",
        "required": ["tenant"],
        "properties": {
            "tenant": {"type": "string", "pattern": r"[a-z]+", "minLength": 2, "maxLength": 5},
            "count": {"type": "integer", "minimum": 1, "maximum": 3},
            "enabled": {"type": "boolean", "enum": [True]},
            "tags": {"type": "array"},
            "payload": {"type": "object"},
        },
    }

    metadata_schema.validate(
        {"tenant": "acme", "count": 2, "enabled": True, "tags": [], "payload": {}},
        schema,
    )

    invalid_cases = [
        ({}, "missing required"),
        ({"tenant": "a"}, "at least"),
        ({"tenant": "toolong"}, "at most"),
        ({"tenant": "AC"}, "pattern"),
        ({"tenant": "ok", "count": True}, "integer"),
        ({"tenant": "ok", "count": 0}, ">= 1"),
        ({"tenant": "ok", "count": 4}, "<= 3"),
        ({"tenant": "ok", "enabled": False}, "one of"),
    ]
    for metadata, message in invalid_cases:
        with pytest.raises(ValueError, match=message):
            metadata_schema.validate(metadata, schema)

    with pytest.raises(ValueError, match="Top-level"):
        metadata_schema.validate({}, {"type": "array"})
    with pytest.raises(ValueError, match="Unknown schema type"):
        metadata_schema.validate({"x": "y"}, {"properties": {"x": {"type": "strang"}}})


def test_file_validation_checks_magic_bytes_and_archives(monkeypatch) -> None:
    file_validation.validate_upload(b"%PDF-1.7", ".pdf")
    file_validation.validate_upload(zip_bytes({"doc.txt": b"hello"}), ".docx")
    file_validation.validate_upload(b"anything", ".txt")

    with pytest.raises(file_validation.InvalidFileContentError, match="declared extension"):
        file_validation.validate_upload(b"not-pdf", ".pdf")
    with pytest.raises(file_validation.InvalidFileContentError, match="Not a valid"):
        file_validation.validate_upload(b"PK\x03\x04not-zip", ".docx")

    monkeypatch.setattr(file_validation, "MAX_DECOMPRESSED_BYTES", 3)
    with pytest.raises(file_validation.InvalidFileContentError, match="Archive too large"):
        file_validation.validate_upload(zip_bytes({"big.txt": b"hello"}), ".docx")


def test_credential_check_maps_provider_responses(monkeypatch) -> None:
    async def run() -> None:
        client = FakeAsyncClient([httpx.Response(200)])
        monkeypatch.setattr(credential_check, "_build_client", lambda timeout: client)
        await credential_check.verify_provider_credentials("openai", "key", None)
        assert client.requests[0][1] == "https://api.openai.com/v1/models"

        statuses = [
            (401, "INVALID_KEY"),
            (403, "INVALID_KEY"),
            (404, "NOT_FOUND"),
            (500, "PROVIDER_ERROR"),
        ]
        for status, code in statuses:
            monkeypatch.setattr(
                credential_check,
                "_build_client",
                lambda timeout, status=status: FakeAsyncClient([httpx.Response(status)]),
            )
            with pytest.raises(credential_check.CredentialCheckError) as exc:
                await credential_check.verify_provider_credentials("cohere", "key", None)
            assert exc.value.code == code

        monkeypatch.setattr(
            credential_check,
            "_build_client",
            lambda timeout: FakeAsyncClient(exc=httpx.TimeoutException("timeout")),
        )
        with pytest.raises(credential_check.CredentialCheckError) as exc:
            await credential_check.verify_provider_credentials("openai", "key", None)
        assert exc.value.code == "TIMEOUT"

        monkeypatch.setattr(
            credential_check,
            "_build_client",
            lambda timeout: FakeAsyncClient(exc=httpx.ConnectError("nope")),
        )
        with pytest.raises(credential_check.CredentialCheckError) as exc:
            await credential_check.verify_provider_credentials("openai", "key", None)
        assert exc.value.code == "UNREACHABLE"

        async def unsafe(value):
            raise UnsafeOutboundUrlError("unsafe")

        monkeypatch.setattr(credential_check, "validate_embedding_base_url", unsafe)
        with pytest.raises(credential_check.CredentialCheckError) as exc:
            await credential_check.verify_provider_credentials(
                "openai_compatible", "key", "http://x"
            )
        assert exc.value.code == "UNSAFE_BASE_URL"

        with pytest.raises(credential_check.CredentialCheckError) as exc:
            await credential_check.verify_provider_credentials("openai_compatible", "key", None)
        assert exc.value.code == "MISSING_BASE_URL"

    asyncio.run(run())


def test_credential_check_voyage_payload_and_error_detail(monkeypatch) -> None:
    async def run() -> None:
        client = FakeAsyncClient([httpx.Response(200)])
        monkeypatch.setattr(credential_check, "_build_client", lambda timeout: client)
        await credential_check.verify_provider_credentials(
            "voyage",
            "key",
            None,
            model="voyage-law-2",
        )
        assert client.requests[0] == (
            "POST",
            "https://api.voyageai.com/v1/embeddings",
            {"Authorization": "Bearer key", "Content-Type": "application/json"},
            {"input": ["ping"], "model": "voyage-law-2"},
        )

        response = httpx.Response(400, json={"error": {"message": "bad model"}})
        monkeypatch.setattr(
            credential_check,
            "_build_client",
            lambda timeout: FakeAsyncClient([response]),
        )
        with pytest.raises(credential_check.CredentialCheckError) as exc:
            await credential_check.verify_provider_credentials("voyage", "key", None)
        assert exc.value.code == "PROVIDER_ERROR"
        assert "bad model" in exc.value.message

        assert credential_check._voyage_error_detail(httpx.Response(400, text="not-json")) == ""

    asyncio.run(run())


def test_redis_cache_plaintext_operations(monkeypatch) -> None:
    async def run() -> None:
        redis = FakeRedis()
        monkeypatch.setattr(redis_cache.crypto, "is_configured", lambda: False)
        monkeypatch.setattr(redis_cache, "_redis", redis)

        await redis_cache.set("a", {"ok": True}, ttl=5)
        assert await redis_cache.get("a") == {"ok": True}
        await redis_cache.delete("a")
        assert redis.deleted == ["bigrag:cache:a"]

        await redis_cache.set("prefix:1", [1], ttl=5)
        await redis_cache.set("prefix:2", [2], ttl=5)
        assert await redis_cache.delete_pattern("prefix:*") == 2

        redis.values["bigrag:cache:bad"] = b"{"
        assert await redis_cache.get("bad") is None

        await redis_cache.close()
        assert redis_cache.get_redis() is None

    asyncio.run(run())


def test_client_ip_respects_trusted_forwarded_chain(monkeypatch) -> None:
    monkeypatch.setattr(
        client_ip.runtime_settings,
        "sync_value",
        lambda key: ["10.0.0.0/8"] if key == "trusted_proxies" else None,
    )
    monkeypatch.setattr(client_ip._config.settings, "trusted_proxies", [])

    assert client_ip.is_trusted_proxy("10.1.2.3") is True
    assert client_ip.is_trusted_proxy("203.0.113.1") is False
    assert (
        client_ip.client_ip_from_scope(
            {
                "client": ("10.1.2.3", 123),
                "headers": [(b"x-forwarded-for", b"198.51.100.5, 10.1.2.3")],
            }
        )
        == "198.51.100.5"
    )
    assert (
        client_ip.client_ip_from_scope(
            {"client": ("203.0.113.1", 123), "headers": [(b"x-forwarded-for", b"198.51.100.5")]}
        )
        == "203.0.113.1"
    )
    assert client_ip.client_ip_from_scope({"headers": []}) is None

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"198.51.100.9")],
            "client": ("10.1.2.3", 123),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    assert client_ip.client_ip(request) == "198.51.100.9"
