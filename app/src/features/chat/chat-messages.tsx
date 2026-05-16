import {
  AlertTriangle,
  BookOpen,
  ChevronRight,
  Database,
  FileText,
  Gauge,
  Hash,
  Search,
  Zap,
} from "lucide-react";
import {
  type MutableRefObject,
  memo,
  type ReactNode,
  type RefObject,
  useEffect,
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
          className="mx-0.5 inline-flex items-center rounded-md border border-border bg-muted px-1.5 align-baseline font-mono text-xs font-semibold text-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
      <article className="w-full">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted px-2 py-1 text-xs font-semibold text-muted-foreground">
                <BookOpen className="size-3.5" />
                Answer
              </span>
              {message.meta?.collection && (
                <span className="max-w-52 truncate rounded-md bg-muted px-2 py-1 font-mono text-xs font-semibold text-muted-foreground">
                  {message.meta.collection}
                </span>
              )}
            </div>
            {message.meta && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <Search className="size-3.5" />
                  {message.meta.sources.length} chunks
                </span>
                {message.meta.timings && (
                  <span className="inline-flex items-center gap-1 font-mono">
                    {message.meta.timings.cache_hit ? (
                      <Database className="size-3.5" />
                    ) : (
                      <Zap className="size-3.5" />
                    )}
                    {formatWholeMs(message.meta.timings.total_ms)}
                  </span>
                )}
              </div>
            )}
          </div>

          <div
            className={cn(
              "whitespace-pre-wrap text-[15px] leading-7 text-foreground",
              hasError &&
                "rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm leading-6",
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
              <span className="text-muted-foreground">
                Retrieving context and drafting answer...
              </span>
            )}
            {isStreaming && (
              <span className="ml-1 inline-block h-4 w-1.5 bg-current align-text-bottom" />
            )}
          </div>

          {message.meta && message.meta.sources.length > 0 && (
            <details ref={detailsRef} className="group mt-4 text-xs">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg border border-border bg-muted/45 px-3 py-2 font-semibold text-muted-foreground hover:bg-muted hover:text-foreground">
                <span className="inline-flex min-w-0 items-center gap-2">
                  <ChevronRight className="size-3.5 shrink-0 group-open:rotate-90" />
                  <span className="truncate">Sources</span>
                </span>
                <span className="shrink-0 font-mono">
                  {message.meta.sources.length}
                  {message.meta.timings ? ` / ${formatWholeMs(message.meta.timings.total_ms)}` : ""}
                </span>
              </summary>
              {message.meta.timings && <LatencyLedger timings={message.meta.timings} />}
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
        </div>
      </article>
    );
  },
);
AssistantMessage.displayName = "AssistantMessage";

const UserMessage = ({ content }: { content: string }) => (
  <article className="ml-auto max-w-[min(42rem,88%)] rounded-xl bg-muted px-4 py-3 text-sm font-semibold leading-6 text-foreground">
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
    <div className="mt-2 rounded-lg border border-border bg-background p-3 text-xs text-muted-foreground">
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
        "rounded-lg border bg-background p-3 text-xs leading-snug",
        highlight ? "border-foreground bg-muted" : "border-border",
      )}
    >
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <span className="rounded-md border border-border bg-card px-1.5 py-0.5 font-mono font-semibold text-foreground">
              [{index}]
            </span>
            <span className="inline-flex min-w-0 items-center gap-1 font-semibold text-foreground">
              <FileText className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate" title={filename ?? source.document_id ?? undefined}>
                {docLabel}
              </span>
            </span>
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
      <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-muted-foreground">{source.text}</p>
    </li>
  );
};

export const ChatMessages = ({ isStreaming, messages }: Props) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useAutoScrollChat(bottomRef, messages, isStreaming);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 md:px-6 lg:px-10">
      <div className="mx-auto flex max-w-4xl flex-col gap-4" role="log">
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
