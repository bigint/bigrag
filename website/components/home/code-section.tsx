import { BookOpen, Database, Terminal } from "lucide-react";

const codeExample = `import { BigRAG } from "@bigrag/client";

const client = new BigRAG({
  apiKey: "bigrag_sk_...",
  baseUrl: "http://localhost:4000",
});

const { results } = await client.queries.query("knowledge_base", {
  query: "What is the PTO policy?",
  top_k: 5,
});`;

export const CodeSection = () => (
  <section className="border-b border-fd-border">
    <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
      <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
        <div>
          <p className="mb-3 text-sm font-medium uppercase tracking-widest text-fd-muted-foreground">
            Simple integration
          </p>
          <h2 className="mb-4 text-3xl font-bold tracking-tight text-fd-foreground md:text-4xl">
            Upload, embed, and search in minutes
          </h2>
          <p className="mb-8 text-fd-muted-foreground md:text-lg md:leading-relaxed">
            bigRAG handles the entire RAG pipeline. Upload any document format, and it automatically
            parses, chunks, embeds, and indexes for vector search. Use the TypeScript SDK or REST
            API.
          </p>
          <div className="flex flex-col gap-3 text-sm text-fd-muted-foreground">
            <div className="flex items-center gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-fd-border bg-fd-card">
                <Terminal className="size-4 text-fd-foreground" />
              </div>
              <span>TypeScript SDK with zero dependencies and full type safety</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-fd-border bg-fd-card">
                <Database className="size-4 text-fd-foreground" />
              </div>
              <span>Qdrant vector database with HNSW search and cosine similarity</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-fd-border bg-fd-card">
                <BookOpen className="size-4 text-fd-foreground" />
              </div>
              <span>Full API reference with Swagger docs at /docs</span>
            </div>
          </div>
        </div>
        <div className="overflow-hidden rounded-lg border border-fd-border bg-fd-card shadow-sm">
          <div className="flex items-center gap-1.5 border-b border-fd-border bg-fd-muted/50 px-4 py-3">
            <div className="size-2.5 rounded-full bg-fd-border" />
            <div className="size-2.5 rounded-full bg-fd-border" />
            <div className="size-2.5 rounded-full bg-fd-border" />
            <span className="ml-3 text-xs text-fd-muted-foreground">app.ts</span>
          </div>
          <pre className="overflow-x-auto p-5 text-[13px] leading-relaxed">
            <code className="text-fd-foreground/85">{codeExample}</code>
          </pre>
        </div>
      </div>
    </div>
  </section>
);
