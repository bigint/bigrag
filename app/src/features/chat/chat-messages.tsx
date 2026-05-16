import {
  AlertTriangle,
  BookOpen,
  ChevronRight,
  Database,
  FileText,
  Gauge,
  Hash,
  Quote,
  Search,
  Zap,
} from "lucide-react";
import {
  type MutableRefObject,
  memo,
  type ReactNode,
  type RefObject,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/cn";
import type { ChatSource, QueryTimings } from "@/types/bigrag";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: "complete" | "error";
  errorMessage?: string | null;
  meta?: {
    collection: string | null;
    sources: ChatSource[];
    timings?: QueryTimings;
  };
};

interface Props {
  isStreaming: boolean;
  messages: ChatMessage[];
}

type RetrievalMeta = NonNullable<ChatMessage["meta"]>;

const CITATION_RE = /\[(\d+)\]/g;

const formatWholeMs = (ms: number) => (ms > 0 && ms < 1 ? "<1ms" : `${Math.round(ms)}ms`);

const renderInlineCitations = (
  content: string,
  chunkCount: number,
  onCite: (n: number) => void,
): ReactNode[] => {
  const nodes: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const match of content.matchAll(CITATION_RE)) {
    const idx = match.index ?? 0;
    if (idx > last) {
      nodes.push(<span key={`t-${key++}`}>{content.slice(last, idx)}</span>);
    }
    const n = Number.parseInt(match[1] ?? "0", 10);
    const valid = n >= 1 && n <= chunkCount;
    if (valid) {
      nodes.push(
        <button
          key={`c-${key++}`}
          type="button"
          onClick={() => onCite(n)}
          className="mx-0.5 inline-flex items-center rounded-md border border-primary/25 bg-primary/10 px-1.5 align-baseline font-mono text-xs font-semibold text-primary hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          aria-label={`Jump to source ${n}`}
        >
          [{n}]
        </button>,
      );
    } else {
      nodes.push(<span key={`r-${key++}`}>{match[0]}</span>);
    }
    last = idx + match[0].length;
  }
  if (last < content.length) {
    nodes.push(<span key={`t-${key++}`}>{content.slice(last)}</span>);
  }
  return nodes;
};

const AssistantMessage = memo(
  ({ isStreaming, message }: { isStreaming: boolean; message: ChatMessage }) => {
    const detailsRef = useRef<HTMLDetailsElement>(null);
    const sourceRefs = useRef<Map<number, HTMLLIElement>>(new Map());
    const highlightTimer = useRef<number | null>(null);
    const [highlight, setHighlight] = useState<number | null>(null);

    useHighlightTimerCleanup(highlightTimer);

    const jumpToSource = (n: number) => {
      const sources = message.meta?.sources;
      if (!sources || n < 1 || n > sources.length) return;
      if (detailsRef.current && !detailsRef.current.open) {
        detailsRef.current.open = true;
      }
      const target = sourceRefs.current.get(n);
      if (target) {
        target.scrollIntoView({ behavior: "instant", block: "nearest" });
      }
      setHighlight(n);
      if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current);
      highlightTimer.current = window.setTimeout(() => setHighlight(null), 1500);
    };

    const sourceCount = message.meta?.sources.length ?? 0;
    const hasError = message.status === "error" && Boolean(message.errorMessage);

    return (
      <article className="border-l-2 border-foreground pl-4">
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-2.5 py-1 text-xs font-semibold text-muted-foreground">
            <BookOpen className="size-3" />
            Grounded answer
          </span>
          {message.meta && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-2.5 py-1 text-xs font-semibold text-muted-foreground">
              <Search className="size-3" />
              {message.meta.sources.length} chunks
            </span>
          )}
          {message.meta?.timings && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/60 px-2.5 py-1 font-mono text-xs text-muted-foreground">
              {message.meta.timings.cache_hit ? (
                <Database className="size-3" />
              ) : (
                <Zap className="size-3" />
              )}
              {message.meta.timings.cache_hit ? "cached " : ""}
              {formatWholeMs(message.meta.timings.total_ms)}
            </span>
          )}
        </div>

        {message.meta?.timings && <LatencyLedger timings={message.meta.timings} />}

        <div
          className={cn(
            "whitespace-pre-wrap text-base leading-7 text-foreground",
            hasError &&
              "rounded-2xl border border-destructive/30 bg-destructive/5 p-3 text-sm leading-6",
          )}
        >
          {hasError ? (
            <span className="inline-flex gap-2 text-destructive">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <span>{message.errorMessage}</span>
            </span>
          ) : message.content ? (
            renderInlineCitations(message.content, sourceCount, jumpToSource)
          ) : (
            <span className="text-muted-foreground">Retrieving context and drafting answer...</span>
          )}
          {isStreaming && (
            <span className="ml-1 inline-block h-4 w-1.5 bg-current align-text-bottom" />
          )}
        </div>

        {message.meta && message.meta.sources.length > 0 && (
          <details ref={detailsRef} className="mt-4 text-xs">
            <summary className="flex w-fit cursor-pointer list-none items-center gap-2 rounded-md border border-border bg-background px-3 py-2 font-semibold text-muted-foreground hover:bg-muted hover:text-foreground">
              <ChevronRight className="size-3.5" />
              View evidence in this answer
            </summary>
            <ol className="mt-2 grid gap-2">
              {message.meta.sources.map((source, index) => (
                <SourceCard
                  key={source.id}
                  highlight={highlight === index + 1}
                  index={index + 1}
                  refCallback={(el) => {
                    if (el) sourceRefs.current.set(index + 1, el);
                    else sourceRefs.current.delete(index + 1);
                  }}
                  source={source}
                />
              ))}
            </ol>
          </details>
        )}
      </article>
    );
  },
);
AssistantMessage.displayName = "AssistantMessage";

