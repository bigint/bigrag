import Link from "next/link";

const features = [
  {
    title: "Any Document Format",
    description:
      "PDF, DOCX, PPTX, HTML, Markdown, images with OCR, and more — powered by Docling.",
    href: "/docs/concepts/documents",
  },
  {
    title: "Any Embedding Model",
    description:
      "OpenAI and Cohere embedding models with per-collection configuration.",
    href: "/docs/concepts/embeddings",
  },
  {
    title: "Hybrid Search",
    description:
      "Semantic, keyword, or hybrid search with Reciprocal Rank Fusion for best results.",
    href: "/docs/concepts/search",
  },
  {
    title: "Real-Time Progress",
    description:
      "Stream document processing progress via Server-Sent Events. Know exactly what's happening.",
    href: "/docs/concepts/documents",
  },
  {
    title: "Webhooks",
    description:
      "Get notified when documents are processed. HMAC-signed payloads with automatic retries.",
    href: "/docs/concepts/webhooks",
  },
  {
    title: "TypeScript SDK",
    description:
      "Zero-dependency client for Node.js, browsers, Deno, and Bun with full type safety.",
    href: "/docs/sdks/typescript",
  },
];

export default function Page() {
  return (
    <main>
      <section className="hero-gradient relative overflow-hidden">
        <div className="mx-auto flex max-w-5xl flex-col items-center px-6 pb-20 pt-24 text-center md:pb-28 md:pt-32">
          <div className="mb-6 inline-flex items-center rounded-full border border-fd-border bg-fd-secondary/50 px-4 py-1.5 text-sm text-fd-muted-foreground">
            Open-source RAG Platform
          </div>
          <h1 className="mb-6 max-w-3xl text-4xl font-bold tracking-tight text-fd-foreground sm:text-5xl md:text-6xl">
            Document ingestion and vector search you can self-host
          </h1>
          <p className="mb-10 max-w-2xl text-lg text-fd-muted-foreground md:text-xl">
            bigRAG is a complete RAG pipeline — upload documents, auto-chunk,
            embed, and search — all behind a simple REST API with full control
            over your data.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/docs"
              className="inline-flex h-11 items-center rounded-lg bg-fd-primary px-6 text-sm font-medium text-fd-primary-foreground transition-colors hover:bg-fd-primary/90"
            >
              Get Started
            </Link>
            <Link
              href="/docs/deployment/docker"
              className="inline-flex h-11 items-center rounded-lg border border-fd-border bg-fd-background px-6 text-sm font-medium text-fd-foreground transition-colors hover:bg-fd-accent"
            >
              Deploy with Docker
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-20">
        <div className="mb-12 text-center">
          <h2 className="mb-3 text-3xl font-bold tracking-tight text-fd-foreground">
            Everything you need for RAG
          </h2>
          <p className="text-fd-muted-foreground">
            One platform for document ingestion, embedding, and retrieval.
          </p>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Link
              key={feature.title}
              href={feature.href}
              className="group rounded-xl border border-fd-border bg-fd-card p-6 transition-colors hover:bg-fd-accent/50"
            >
              <h3 className="mb-2 font-semibold text-fd-foreground group-hover:text-fd-primary">
                {feature.title}
              </h3>
              <p className="text-sm leading-relaxed text-fd-muted-foreground">
                {feature.description}
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-20">
        <div className="rounded-xl border border-fd-border bg-fd-card p-8 md:p-12">
          <div className="flex flex-col items-center gap-6 text-center md:flex-row md:text-left">
            <div className="flex-1">
              <h2 className="mb-2 text-2xl font-bold tracking-tight text-fd-foreground">
                Ready to deploy?
              </h2>
              <p className="text-fd-muted-foreground">
                Get bigRAG running on your infrastructure in under 5 minutes
                with Docker Compose.
              </p>
            </div>
            <Link
              href="/docs/getting-started/quickstart"
              className="inline-flex h-11 shrink-0 items-center rounded-lg bg-fd-primary px-6 text-sm font-medium text-fd-primary-foreground transition-colors hover:bg-fd-primary/90"
            >
              Quickstart Guide
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-fd-border py-8 text-center text-sm text-fd-muted-foreground">
        <p>
          Built by{" "}
          <a
            href="https://x.com/yoginth"
            className="font-medium text-fd-foreground hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            Yoginth
          </a>
          . The source code is on{" "}
          <a
            href="https://github.com/bigint/bigrag"
            className="font-medium text-fd-foreground hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
          .
        </p>
      </footer>
    </main>
  );
}
