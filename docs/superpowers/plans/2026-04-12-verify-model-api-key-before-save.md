# Verify Model API Key Before Save — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject `POST /v1/admin/embedding-presets` when the supplied API key cannot authenticate against the provider's `/models` endpoint, so bad keys never reach the database.

**Architecture:** New `verify_provider_credentials()` helper in `bigrag.services.credential_check` runs inside the `create_preset` handler before the INSERT. On failure, the handler raises a 422 with a typed `{code, message}` body. Studio's preset form turns the submit button into "Verifying…" during the call and shows an inline error on the API Key field when the server returns `code=INVALID_KEY`.

**Tech Stack:** Python 3.11 / FastAPI / httpx (`httpx.MockTransport` for tests, no new deps) / pytest-asyncio. Next.js 16 / React / `ky` HTTP client / Sonner toasts.

---

## File Structure

**Create:**
- `api/bigrag/services/credential_check.py` — module with `CredentialCheckError` + `verify_provider_credentials()`
- `api/tests/test_credential_check.py` — unit tests using `httpx.MockTransport`
- `api/tests/test_embedding_presets.py` — router integration tests

**Modify:**
- `api/bigrag/routers/embedding_presets.py:62-86` — call `verify_provider_credentials()` before INSERT
- `api/tests/conftest.py:382-383` — patch `bigrag.routers.embedding_presets.db` in the `client` fixture
- `app/src/lib/api.ts:10-26` — extract `detail.code` when error `detail` is an object
- `app/src/app/(dashboard)/models/components/preset-form.tsx` — "Verifying…" label + inline INVALID_KEY error
- `website/content/docs/api-reference/embedding-presets.mdx` — document the new 422 error codes
- `website/content/docs/concepts/embeddings.mdx` — note that `POST` verifies keys, `PATCH` does not

---

## Task 1: Credential-check module (TDD)

**Files:**
- Create: `api/bigrag/services/credential_check.py`
- Test: `api/tests/test_credential_check.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_credential_check.py`:

```python
"""Unit tests for bigrag.services.credential_check."""

from __future__ import annotations

import httpx
import pytest

from bigrag.services.credential_check import (
    CredentialCheckError,
    verify_provider_credentials,
)


def _mock_client(status_code: int | None = None, exc: Exception | None = None):
    """Returns a factory for httpx.AsyncClient that responds with a canned status or raises."""

    def handler(request: httpx.Request) -> httpx.Response:
        if exc is not None:
            raise exc
        assert status_code is not None
        return httpx.Response(status_code, json={"data": []})

    transport = httpx.MockTransport(handler)
    return transport


async def test_openai_200_returns_none(monkeypatch):
    transport = _mock_client(status_code=200)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    # Should not raise
    await verify_provider_credentials(
        provider="openai", api_key="sk-good", base_url=None
    )


async def test_openai_custom_base_url_200(monkeypatch):
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    await verify_provider_credentials(
        provider="openai",
        api_key="sk-good",
        base_url="https://ollama.example.com/v1",
    )
    assert seen["url"] == "https://ollama.example.com/v1/models"


async def test_401_raises_invalid_key(monkeypatch):
    transport = _mock_client(status_code=401)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-bad", base_url=None
        )
    assert exc.value.code == "INVALID_KEY"


async def test_403_raises_invalid_key(monkeypatch):
    transport = _mock_client(status_code=403)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-bad", base_url=None
        )
    assert exc.value.code == "INVALID_KEY"


async def test_404_raises_not_found(monkeypatch):
    transport = _mock_client(status_code=404)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai",
            api_key="sk-good",
            base_url="https://self-hosted.example.com/v1",
        )
    assert exc.value.code == "NOT_FOUND"


async def test_503_raises_provider_error(monkeypatch):
    transport = _mock_client(status_code=503)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-good", base_url=None
        )
    assert exc.value.code == "PROVIDER_ERROR"
    assert "503" in exc.value.message


async def test_connect_error_raises_unreachable(monkeypatch):
    transport = _mock_client(exc=httpx.ConnectError("refused"))
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-good", base_url=None
        )
    assert exc.value.code == "UNREACHABLE"


async def test_timeout_raises_timeout(monkeypatch):
    transport = _mock_client(exc=httpx.TimeoutException("slow"))
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-good", base_url=None
        )
    assert exc.value.code == "TIMEOUT"


async def test_cohere_hits_cohere_ai(monkeypatch):
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"models": []})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    await verify_provider_credentials(
        provider="cohere", api_key="co-good", base_url=None
    )
    assert seen["url"] == "https://api.cohere.ai/v1/models"
    assert seen["auth"] == "Bearer co-good"


async def test_api_key_not_in_logs(monkeypatch, caplog):
    transport = _mock_client(status_code=401)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    import logging

    caplog.set_level(logging.DEBUG, logger="bigrag.services.credential_check")
    with pytest.raises(CredentialCheckError):
        await verify_provider_credentials(
            provider="openai",
            api_key="sk-SECRET-TOKEN-12345",
            base_url=None,
        )
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "sk-SECRET-TOKEN-12345" not in joined
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/yoginth/bigrag/api && uv run pytest tests/test_credential_check.py -v
```

