# Voyage AI Embedding Support — Design

**Date:** 2026-04-25
**Status:** Approved
**Scope:** Add Voyage AI as a third managed embedding provider alongside OpenAI and Cohere.

## Goal

Operators can pick a Voyage AI model when creating a collection or an embedding preset, exactly the way they pick `openai` or `cohere` today. Provider authentication, credential verification, the embedding cache, the Studio admin UI, and the docs site all treat `voyage` as a first-class provider.

## Models supported out of the box

Six entries appear in `AVAILABLE_MODELS` and the Studio dropdown:

| Model | Default dim | Notes |
|-------|-------------|-------|
| `voyage-3-large` | 1024 | Highest quality general-purpose |
| `voyage-3.5` | 1024 | Default |
| `voyage-3.5-lite` | 1024 | Cheap general-purpose |
| `voyage-code-3` | 1024 | Code-tuned |
| `voyage-finance-2` | 1024 | Finance domain |
| `voyage-law-2` | 1024 | Legal domain |

Multilingual-2 is intentionally excluded — `voyage-3.5` already handles multilingual well.

## Approach: native SDK client

Add a `VoyageEmbedding` class in `api/bigrag/services/embedding.py` that wraps `voyageai.AsyncClient`. Voyage's `input_type` field accepts `"query"` and `"document"` directly, matching our existing `EmbeddingModel.embed(texts, input_type=...)` abstraction with no translation. Token limit set to 32 000 (Voyage's 32k context).

Rejected alternatives:
- **`openai_compatible` shim** — Voyage's `/embeddings` shape is similar but its `input_type` field is required for retrieval quality; routing via `openai_compatible` would silently drop it.
- **HTTP-only via httpx** — saves a dep but loses retries/typed responses for marginal benefit.

## Matryoshka dimension handling

`voyage-3-large`, `voyage-3.5`, `voyage-3.5-lite`, and `voyage-code-3` accept `output_dimension` ∈ {256, 512, 1024, 2048}. The `voyage-finance-2` and `voyage-law-2` models are fixed at 1024. We always pass `output_dimension=<dimension>` from the preset/collection config — Voyage accepts the default value as a no-op for fixed-dim models, so the same code path works for both.

The Studio catalog only shows the default 1024 entry per model. Operators who want a non-default dimension pass `dimension: 256` (etc.) via the API directly.

## Files changed

### Backend
- `api/pyproject.toml` — add `voyageai>=0.3`
- `api/uv.lock` — refreshed
- `api/bigrag/services/embedding.py` — new `VoyageEmbedding` class, extend `_TOKEN_LIMITS`, extend `get_embedding_model` factory, extend `AVAILABLE_MODELS` (6 entries)
- `api/bigrag/services/credential_check.py` — extend `Provider` Literal, add `voyage` to `_DEFAULT_BASE_URLS` (`https://api.voyageai.com/v1`)
- `api/bigrag/models/embedding_preset.py` — regex `^(openai|cohere|voyage)$` on Create/Update bodies
- `api/bigrag/routers/collections.py` — extend supported-providers tuple at the validation point

### Studio UI (Next.js)
- `app/src/app/(dashboard)/models/components/preset-form.tsx` — provider union widens, `DEFAULT_MODELS.voyage` added, Select adds Voyage option
- `app/src/types/bigrag.ts`, `app/src/hooks/use-collections.ts`, `app/src/hooks/use-embedding-presets.ts` — provider union widened wherever it appears

### Docs
- `website/content/docs/concepts/embeddings.mdx` — providers list, managed-models table, configuration tab
- `website/content/docs/api-reference/embedding-presets.mdx` — provider enum
- `website/content/docs/api-reference/collections.mdx` — provider enum
- `website/content/docs/getting-started/configuration.mdx` — `BIGRAG_EMBEDDING_PROVIDER` mention
- `website/content/docs/comparison.mdx` — if it lists embedding providers

## Cache safety

The persistent `embedding_cache` keys on `(content_hash, provider, model, dimension)`. Adding a new provider value introduces no collisions; existing OpenAI/Cohere cache entries are untouched. No migration.

## Out of scope (deliberate)

- `truncation` flag (operator-level override of our auto-truncation)
- `quantization: "int8"` / `"binary"` Voyage offers
- Contextual embeddings (`voyage-context-3`)
- A `voyage_compatible` provider — Voyage has no self-hosted ecosystem like OpenAI's

These can be added later if demand surfaces.

## Verification

- `ruff check api/` clean
- `biome check app/` clean
- Backend imports cleanly (Voyage class only constructs the client, not at import time)
- Manual: create preset via Studio with a real Voyage key, attach to a collection, ingest a small document, run a query — vectors land in Milvus and retrieval returns hits.