const UserMessage = ({ content }: { content: string }) => (
  <article className="ml-auto max-w-2xl rounded-xl border border-border bg-muted px-4 py-3 text-sm font-semibold leading-6 text-foreground">
    {content}
  </article>
);

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
    <details className="mb-3 text-xs text-muted-foreground">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-2 rounded-md border border-border bg-background px-3 py-1.5 font-semibold hover:bg-muted hover:text-foreground">
        {timings.cache_hit ? <Database className="size-3.5" /> : <Gauge className="size-3.5" />}
        {timings.cache_hit ? "Cached retrieval" : "Retrieval latency"}
      </summary>
      <div className="mt-2 grid max-w-lg gap-1.5 rounded-lg border border-border bg-card p-3">
        {phases.map(([name, ms]) => {
          const pct = total > 0 ? Math.min(100, (ms / total) * 100) : 0;
          const dim = ms < 0.05;
          return (
            <div key={name} className="grid grid-cols-[3.5rem_1fr_4rem] items-center gap-2">
              <span className={cn("font-semibold", dim && "opacity-50")}>{name}</span>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-foreground" style={{ width: `${pct}%` }} />
              </div>
              <span className="text-right font-mono tabular-nums">{ms.toFixed(1)}ms</span>
            </div>
          );
        })}
        <div className="mt-1 grid grid-cols-[3.5rem_1fr_4rem] border-t border-border pt-2 font-semibold text-foreground">
          <span>total</span>
          <span aria-hidden />
          <span className="text-right font-mono tabular-nums">{total.toFixed(1)}ms</span>
        </div>
      </div>
    </details>
  );
};