Expected: ImportError — module `bigrag.services.credential_check` does not exist.

- [ ] **Step 3: Implement the module**

Create `api/bigrag/services/credential_check.py`:

```python
"""Live credential verification for embedding provider API keys.

Called from the admin ``POST /v1/admin/embedding-presets`` handler before
the preset is persisted, so operators learn immediately when a key is bad
instead of hitting the failure at first-use.

The check is intentionally cheap: a single GET against the provider's
``/models`` listing. That proves the key authenticates; it does not prove
the requested ``model`` exists on the provider (mismatches surface at
embed time).

Strictly fails closed — any non-2xx, network error, or timeout raises
``CredentialCheckError``. Self-hosted OpenAI-compatible endpoints must
serve ``/models``; if they do not, the operator must fix the endpoint
rather than bypass verification.
"""

from __future__ import annotations

from typing import Literal

import httpx

from bigrag.logging import get_logger

logger = get_logger("bigrag.services.credential_check")

Provider = Literal["openai", "cohere"]

_DEFAULT_BASE_URLS: dict[Provider, str] = {
    "openai": "https://api.openai.com/v1",
    "cohere": "https://api.cohere.ai/v1",
}


class CredentialCheckError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _build_client(timeout: float) -> httpx.AsyncClient:
    """Seam for tests to inject an httpx.MockTransport."""
    return httpx.AsyncClient(timeout=timeout)


async def verify_provider_credentials(
    provider: Provider,
    api_key: str,
    base_url: str | None,
    *,
    timeout_seconds: float = 5.0,
) -> None:
    """Hit the provider's /models endpoint. Return None on 2xx.

    Raises :class:`CredentialCheckError` on any non-2xx response, network
    failure, or timeout. The ``api_key`` is never logged, even on error.
    """
    root = (base_url or _DEFAULT_BASE_URLS[provider]).rstrip("/")
    url = f"{root}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with _build_client(timeout_seconds) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        logger.warning(
            "credential_check timeout", extra={"provider": provider, "base_url": base_url}
        )
        raise CredentialCheckError(
            "TIMEOUT", f"Provider did not respond within {timeout_seconds:.0f}s."
        ) from None
    except httpx.HTTPError as exc:
        logger.warning(
            "credential_check unreachable",
            extra={"provider": provider, "base_url": base_url, "error": type(exc).__name__},
        )
        raise CredentialCheckError("UNREACHABLE", "Could not reach provider.") from None

    status = response.status_code
    if 200 <= status < 300:
        return

    if status in (401, 403):
        logger.info(
            "credential_check rejected",
            extra={"provider": provider, "base_url": base_url, "status": status},
        )
        raise CredentialCheckError("INVALID_KEY", "Invalid API key.")
    if status == 404:
        logger.info(
            "credential_check endpoint missing",
            extra={"provider": provider, "base_url": base_url},
        )
        raise CredentialCheckError(
            "NOT_FOUND", "Provider endpoint did not recognize /models."
        )
    logger.warning(
        "credential_check provider error",
        extra={"provider": provider, "base_url": base_url, "status": status},
    )
    raise CredentialCheckError("PROVIDER_ERROR", f"Provider returned {status}.")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/yoginth/bigrag/api && uv run pytest tests/test_credential_check.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/yoginth/bigrag
git add api/bigrag/services/credential_check.py api/tests/test_credential_check.py
git commit -m "feat: add verify_provider_credentials helper for model API keys"
```

