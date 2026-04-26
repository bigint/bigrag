"use client";

import { BookOpen, ChevronRight, Zap } from "lucide-react";
import { memo, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type { Document, QueryResult, QueryTimings } from "@/types/bigrag";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: {
    collection: string;
    chunks: QueryResult[];
    timings?: QueryTimings;
    cached?: boolean;
  };
};

interface Props {
  messages: ChatMessage[];
  isStreaming: boolean;
  documents?: Document[];
}

const CITATION_RE = /\[(\d+)\]/g;

const renderInlineCitations = (
  content: string,
  chunkCount: number,
  onCite: (n: number) => void,
): ReactNode[] => {
  const nodes: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const m of content.matchAll(CITATION_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) {
      nodes.push(<span key={`t-${key++}`}>{content.slice(last, idx)}</span>);
    }
    const n = Number.parseInt(m[1] ?? "0", 10);
    const valid = n >= 1 && n <= chunkCount;
    if (valid) {
      nodes.push(
        <button
          key={`c-${key++}`}
          type="button"
          onClick={() => onCite(n)}
          className="mx-0.5 inline-flex items-center rounded-sm bg-primary/10 px-1 align-baseline font-mono text-[11px] font-medium text-primary transition-colors hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          aria-label={`Jump to source ${n}`}
        >
          [{n}]
        </button>,
      );
    } else {
      nodes.push(<span key={`r-${key++}`}>{m[0]}</span>);
    }
    last = idx + m[0].length;
  }
  if (last < content.length) {
    nodes.push(<span key={`t-${key++}`}>{content.slice(last)}</span>);
  }
  return nodes;
};

