# Verify model API key against provider before persisting

## Problem

When a user adds a new embedding-provider API key in Studio (`/models`), the backend at `api/bigrag/routers/embedding_presets.py:62-86` writes the key straight into the `embedding_presets` table. The key is only exercised later — when a collection is created against the preset, or when `/health/ready` runs. This lets bad keys (typos, wrong provider, revoked tokens) land in the database and only surface as a failure at ingestion time, far from the form that introduced them.

Users expect "Save" to mean "this key works."

## Goal

A `POST /v1/admin/embedding-presets` request with an unusable API key must fail synchronously with a clear error, and no row may be written. Edits (`PATCH`) are out of scope and keep current behavior.

## Non-goals

- Validating `PATCH` updates. Edits remain trusted.
- Re-validating existing rows in the database.
- Encrypting keys at rest, rotating keys, or any other credential-lifecycle work.
- Supporting providers other than the two already supported (`openai`, `cohere`).
- Verifying that the chosen `model` exists on the provider. We only verify that the key authenticates. Model mismatches continue to surface at embed time.

## Design

### Validation strategy

A single, cheap HTTP call to the provider's `/models` listing endpoint, authenticated with the supplied `api_key`. Any non-2xx response, network failure, or timeout aborts the save.

| Provider | Endpoint |
|----------|----------|
| `openai` | `GET {base_url or "https://api.openai.com/v1"}/models`, header `Authorization: Bearer {api_key}` |
| `cohere` | `GET https://api.cohere.ai/v1/models`, header `Authorization: Bearer {api_key}` |

OpenAI-compatible endpoints reached via `base_url` (Ollama, vLLM, LiteLLM, Azure) are assumed to implement `/models`. If they do not, the save is rejected with `NOT_FOUND` and the operator must use a compatible endpoint. This is strict-by-design — the user confirmed this tradeoff during brainstorming.

### New module: `api/bigrag/services/credential_check.py`

```python
from typing import Literal

class CredentialCheckError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

async def verify_provider_credentials(
    provider: Literal["openai", "cohere"],
    api_key: str,
    base_url: str | None,
    *,
    timeout_seconds: float = 5.0,
) -> None:
    """Hits the provider's /models endpoint. Returns None on 2xx.
    Raises CredentialCheckError on any failure."""
```

Implementation uses `httpx.AsyncClient` (already an indirect dependency via the `openai` SDK). The client is created per-call with `timeout=timeout_seconds` — no shared client, no pool. The call is fire-and-forget: response body is discarded, only the status code matters.

Error codes raised:

| Code | Condition | HTTP detail message |
|------|-----------|---------------------|
| `INVALID_KEY` | Response status `401` or `403` | "Invalid API key." |
| `NOT_FOUND` | Response status `404` | "Provider endpoint did not recognize /models." |
| `PROVIDER_ERROR` | Response status `5xx` or any other non-2xx | "Provider returned {status}." |
| `UNREACHABLE` | `httpx.ConnectError`, `httpx.NetworkError`, DNS failure | "Could not reach provider." |
| `TIMEOUT` | `httpx.TimeoutException` | "Provider did not respond within 5s." |

The module does not log the API key on failure. The log line includes provider, base_url (if set), status code, and error code — never the key.

### Router change

`api/bigrag/routers/embedding_presets.py`, `create_preset` handler:

```python
from bigrag.services.credential_check import (
    CredentialCheckError,
    verify_provider_credentials,
)

@router.post(...)
async def create_preset(body: CreateEmbeddingPresetRequest, ...):
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
        )
    # existing INSERT INTO embedding_presets (...) stays unchanged
```

The validation runs *after* Pydantic request parsing but *before* any database work. If validation fails, no row, no side effects.

### UI change

`app/src/app/(dashboard)/models/components/preset-form.tsx`:

- While the `POST` is in flight, the submit button disables and its label changes from "Save preset" to "Verifying…".
- On 422 with `detail.code === "INVALID_KEY"`, an inline error ("Invalid API key.") is shown under the API Key field. The toast is suppressed in this case — the inline message is enough.
- On any other 422 code (`NOT_FOUND`, `PROVIDER_ERROR`, `UNREACHABLE`, `TIMEOUT`), the existing toast system surfaces `detail.message`. No inline state change.
- On 2xx, existing success flow (close modal, invalidate query).

The PATCH path is unchanged — no "Verifying…" label, no new error handling, since the server does not validate.

### Testing

**Unit tests** (`api/tests/services/test_credential_check.py`, new file) using `respx` to stub `httpx`:

- OpenAI default base_url, 200 → no exception.
- OpenAI custom base_url, 200 → hits custom URL, no exception.
- 401 → `CredentialCheckError(code="INVALID_KEY")`.
- 403 → `CredentialCheckError(code="INVALID_KEY")`.
- 404 → `CredentialCheckError(code="NOT_FOUND")`.
- 503 → `CredentialCheckError(code="PROVIDER_ERROR")`.
- `httpx.ConnectError` → `CredentialCheckError(code="UNREACHABLE")`.
- `httpx.TimeoutException` → `CredentialCheckError(code="TIMEOUT")`.
- Cohere 200 hits `api.cohere.ai`.
- Assert that no test call accidentally logs the api_key (scan captured log records).

**E2E tests** (`e2e/tests/test_embedding_presets.py`, extended):

- `POST` with a syntactically plausible but bogus OpenAI key (`sk-invalid-for-test`) → expect 422 with `detail.code == "INVALID_KEY"`; follow up with `GET /v1/admin/embedding-presets` and assert the preset was not created.
- `POST` with the real OPENAI_API_KEY from `e2e/.env` → expect 201 (existing happy-path test, unchanged in intent but now implicitly covers the new code path).
- `PATCH` with a bogus api_key → expect 200 (confirms PATCH is not validated — documents the scope decision).

### Timeout

5 seconds, hardcoded in `verify_provider_credentials` default and not configurable from the router. Rationale: if `/models` can't respond in 5s, actual embed traffic against the same endpoint won't meet ingestion SLAs either. Making this configurable invites deploys that silently mask a broken provider.

### Documentation updates

- `website/content/docs/api-reference/embedding-presets.mdx` — document the new 422 error codes (`INVALID_KEY`, `NOT_FOUND`, `PROVIDER_ERROR`, `UNREACHABLE`, `TIMEOUT`) on `POST`, and note that the endpoint now performs a live credential check.
- `website/content/docs/concepts/embeddings.mdx` — add one paragraph under the presets section: "Creating a preset verifies the key against the provider before saving. Edits do not re-verify."

## Trade-offs

- **`GET /models` versus an actual embed call.** A `/models` call only proves authentication; a bad `model` value or wrong-dimension configuration still slips through to first use. We accepted this during brainstorming — the check is faster, cheaper, and doesn't bill the provider for a real embedding. The residual risk (bad model name) is small and surfaces clearly at first use.
- **Strict failure for every non-2xx.** Self-hosted endpoints that don't serve `/models` can't create presets. The operator has to fix their endpoint. User explicitly chose this over a "skip verification" escape hatch.
- **PATCH not validated.** An edit that changes only `name` shouldn't pay for a provider round-trip. Validating PATCH-with-new-key would require branching logic that gets confusing when multiple fields change together. The cost is that a user can still PATCH a bad key in. Acceptable: the create path is where typos actually happen.

## Rollout

Single merge to `main`. No migration, no feature flag — the behavior change is user-visible and desired. Existing rows are untouched.