---

## Task 2: Wire credential check into the preset router (TDD)

**Files:**
- Modify: `api/bigrag/routers/embedding_presets.py:62-86`
- Modify: `api/tests/conftest.py` (add `bigrag.routers.embedding_presets.db` to the patch list)
- Test: `api/tests/test_embedding_presets.py`

- [ ] **Step 1: Wire the router's db into the test fixture**

Open `api/tests/conftest.py`. Find the block that patches router modules (around line 379-383) and add one line for `embedding_presets`:

```python
stack.enter_context(patch("bigrag.routers.collections.db", mock_db))
stack.enter_context(patch("bigrag.routers.documents.db", mock_db))
stack.enter_context(patch("bigrag.routers.embedding_presets.db", mock_db))  # NEW
stack.enter_context(patch("bigrag.routers.webhooks.db", mock_db))
```

- [ ] **Step 2: Write the failing router tests**

Create `api/tests/test_embedding_presets.py`. Note the pattern: set `mock_db.fetchrow.return_value = <row>` rather than replacing `mock_db.fetchrow` itself — the `_install_auth_fetchrow` wrapper in conftest falls through to `return_value` for any query it does not recognize (see `conftest.py:230-258`), so auth keeps working for free.

```python
"""Tests for the POST /v1/admin/embedding-presets credential check."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from httpx import AsyncClient

from bigrag.services.credential_check import CredentialCheckError


def _preset_row(name: str) -> dict:
    now = datetime.now(UTC)
    return {
        "id": uuid.uuid4(),
        "name": name,
        "provider": "openai",
        "model": "text-embedding-3-small",
        "api_key": "sk-xxx",
        "base_url": None,
        "dimension": 1536,
        "created_at": now,
        "updated_at": now,
    }


async def test_create_preset_rejects_invalid_key(
    client: AsyncClient, mock_db, monkeypatch
):
    async def fail_verify(**kwargs):
        raise CredentialCheckError("INVALID_KEY", "Invalid API key.")

    monkeypatch.setattr(
        "bigrag.routers.embedding_presets.verify_provider_credentials",
        fail_verify,
    )
    mock_db.fetchrow.return_value = _preset_row("ShouldNotInsert")

    resp = await client.post(
        "/v1/admin/embedding-presets",
        json={
            "name": "Bad",
            "provider": "openai",
            "model": "text-embedding-3-small",
            "api_key": "sk-bad",
            "dimension": 1536,
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"]["code"] == "INVALID_KEY"
    assert body["detail"]["message"] == "Invalid API key."

    inserts = [
        c
        for c in mock_db.fetchrow.await_args_list
        if c.args and "INSERT INTO embedding_presets" in c.args[0]
    ]
    assert inserts == [], "INSERT must not run when verification fails"


async def test_create_preset_accepts_valid_key(
    client: AsyncClient, mock_db, monkeypatch
):
    async def ok_verify(**kwargs):
        return None

    monkeypatch.setattr(
        "bigrag.routers.embedding_presets.verify_provider_credentials",
        ok_verify,
    )
    mock_db.fetchrow.return_value = _preset_row("Good")

    resp = await client.post(
        "/v1/admin/embedding-presets",
        json={
            "name": "Good",
            "provider": "openai",
            "model": "text-embedding-3-small",
            "api_key": "sk-good",
            "dimension": 1536,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Good"
    assert body["has_api_key"] is True


async def test_create_preset_surfaces_timeout_code(
    client: AsyncClient, mock_db, monkeypatch
):
    async def slow_verify(**kwargs):
        raise CredentialCheckError("TIMEOUT", "Provider did not respond within 5s.")

    monkeypatch.setattr(
        "bigrag.routers.embedding_presets.verify_provider_credentials",
        slow_verify,
    )

    resp = await client.post(
        "/v1/admin/embedding-presets",
        json={
            "name": "Slow",
            "provider": "openai",
            "model": "text-embedding-3-small",
            "api_key": "sk-any",
            "dimension": 1536,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "TIMEOUT"


async def test_patch_preset_does_not_verify(
    client: AsyncClient, mock_db, monkeypatch
):
    """PATCH must not call verify_provider_credentials (scope decision)."""
    verify_mock = AsyncMock()
    monkeypatch.setattr(
        "bigrag.routers.embedding_presets.verify_provider_credentials",
        verify_mock,
    )
    preset_id = str(uuid.uuid4())
    mock_db.fetchrow.return_value = _preset_row("Existing")

    resp = await client.patch(
        f"/v1/admin/embedding-presets/{preset_id}",
        json={"api_key": "sk-new-value"},
    )
    assert resp.status_code == 200
    verify_mock.assert_not_called()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/yoginth/bigrag/api && uv run pytest tests/test_embedding_presets.py -v
```