const SourceCard = ({
  highlight,
  index,
  refCallback,
  source,
}: {
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
        "rounded-2xl border bg-card p-3 text-xs leading-snug",
        highlight ? "border-foreground bg-muted" : "border-border",
      )}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2 text-muted-foreground">
        <span className="rounded-md border border-border bg-background px-1.5 py-0.5 font-mono font-semibold text-foreground">
          [{index}]
        </span>
        <span className="inline-flex items-center gap-1 font-mono">
          <Gauge className="size-3" />
          {source.score.toFixed(3)}
        </span>
        <span className="inline-flex min-w-0 max-w-72 items-center gap-1 truncate font-semibold text-foreground">
          <FileText className="size-3 shrink-0" />
          <span className="truncate" title={filename ?? source.document_id ?? undefined}>
            {docLabel}
          </span>
        </span>
        {typeof source.chunk_index === "number" && (
          <span className="inline-flex items-center gap-1 font-mono">
            <Hash className="size-3" />
            {source.chunk_index}
          </span>
        )}
        {typeof source.page_no === "number" && (
          <span className="rounded-md border border-border bg-muted px-1.5 py-0.5 font-semibold text-foreground">
            p. {source.page_no}
          </span>
        )}
        {hasCharRange && (
          <span className="font-mono" title="character offsets in source">
            {source.char_start}-{source.char_end}
          </span>
        )}
      </div>
      <p className="line-clamp-4 whitespace-pre-wrap text-muted-foreground">{source.text}</p>
    </li>
  );
};

const RetrievalPanel = ({ meta }: { meta: RetrievalMeta | null }) => (
  <aside className="hidden min-h-0 border-l border-border bg-muted/35 lg:flex lg:flex-col">
    <div className="border-b border-border px-4 py-3">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Quote className="size-4" />
        Evidence ledger
      </div>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        Latest assistant retrieval, kept beside the answer for quick audit.
      </p>
    </div>
    {meta ? (
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="mb-3 grid grid-cols-2 gap-2">
          <PanelMetric label="collection" value={meta.collection ?? "none"} />
          <PanelMetric label="chunks" value={String(meta.sources.length)} />
          {meta.timings && (
            <PanelMetric label="total" value={formatWholeMs(meta.timings.total_ms)} />
          )}
          {meta.timings?.cache_hit ? (
            <PanelMetric
              label="cache"
              value={formatWholeMs(meta.timings.cache_ms || meta.timings.total_ms)}
            />
          ) : meta.timings ? (
            <PanelMetric label="rerank" value={formatWholeMs(meta.timings.rerank_ms)} />
          ) : null}
        </div>
        <ol className="grid gap-2">
          {meta.sources.slice(0, 8).map((source, index) => (
            <SourceCard key={source.id} index={index + 1} source={source} />
          ))}
        </ol>
      </div>
    ) : (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-xs leading-5 text-muted-foreground">
        Sources appear here after the first grounded response.
      </div>
    )}
  </aside>
);

const PanelMetric = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-2xl border border-border bg-background p-2">
    <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
      {label}
    </div>
    <div className="mt-1 truncate font-mono text-xs font-semibold">{value}</div>
  </div>
);

export const ChatMessages = ({ isStreaming, messages }: Props) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const latestMeta = useMemo(
    () =>
      [...messages].reverse().find((message) => message.role === "assistant" && message.meta)
        ?.meta ?? null,
    [messages],
  );

  useAutoScrollChat(bottomRef, messages, isStreaming);

  return (
    <div className="min-h-0 flex-1 overflow-hidden">
      <div className="grid h-full min-h-0 lg:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-h-0 overflow-y-auto px-4 py-6 md:px-6 lg:px-8">
          <div className="mx-auto flex max-w-3xl flex-col gap-6" role="log">
            {messages.map((message, index) =>
              message.role === "user" ? (
                <UserMessage content={message.content} key={message.id} />
              ) : (
                <AssistantMessage
                  isStreaming={
                    isStreaming && index === messages.length - 1 && message.role === "assistant"
                  }
                  key={message.id}
                  message={message}
                />
              ),
            )}
            <div ref={bottomRef} />
          </div>
        </div>
        <RetrievalPanel meta={latestMeta} />
      </div>
    </div>
  );
};

const useHighlightTimerCleanup = (highlightTimer: MutableRefObject<number | null>) => {
  useEffect(
    () => () => {
      if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current);
    },
    [highlightTimer],
  );
};

const useAutoScrollChat = (
  bottomRef: RefObject<HTMLDivElement | null>,
  messages: ChatMessage[],
  isStreaming: boolean,
) => {
  useEffect(() => {
    if (messages.length === 0 && !isStreaming) return;
    bottomRef.current?.scrollIntoView({
      behavior: "instant",
    });
  }, [bottomRef, messages, isStreaming]);
};
