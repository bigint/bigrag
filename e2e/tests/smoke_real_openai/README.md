# Real-OpenAI smoke pass

Opt-in nightly safety net that proves bigRAG can still talk to the real
OpenAI API. Everything in this directory is **skipped** unless
`BIGRAG_E2E_REAL_OPENAI=1` is set in the environment.

## Budget

A full run issues **at most 5** real OpenAI calls, all against the
cheapest available models:

| Call                                                  | Model                     |
|-------------------------------------------------------|---------------------------|
| Embed `sample.txt` during ingestion (per test)        | `text-embedding-3-small`  |
| Embed the query                                       | `text-embedding-3-small`  |
| Non-streaming chat completion (1 test, ~1 call)       | `gpt-4o-mini`             |
| Streaming chat completion (1 test, ~1 call)           | `gpt-4o-mini`             |

Estimated cost per nightly run: **~$0.001 - $0.005**.

## Running locally

The fake-openai stack from `docker-compose.e2e.yml` still has to be up
(the smoke pass only overrides settings at runtime, it does not stand up
its own services):

```bash
cd e2e
make up                          # one-time, brings up the e2e stack
OPENAI_API_KEY=sk-... BIGRAG_E2E_REAL_OPENAI=1 make test-real
make down                        # when you are done
```

## CI cadence

Run **only on the nightly schedule** in `.github/workflows/e2e.yml`, not
on every PR. The fake-openai e2e suite is the per-PR safety net; this
suite is the daily contract check against the real provider.