Expected: all four tests fail. Either `AttributeError` on `verify_provider_credentials` (not yet imported in the router) or the 422 assertion fails (validation not wired).

- [ ] **Step 4: Wire credential check into the router**

Open `api/bigrag/routers/embedding_presets.py`. Add the import near the top (line 14-23 area):

```python
from bigrag.services.credential_check import (
    CredentialCheckError,
    verify_provider_credentials,
)
```

Replace the `create_preset` body (lines 62-86). The current body is:

```python
@router.post("", response_model=EmbeddingPresetResponse, status_code=201)
async def create_preset(
    body: CreateEmbeddingPresetRequest,
    admin: dict = Depends(require_session),
) -> EmbeddingPresetResponse:
    try:
        row = await db.fetchrow(
            """
            INSERT INTO embedding_presets
                (id, name, provider, model, api_key, base_url, dimension)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            uuid.uuid4(),
            body.name,
            body.provider,
            body.model,
            body.api_key,
            body.base_url,
            body.dimension,
        )
    except UniqueViolationError as e:
        raise HTTPException(status_code=409, detail="A preset with that name already exists") from e
    logger.info(f"Embedding preset created: name={body.name} by={admin['email']}")
    return _row_to_response(dict(row))
```

Change to:

```python
@router.post("", response_model=EmbeddingPresetResponse, status_code=201)
async def create_preset(
    body: CreateEmbeddingPresetRequest,
    admin: dict = Depends(require_session),
) -> EmbeddingPresetResponse:
    try:
        await verify_provider_credentials(
            provider=body.provider,
            api_key=body.api_key,
            base_url=body.base_url,
        )
    except CredentialCheckError as e:
        raise HTTPException(
            status_code=422,
            detail={"code": e.code, "message": e.message},
        ) from e

    try:
        row = await db.fetchrow(
            """
            INSERT INTO embedding_presets
                (id, name, provider, model, api_key, base_url, dimension)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            uuid.uuid4(),
            body.name,
            body.provider,
            body.model,
            body.api_key,
            body.base_url,
            body.dimension,
        )
    except UniqueViolationError as e:
        raise HTTPException(
            status_code=409,
            detail="A preset with that name already exists",
        ) from e
    logger.info(f"Embedding preset created: name={body.name} by={admin['email']}")
    return _row_to_response(dict(row))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/yoginth/bigrag/api && uv run pytest tests/test_embedding_presets.py tests/test_credential_check.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Run the full backend test suite to check nothing else broke**

```bash
cd /Users/yoginth/bigrag/api && uv run pytest -q
```

Expected: green.

- [ ] **Step 7: Commit**

```bash
cd /Users/yoginth/bigrag
git add api/bigrag/routers/embedding_presets.py api/tests/conftest.py api/tests/test_embedding_presets.py
git commit -m "feat: verify provider API key before creating embedding preset"
```

---

## Task 3: Extract error code from `detail` in the Studio API client

**Files:**
- Modify: `app/src/lib/api.ts:10-26`

Currently `beforeError` handles `detail` as a string only. The new endpoint returns `detail: {code, message}`, so we need to support both shapes and stash the code on the wrapped error.

- [ ] **Step 1: Replace the `beforeError` hook**

Open `app/src/lib/api.ts`. Replace the existing hook:

```typescript
const api: KyInstance = ky.create({
  prefix: "/api/bigrag",
  credentials: "include",
  timeout: 120_000,
  retry: { limit: 1 },
  hooks: {
    beforeError: [
      async ({ error }) => {
        if (error instanceof HTTPError) {
          try {
            const body = (await error.response.clone().json()) as {
              detail?: string | { code?: string; message?: string };
            };
            const detail = body.detail;
            if (typeof detail === "string" && detail) {
              const wrapped = new Error(detail) as Error & {
                status?: number;
                code?: string;
              };
              wrapped.name = "HTTPError";
              wrapped.status = error.response.status;
              return wrapped;
            }
            if (detail && typeof detail === "object" && detail.message) {
              const wrapped = new Error(detail.message) as Error & {
                status?: number;
                code?: string;
              };
              wrapped.name = "HTTPError";
              wrapped.status = error.response.status;
              wrapped.code = detail.code;
              return wrapped;
            }
          } catch {
            // body was not JSON — fall through to the original error
          }
        }
        return error;
      },
    ],
  },
});
```

- [ ] **Step 2: Typecheck the app**

```bash
cd /Users/yoginth/bigrag && pnpm --filter @bigrag/app typecheck
```

Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/yoginth/bigrag
git add app/src/lib/api.ts
git commit -m "feat: surface error code from object-shaped 422 detail"
```

