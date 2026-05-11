import { ArrowRight, CheckCircle2, FileText, Search, Server, Zap } from "lucide-react";
import Link from "next/link";
import { GitHubIcon } from "../icons";

const pipelineSteps = [
  { label: "Upload", value: "policy-handbook.pdf", icon: FileText },
  { label: "Parse", value: "248 chunks with page metadata", icon: CheckCircle2 },
  { label: "Embed", value: "OpenAI text-embedding-3-large", icon: Server },
  { label: "Query", value: "Hybrid search with citations", icon: Search },
];

export const Hero = () => (
  <section className="relative overflow-hidden border-b border-fd-border">
    <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,hsla(0,0%,0%,0.025)_1px,transparent_1px),linear-gradient(to_bottom,hsla(0,0%,0%,0.025)_1px,transparent_1px)] bg-[size:4rem_4rem]" />

    <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-6 py-20 md:py-24 lg:grid-cols-[minmax(0,0.95fr)_minmax(440px,1fr)] lg:py-28">
      <div>
        <div className="mb-6 inline-flex items-center gap-2 rounded-md border border-fd-border bg-fd-card px-3 py-1.5 text-[13px] text-fd-muted-foreground shadow-sm">
          <Zap className="size-3.5" />
          Open-source &middot; Self-hosted &middot; Full control
        </div>

        <h1 className="max-w-4xl text-4xl font-bold tracking-tight text-fd-foreground sm:text-5xl md:text-6xl lg:text-[4rem] lg:leading-[1.1]">
          Document ingestion and vector search you can self-host
        </h1>

        <p className="mt-6 max-w-2xl text-base text-fd-muted-foreground md:text-lg md:leading-relaxed">
          Upload documents, parse with Docling, embed with your provider, and retrieve cited chunks
          through one API.
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link
            className="inline-flex h-10 items-center gap-2 rounded-md bg-fd-primary px-5 text-sm font-medium text-fd-primary-foreground shadow-sm hover:opacity-90"
            href="/docs"
          >
            Get Started
            <ArrowRight className="size-4" />
          </Link>
          <Link
            className="inline-flex h-10 items-center gap-2 rounded-md border border-fd-border bg-fd-card px-5 text-sm font-medium text-fd-foreground shadow-sm hover:bg-fd-accent"
            href="https://github.com/bigint/bigrag"
            rel="noopener noreferrer"
            target="_blank"
          >
            <GitHubIcon className="size-4" />
            Star on GitHub
          </Link>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-fd-border bg-fd-card shadow-sm">
        <div className="border-b border-fd-border bg-fd-background px-5 py-4">
          <div className="text-xs font-medium uppercase tracking-widest text-fd-muted-foreground">
            Live retrieval flow
          </div>
          <div className="mt-2 text-lg font-semibold text-fd-foreground">
            Ask across policy-handbook.pdf
          </div>
        </div>
        <div className="grid gap-px bg-fd-border sm:grid-cols-2">
          {pipelineSteps.map(({ icon: Icon, label, value }) => (
            <div className="bg-fd-card p-5" key={label}>
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-fd-muted-foreground">
                <Icon className="size-3.5 text-fd-foreground" />
                {label}
              </div>
              <div className="mt-2 text-sm font-medium text-fd-foreground">{value}</div>
            </div>
          ))}
        </div>
        <div className="space-y-4 bg-fd-background p-5">
          <div className="rounded-lg border border-fd-border bg-fd-card p-4">
            <div className="text-sm font-medium text-fd-foreground">
              What is the PTO carryover policy?
            </div>
            <div className="mt-3 text-sm leading-6 text-fd-muted-foreground">
              Employees can carry over up to 40 PTO hours into the next calendar year, with unused
              excess paid out at year end.
            </div>
          </div>
          <div className="grid gap-2 text-xs text-fd-muted-foreground sm:grid-cols-2">
            <div className="rounded-md border border-fd-border bg-fd-card px-3 py-2">
              [1] policy-handbook.pdf, page 12
            </div>
            <div className="rounded-md border border-fd-border bg-fd-card px-3 py-2">
              score 0.91 &middot; hybrid
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
);
