import { ArrowRight, Zap } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { GitHubIcon } from "../icons";

export const Hero = () => (
  <section className="relative overflow-hidden border-b border-fd-border bg-fd-background">
    <Image
      alt=""
      aria-hidden="true"
      className="absolute inset-0 size-full object-cover object-center"
      fill
      priority
      sizes="100vw"
      src="/home/bengaluru-hero.webp"
    />
    <div className="absolute inset-0 bg-gradient-to-b from-fd-background via-fd-background/80 to-fd-background/10 md:bg-gradient-to-r" />
    <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-fd-background to-transparent" />

    <div className="relative mx-auto max-w-6xl px-6 py-20 md:py-24 lg:py-28">
      <div className="max-w-2xl">
        <div className="mb-6 inline-flex items-center gap-2 rounded-md border border-fd-border/80 bg-fd-background/85 px-3 py-1.5 text-[13px] text-fd-muted-foreground shadow-sm backdrop-blur">
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
    </div>
  </section>
);