---

## Task 4: Update the preset form for inline INVALID_KEY + "Verifying…" label

**Files:**
- Modify: `app/src/app/(dashboard)/models/components/preset-form.tsx`

- [ ] **Step 1: Add the API-key error state and handler**

Open `app/src/app/(dashboard)/models/components/preset-form.tsx`.

Add a new state near line 38 (next to `error`):

```tsx
const [apiKeyError, setApiKeyError] = useState<string | null>(null);
```

Reset it in the `useEffect` that fires when the modal opens or `editing` changes (around line 54), alongside `setError(null)`:

```tsx
setApiKeyError(null);
```

- [ ] **Step 2: Replace the submit error handling**

Replace the `catch` block inside `onSubmit` (current lines 93-97):

```tsx
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setError(message);
      toast.error(message);
    }
```

With:

```tsx
    } catch (err) {
      const e = err as Error & { code?: string };
      const message = e.message || "Something went wrong";
      if (e.code === "INVALID_KEY") {
        setApiKeyError(message);
        return;
      }
      setError(message);
      toast.error(message);
    }
```

- [ ] **Step 3: Clear the inline error when the user edits the key**

Replace the `onChange` on the API key `<Input>` (around line 151):

```tsx
onChange={(e) => setApiKey(e.target.value)}
```

With:

```tsx
onChange={(e) => {
  setApiKey(e.target.value);
  if (apiKeyError) setApiKeyError(null);
}}
```

- [ ] **Step 4: Show the inline error and update the button label**

Add the inline error under the API-key input. Replace the existing `<Input ... type="password" value={apiKey} />` block (lines 144-155) with the same input wrapped in a fragment followed by a conditional error line:

```tsx
<div className="space-y-1">
  <Input
    label="Provider API key"
    description={
      isEdit
        ? "Leave blank to keep the existing key."
        : "Stored server-side; used whenever a collection references this preset."
    }
    onChange={(e) => {
      setApiKey(e.target.value);
      if (apiKeyError) setApiKeyError(null);
    }}
    placeholder={isEdit ? "••••••••" : "sk-..."}
    type="password"
    value={apiKey}
  />
  {apiKeyError && (
    <p className="text-sm text-destructive">{apiKeyError}</p>
  )}
</div>
```

Replace the submit-button label (around lines 164-172) to show "Verifying…" during a fresh create:

```tsx
<Button type="submit" disabled={isPending}>
  {isPending
    ? isEdit
      ? "Saving…"
      : "Verifying…"
    : isEdit
      ? "Save changes"
      : "Create preset"}
</Button>
```

- [ ] **Step 5: Typecheck and lint**

```bash
cd /Users/yoginth/bigrag && pnpm --filter @bigrag/app typecheck && pnpm biome check app/src/app/\(dashboard\)/models
```

Expected: no errors.

- [ ] **Step 6: Manual smoke test**

Start the stack:

```bash
cd /Users/yoginth/bigrag && ./dev.sh &
cd /Users/yoginth/bigrag && pnpm dev:app
```

