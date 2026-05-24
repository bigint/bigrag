import type { ChatSource } from "@bigrag/client/browser";
import { Link } from "@tanstack/react-router";
import { ChevronRight, Database, FileText, Gauge, Hash } from "lucide-react";
import type { MutableRefObject, RefObject } from "react";
import { type ChatMessage, formatWholeMs } from "@/features/chat/chat-message-types";
import { cn } from "@/lib/cn";
import type { QueryTimings } from "@/types/bigrag";

export const SourcesPanel = ({
  detailsRef,
  highlight,
  message,
  sourceRefs,
}: {
  detailsRef: RefObject<HTMLDetailsElement | null>;
  highlight: number | null;
  message: ChatMessage;
  sourceRefs: MutableRefObject<Map<number, HTMLLIElement>>;
}) => {
  const meta = message.meta;
  if (!meta || meta.sources.length === 0) return null;
  return (
    <details ref={detailsRef} className="group mt-4 min-w-0 text-xs">
      <summary className="flex min-w-0 cursor-pointer list-none items-center justify-between gap-3 rounded-lg border border-border bg-muted/45 px-3 py-2 font-semibold text-muted-foreground hover:bg-muted hover:text-foreground">
        <span className="inline-flex min-w-0 items-center gap-2">
          <ChevronRight className="size-3.5 shrink-0 group-open:rotate-90" />
          <span className="truncate">Sources</span>
        </span>
        <span className="shrink-0 font-mono">
          {meta.sources.length}
          {meta.timings ? ` / ${formatWholeMs(meta.timings.total_ms)}` : ""}
        </span>
      </summary>
      {meta.timings && <LatencyLedger timings={meta.timings} />}
      <ol className="mt-2 grid min-w-0 gap-2">
        {meta.sources.map((source, index) => (
          <SourceCard
            key={source.id}
            highlight={highlight === index + 1}
            index={index + 1}
            refCallback={(el) => {
              if (el) sourceRefs.current.set(index + 1, el);
              else sourceRefs.current.delete(index + 1);
            }}
            source={source}
            collection={meta.collection}
          />
        ))}
      </ol>
    </details>
  );
};

const LatencyLedger = ({ timings }: { timings: QueryTimings }) => {
  const total = timings.total_ms;
  const cacheMs = timings.cache_ms > 0 ? timings.cache_ms : total;
  const phases = timings.cache_hit
    ? ([
        ["cache", cacheMs],
        ["embed", timings.embed_ms],
        ["search", timings.search_ms],
        ["rerank", timings.rerank_ms],
      ] as const)
    : ([
        ["embed", timings.embed_ms],
        ["search", timings.search_ms],
        ["rerank", timings.rerank_ms],
      ] as const);

  return (
    <div className="mt-2 min-w-0 rounded-lg border border-border bg-background p-3 text-xs text-muted-foreground">
      <div className="mb-2 flex items-center justify-between gap-3 font-semibold text-foreground">
        <span className="inline-flex items-center gap-2">
          {timings.cache_hit ? <Database className="size-3.5" /> : <Gauge className="size-3.5" />}
          Retrieval
        </span>
        <span className="font-mono tabular-nums">{formatWholeMs(total)}</span>
      </div>
      <div className="grid gap-1.5">
        {phases.map(([name, ms]) => {
          const pct = total > 0 ? Math.min(100, (ms / total) * 100) : 0;
          const isZero = ms < 0.05;
          return (
            <div key={name} className="grid grid-cols-[3.5rem_1fr_3.75rem] items-center gap-2">
              <span className={cn("font-semibold", isZero && "opacity-50")}>{name}</span>
              <div className="h-1 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-foreground" style={{ width: `${pct}%` }} />
              </div>
              <span className="text-right font-mono tabular-nums">{ms.toFixed(1)}ms</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const SourceCard = ({
  collection,
  highlight,
  index,
  refCallback,
  source,
}: {
  collection: string | null;
  highlight?: boolean;
  index: number;
  refCallback?: (el: HTMLLIElement | null) => void;
  source: ChatSource;
}) => {
  const filename = source.document_filename ?? undefined;
  const docLabel =
    filename ?? (source.document_id ? `${source.document_id.slice(0, 8)}...` : "Unknown source");
  const hasCharRange = typeof source.char_start === "number" && typeof source.char_end === "number";

  return (
    <li
      ref={refCallback}
      className={cn(
        "min-w-0 overflow-hidden rounded-lg border bg-background p-3 text-xs leading-snug",
        highlight ? "border-foreground bg-muted" : "border-border",
      )}
    >
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <span className="rounded-md border border-border bg-card px-1.5 py-0.5 font-mono font-semibold text-foreground">
              [{index}]
            </span>
            {collection && source.document_id ? (
              <Link
                to="/collections/$name/documents/$docId"
                params={{ name: collection, docId: source.document_id }}
                hash={
                  typeof source.chunk_index === "number" ? `chunk-${source.chunk_index}` : undefined
                }
                className="inline-flex min-w-0 items-center gap-1 font-semibold text-foreground hover:text-primary"
              >
                <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate" title={filename ?? source.document_id ?? undefined}>
                  {docLabel}
                </span>
              </Link>
            ) : (
              <span className="inline-flex min-w-0 items-center gap-1 font-semibold text-foreground">
                <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate" title={filename ?? source.document_id ?? undefined}>
                  {docLabel}
                </span>
              </span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-muted-foreground">
            {typeof source.chunk_index === "number" && (
              <span className="inline-flex items-center gap-1 font-mono">
                <Hash className="size-3" />
                {source.chunk_index}
              </span>
            )}
            {typeof source.page_no === "number" && (
              <span className="rounded-md bg-muted px-1.5 py-0.5 font-semibold text-foreground">
                p. {source.page_no}
              </span>
            )}
            {hasCharRange && (
              <span className="font-mono">
                {source.char_start}-{source.char_end}
              </span>
            )}
          </div>
        </div>
        <span className="shrink-0 font-mono text-muted-foreground">{source.score.toFixed(3)}</span>
      </div>
      <p className="mt-2 line-clamp-3 min-w-0 break-all whitespace-pre-wrap text-muted-foreground [overflow-wrap:anywhere]">
        {source.text}
      </p>
    </li>
  );
};