const Bubble = memo(
  ({
    message,
    isStreaming,
    documentMap,
  }: {
    message: ChatMessage;
    isStreaming: boolean;
    documentMap: Map<string, string>;
  }) => {
    const isUser = message.role === "user";
    const detailsRef = useRef<HTMLDetailsElement>(null);
    const sourceRefs = useRef<Map<number, HTMLLIElement>>(new Map());
    const highlightTimer = useRef<number | null>(null);
    const [highlight, setHighlight] = useState<number | null>(null);

    useEffect(
      () => () => {
        if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current);
      },
      [],
    );

    const jumpToSource = (n: number) => {
      const chunks = message.meta?.chunks;
      if (!chunks || n < 1 || n > chunks.length) return;
      if (detailsRef.current && !detailsRef.current.open) {
        detailsRef.current.open = true;
      }
      const target = sourceRefs.current.get(n);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
      setHighlight(n);
      if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current);
      highlightTimer.current = window.setTimeout(() => setHighlight(null), 1500);
    };

    const chunkCount = message.meta?.chunks.length ?? 0;

    return (
      <div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
        {!isUser && message.meta && (
          <div className="mb-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
            <div className="flex items-center gap-1.5 rounded-md border border-border/60 bg-muted/60 px-2.5 py-1">
              <BookOpen aria-hidden className="size-3 shrink-0" />
              <span>
                Retrieved {message.meta.chunks.length} chunks from{" "}
                <span className="font-medium text-foreground">{message.meta.collection}</span>
                {message.meta.cached && (
                  <span className="ml-1.5 rounded-sm bg-success/15 px-1.5 py-0.5 font-medium text-success">
                    cached
                  </span>
                )}
              </span>
            </div>
            {message.meta.timings && (
              <div className="flex items-center gap-1.5 rounded-md border border-border/60 bg-muted/60 px-2.5 py-1 font-mono">
                <Zap aria-hidden className="size-3 shrink-0" />
                <span>{Math.round(message.meta.timings.total_ms)}ms</span>
              </div>
            )}
          </div>
        )}
        {!isUser &&
          message.meta?.timings &&
          (() => {
            const t = message.meta.timings;
            const phases = [
              ["embed", t.embed_ms],
              ["search", t.search_ms],
              ["rerank", t.rerank_ms],
              ["hyde", t.hyde_ms],
              ["mmr", t.mmr_ms],
            ] as const;
            const total = t.total_ms;
            return (
              <details className="group mt-0.5 mb-1 text-[11px] text-muted-foreground">
                <summary className="flex w-fit cursor-pointer items-center gap-1.5 rounded-md transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
                  <ChevronRight
                    aria-hidden
                    className="size-3 transition-transform [details[open]_&]:rotate-90"
                  />
                  <span>Per-phase latency</span>
                </summary>
                <div className="mt-1.5 w-full max-w-md space-y-1 rounded-md border border-border/60 bg-card px-3 py-2.5">
                  {phases.map(([name, ms]) => {
                    const pct = total > 0 ? Math.min(100, (ms / total) * 100) : 0;
                    const dim = ms < 0.05;
                    return (
                      <div
                        key={name}
                        className="grid grid-cols-[3.5rem_1fr_3.5rem] items-center gap-2.5"
                      >
                        <span className={cn(dim && "opacity-50")}>{name}</span>
                        <div className="h-1 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-primary/70"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span
                          className={cn(
                            "text-right font-mono tabular-nums",
                            dim ? "text-muted-foreground" : "text-foreground",
                          )}
                        >
                          {ms.toFixed(1)}ms
                        </span>
                      </div>
                    );
                  })}
                  <div className="mt-1.5 grid grid-cols-[3.5rem_1fr_3.5rem] items-center gap-2.5 border-t border-border/60 pt-1.5">
                    <span className="font-medium text-foreground">total</span>
                    <span aria-hidden />
                    <span className="text-right font-mono font-semibold tabular-nums text-foreground">
                      {total.toFixed(1)}ms
                    </span>
                  </div>
                </div>
              </details>
            );
          })()}
        <div
          className={cn(
            "max-w-[80%] whitespace-pre-wrap rounded-xl px-4 py-2.5 text-sm leading-relaxed",
            isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
          )}
        >
          {isUser
            ? message.content
            : renderInlineCitations(message.content, chunkCount, jumpToSource)}
          {isStreaming && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-current align-text-bottom" />
          )}
        </div>
        {!isUser && message.meta && message.meta.chunks.length > 0 && (
          <details ref={detailsRef} className="mt-1 text-xs">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              View sources
            </summary>
            <ol className="mt-2 space-y-1.5">
              {message.meta.chunks.map((c, i) => {
                const n = i + 1;
                const filename = c.document_id ? documentMap.get(c.document_id) : undefined;
                const docLabel =
                  filename ?? (c.document_id ? `${c.document_id.slice(0, 8)}…` : null);
                const hasCharRange =
                  typeof c.char_start === "number" && typeof c.char_end === "number";
                return (
                  <li
                    key={c.id}
                    ref={(el) => {
                      if (el) sourceRefs.current.set(n, el);
                      else sourceRefs.current.delete(n);
                    }}
                    className={cn(
                      "rounded-md border bg-card p-2 text-xs leading-snug transition-colors",
                      highlight === n ? "border-primary bg-primary/5" : "border-border",
                    )}
                  >
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground">
                      <span className="font-mono font-semibold text-foreground">[{n}]</span>
                      <span className="font-mono">score {c.score.toFixed(3)}</span>
                      {docLabel && (
                        <span
                          className={cn(
                            "max-w-[18rem] truncate",
                            filename ? "font-medium text-foreground" : "font-mono",
                          )}
                          title={filename ?? c.document_id ?? undefined}
                        >
                          {docLabel}
                        </span>
                      )}
                      {typeof c.chunk_index === "number" && (
                        <span className="font-mono">#{c.chunk_index}</span>
                      )}
                      {typeof c.page_no === "number" && (
                        <span className="rounded-sm bg-muted px-1.5 py-0.5 font-medium text-foreground">
                          p. {c.page_no}
                        </span>
                      )}
                      {hasCharRange && (
                        <span className="font-mono" title="character offsets in source">
                          {c.char_start}–{c.char_end}
                        </span>
                      )}
                    </div>
                    <p className="line-clamp-4 whitespace-pre-wrap text-muted-foreground">
                      {c.text}
                    </p>
                  </li>
                );
              })}
            </ol>
          </details>
        )}
      </div>
    );
  },
);
Bubble.displayName = "Bubble";

export const ChatMessages = ({ messages, isStreaming, documents }: Props) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const documentMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const d of documents ?? []) m.set(d.id, d.filename);
    return m;
  }, [documents]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: re-scroll on every messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: isStreaming ? "instant" : "smooth",
    });
  }, [messages, isStreaming]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 md:px-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4" role="log">
        {messages.map((m, i) => (
          <Bubble
            key={m.id}
            message={m}
            documentMap={documentMap}
            isStreaming={isStreaming && i === messages.length - 1 && m.role === "assistant"}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