In the browser (http://localhost:3100):
1. Log in, go to `/models`.
2. Click "New preset", fill in name="Smoke bad", provider=OpenAI, model=`text-embedding-3-small`, api_key=`sk-obviously-invalid-12345`.
3. Submit. Expect: button shows "Verifying…" briefly, then inline red text appears under the API Key input saying "Invalid API key." No toast. Modal stays open.
4. Change the API key to the real OPENAI_API_KEY, submit. Expect: success toast, modal closes, preset appears in the table.
5. Stop the manual test.

- [ ] **Step 7: Commit**

```bash
cd /Users/yoginth/bigrag
git add app/src/app/\(dashboard\)/models/components/preset-form.tsx
git commit -m "feat: surface INVALID_KEY inline and show 'Verifying…' while checking"
```

---

## Task 5: Documentation

**Files:**
- Modify: `website/content/docs/api-reference/embedding-presets.mdx`
- Modify: `website/content/docs/concepts/embeddings.mdx`

- [ ] **Step 1: Read the current docs to find the right insertion points**

```bash
cd /Users/yoginth/bigrag
head -80 website/content/docs/api-reference/embedding-presets.mdx
head -80 website/content/docs/concepts/embeddings.mdx
```

Look for:
- In `api-reference/embedding-presets.mdx`: the section documenting `POST /v1/admin/embedding-presets` responses / errors.
- In `concepts/embeddings.mdx`: the section introducing presets.

- [ ] **Step 2: Update the API reference**

In `website/content/docs/api-reference/embedding-presets.mdx`, under the `POST` endpoint's error-responses section (add a new subsection if one doesn't exist), insert:

````markdown
### 422 Unprocessable Entity — credential verification failed

`POST` verifies the supplied `api_key` against the provider's `/models` endpoint before persisting. When that check fails, the endpoint returns 422 with a typed `detail`:

```json
{
  "detail": {
    "code": "INVALID_KEY",
    "message": "Invalid API key."
  }
}
```

| `code` | Condition |
|--------|-----------|
| `INVALID_KEY` | Provider returned 401 or 403. |
| `NOT_FOUND` | Provider returned 404 (self-hosted endpoints that do not implement `/models`). |
| `PROVIDER_ERROR` | Provider returned 5xx or another non-2xx status. |
| `UNREACHABLE` | Could not open a connection to the provider. |
| `TIMEOUT` | Provider did not respond within 5 seconds. |

The check runs only on `POST`. `PATCH` does not re-verify, so an edit that changes `api_key` is accepted without a live check.
````

- [ ] **Step 3: Update the concepts page**

In `website/content/docs/concepts/embeddings.mdx`, in the section that introduces presets (search for "preset" to find it), add a paragraph:

```markdown
When you create a preset, bigRAG calls the provider's `/models` endpoint with the supplied key before saving. If the key is rejected or the provider is unreachable, the request fails and no preset is created. Edits do not re-verify — update the key through the same form, and the check runs again.
```

- [ ] **Step 4: Typecheck the docs site**

```bash
cd /Users/yoginth/bigrag && pnpm --filter website build
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /Users/yoginth/bigrag
git add website/content/docs/api-reference/embedding-presets.mdx website/content/docs/concepts/embeddings.mdx
git commit -m "docs: document credential verification on POST embedding-presets"
```

---

## Task 6: Final verification

- [ ] **Step 1: Re-run backend tests**

```bash
cd /Users/yoginth/bigrag/api && uv run pytest -q
```

Expected: green.

- [ ] **Step 2: Re-run app typecheck + lint**

```bash
cd /Users/yoginth/bigrag && pnpm --filter @bigrag/app typecheck && pnpm biome check app
```

Expected: green.

- [ ] **Step 3: Verify the spec's acceptance criteria**

Read `docs/superpowers/specs/2026-04-12-verify-model-api-key-before-save-design.md` and confirm each of the following:

- `POST` with a bogus key → 422, no DB row. (covered by `test_create_preset_rejects_invalid_key`)
- `POST` with a real key → 201. (covered by `test_create_preset_accepts_valid_key`)
- `PATCH` behavior unchanged. (covered by `test_patch_preset_does_not_verify`)
- All five error codes raise-able. (covered by `test_credential_check.py`)
- API key never logged. (covered by `test_api_key_not_in_logs`)
- UI surfaces INVALID_KEY inline and other codes via toast. (covered by manual smoke in Task 4 Step 6)
- Docs reflect the new 422 payload shape.

- [ ] **Step 4: Nothing to commit here** — this is a verification gate only.
