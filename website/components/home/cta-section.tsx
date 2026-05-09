import { ArrowRight, Server } from "lucide-react";
import Link from "next/link";

export function CtaSection() {
  return (
    <section>
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <div className="flex flex-col items-center rounded-xl border border-fd-border bg-fd-card p-10 text-center shadow-sm md:p-16">
          <Server className="mb-6 size-10 text-fd-muted-foreground" />
          <h2 className="mb-3 text-3xl font-bold tracking-tight text-fd-foreground md:text-4xl">
            Deploy on your infrastructure
          </h2>
          <p className="mb-8 max-w-lg text-fd-muted-foreground md:text-lg">
            Your documents, embeddings, and search data never leave your servers. One command to get
            started.
          </p>
          <div className="mb-8 w-full max-w-md overflow-hidden rounded-lg border border-fd-border bg-fd-background shadow-sm">
            <pre className="px-5 py-4 text-left text-sm">
              <code className="text-fd-foreground/85">
                <span className="text-fd-muted-foreground">$</span>
                {" git clone https://github.com/bigint/bigrag"}
                {"\n"}
                <span className="text-fd-muted-foreground">$</span> cd bigrag
                {"\n"}
                <span className="text-fd-muted-foreground">$</span> docker compose up -d
              </code>
            </pre>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              className="inline-flex h-10 items-center gap-2 rounded-md bg-fd-primary px-5 text-sm font-medium text-fd-primary-foreground shadow-sm hover:opacity-90"
              href="/docs/deployment/docker"
            >
              Deployment Guide
              <ArrowRight className="size-4" />
            </Link>
            <Link
              className="inline-flex h-10 items-center rounded-md border border-fd-border bg-fd-background px-5 text-sm font-medium text-fd-foreground shadow-sm hover:bg-fd-accent"
              href="/docs/getting-started/quickstart"
            >
              Quickstart
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
