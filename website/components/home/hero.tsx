import { ArrowRight, Zap } from "lucide-react";
import Link from "next/link";
import { GitHubIcon } from "../icons";

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-fd-border">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_50%_-20%,hsla(0,0%,50%,0.07),transparent)]" />
      <div className="dark:hidden pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,hsla(0,0%,0%,0.02)_1px,transparent_1px),linear-gradient(to_bottom,hsla(0,0%,0%,0.02)_1px,transparent_1px)] bg-[size:4rem_4rem]" />
      <div className="hidden dark:block pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,hsla(0,0%,100%,0.02)_1px,transparent_1px),linear-gradient(to_bottom,hsla(0,0%,100%,0.02)_1px,transparent_1px)] bg-[size:4rem_4rem]" />

      <div className="relative mx-auto flex max-w-6xl flex-col items-center px-6 pb-24 pt-28 text-center md:pb-32 md:pt-36">
        <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-fd-border bg-fd-card px-4 py-1.5 text-[13px] text-fd-muted-foreground shadow-sm">
          <Zap className="size-3.5" />
          Open-source &middot; Self-hosted &middot; Full control
        </div>

        <h1 className="mb-6 max-w-4xl text-4xl font-bold tracking-tight text-fd-foreground sm:text-5xl md:text-6xl lg:text-[4rem] lg:leading-[1.1]">
          Document ingestion and{" "}
          <span className="bg-gradient-to-r from-fd-foreground/80 to-fd-foreground bg-clip-text">
            vector search
          </span>{" "}
          you can self-host
        </h1>

        <p className="mb-10 max-w-2xl text-base text-fd-muted-foreground md:text-lg md:leading-relaxed">
          bigRAG is a complete RAG pipeline — upload documents, auto-chunk, embed, and search. One
          API for your entire retrieval-augmented generation stack. Deploy on your infrastructure in
          minutes.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-fd-primary px-5 text-sm font-medium text-fd-primary-foreground shadow-sm transition-all hover:opacity-90"
            href="/docs"
          >
            Get Started
            <ArrowRight className="size-4" />
          </Link>
          <Link
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-fd-border bg-fd-card px-5 text-sm font-medium text-fd-foreground shadow-sm transition-all hover:bg-fd-accent"
            href="https://github.com/bigint/bigrag"
            rel="noopener noreferrer"
            target="_blank"
          >
            <GitHubIcon className="size-4" />
            Star on GitHub
          </Link>
        </div>
      </div>
    </section>
  );
}
