# bigRAG Studio

A Next.js admin console for bigRAG — manage collections, upload documents,
watch ingestion live, run RAG queries, and mint API keys for external clients.

## Running

```bash
pnpm install
pnpm dev:app
```

Open http://localhost:3000. On first run the `/setup` page lets you create the
initial admin account. The Studio talks to the bigRAG server set in
`BIGRAG_URL` (defaults to `http://localhost:4000`).

## Stack

- Next.js 16 (App Router) · React 19 · TypeScript
- Tailwind CSS v4 with violet accent + stone neutrals
- Base UI for accessible primitives
- TanStack Query + Ky for data · Zustand for theme · Sonner for toasts
- `@bigrag/client` is used server-side in the catch-all proxy at `/api/bigrag/[...path]`

The server-side proxy forwards the browser's session cookie — and for external
clients using a minted API key, the Bearer header — to the bigRAG FastAPI service.
