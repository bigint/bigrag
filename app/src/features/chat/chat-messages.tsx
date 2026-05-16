import {
  AlertTriangle,
  BookOpen,
  ChevronRight,
  Copy,
  Database,
  FilePenLine,
  FileText,
  Gauge,
  Hash,
  Play,
  RotateCcw,
  Search,
  Trash2,
  Zap,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
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
  status?: "complete" | "error" | "stopped";
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
  onClear?: () => void;
  onEditUserMessage?: (messageId: string, content: string) => void;
  onRegenerate?: (messageId: string) => void;
  onResume?: (messageId: string) => void;
}

const CITATION_RE = /\[([0-9]+(?:\s*,\s*[0-9]+)*)\]/g;

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
    const citations = (match[1] ?? "")
      .split(",")
      .map((value) => Number.parseInt(value.trim(), 10))
      .filter((value) => Number.isFinite(value));
    const valid = citations.length > 0 && citations.every((n) => n >= 1 && n <= chunkCount);
    if (valid) {
      nodes.push(
        <span key={`c-${key++}`} className="inline-flex items-center gap-0.5">
          {citations.map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => onCite(n)}
              className="mx-0.5 inline-flex items-center rounded-md border border-border bg-muted px-1.5 align-baseline font-mono text-xs font-semibold text-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Jump to source ${n}`}
            >
              [{n}]
            </button>
          ))}
        </span>,
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
  ({
    isStreaming,
    message,
    onRegenerate,
    onResume,
  }: {
    isStreaming: boolean;
    message: ChatMessage;
    onRegenerate?: (messageId: string) => void;
    onResume?: (messageId: string) => void;
  }) => {
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
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {message.meta && (
                <>
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
                </>
              )}
              {message.content && (
                <button
                  type="button"
                  className="inline-flex size-7 items-center justify-center rounded-md hover:bg-muted hover:text-foreground"
                  onClick={() => navigator.clipboard.writeText(message.content)}
                  aria-label="Copy answer"
                >
                  <Copy className="size-3.5" />
                </button>
              )}
              {message.status === "stopped" && onResume ? (
                <button
                  type="button"
                  className="inline-flex size-7 items-center justify-center rounded-md hover:bg-muted hover:text-foreground"
                  onClick={() => onResume(message.id)}
                  aria-label="Resume answer"
                >
                  <Play className="size-3.5" />
                </button>
              ) : (
                onRegenerate && (
                  <button
                    type="button"
                    className="inline-flex size-7 items-center justify-center rounded-md hover:bg-muted hover:text-foreground"
                    onClick={() => onRegenerate(message.id)}
                    aria-label="Regenerate answer"
                  >
                    <RotateCcw className="size-3.5" />
                  </button>
                )
              )}
            </div>
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
              <MarkdownContent
                chunkCount={sourceCount}
                content={message.content}
                onCite={jumpToSource}
              />
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
                    collection={message.meta.collection}
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

const UserMessage = ({
  content,
  id,
  onEdit,
}: {
  content: string;
  id: string;
  onEdit?: (messageId: string, content: string) => void;
}) => (
  <article className="group ml-auto max-w-[min(42rem,88%)] rounded-xl bg-muted px-4 py-3 text-sm font-semibold leading-6 text-foreground">
    <div className="flex items-start gap-3">
      <span className="whitespace-pre-wrap">{content}</span>
      {onEdit && (
        <button
          type="button"
          className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 hover:bg-background hover:text-foreground group-hover:opacity-100"
          onClick={() => {
            const next = window.prompt("Edit message", content);
            if (next?.trim()) onEdit(id, next.trim());
          }}
          aria-label="Edit message"
        >
          <FilePenLine className="size-3.5" />
        </button>
      )}
    </div>
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
            {collection && source.document_id ? (
              <Link
                to="/collections/$name/documents/$docId"
                params={{ name: collection, docId: source.document_id }}
                hash={typeof source.chunk_index === "number" ? `chunk-${source.chunk_index}` : undefined}
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
      <p className="mt-2 line-clamp-3 whitespace-pre-wrap text-muted-foreground">{source.text}</p>
    </li>
  );
};

export const ChatMessages = ({
  isStreaming,
  messages,
  onClear,
  onEditUserMessage,
  onRegenerate,
  onResume,
}: Props) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useAutoScrollChat(bottomRef, messages, isStreaming);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 md:px-6 lg:px-10">
      <div className="mx-auto flex max-w-4xl flex-col gap-4" role="log">
        {messages.length > 0 && onClear && (
          <div className="flex justify-end">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1.5 text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={onClear}
            >
              <Trash2 className="size-3.5" />
              Clear
            </button>
          </div>
        )}
        {messages.map((message, index) =>
          message.role === "user" ? (
            <UserMessage
              content={message.content}
              id={message.id}
              key={message.id}
              onEdit={onEditUserMessage}
            />
          ) : (
            <AssistantMessage
              isStreaming={
                isStreaming && index === messages.length - 1 && message.role === "assistant"
              }
              key={message.id}
              message={message}
              onRegenerate={onRegenerate}
              onResume={onResume}
            />
          ),
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

const MarkdownContent = ({
  chunkCount,
  content,
  onCite,
}: {
  chunkCount: number;
  content: string;
  onCite: (n: number) => void;
}) => {
  const blocks = content.split(/\n{2,}/);
  return (
    <>
      {blocks.map((block, index) => {
        const key = `${index}-${block.slice(0, 12)}`;
        if (block.startsWith("```")) {
          const code = block.replace(/^```[^\n]*\n?/, "").replace(/```$/, "");
          return (
            <pre key={key} className="my-3 overflow-x-auto rounded-lg bg-muted p-3 text-sm">
              <code>{code}</code>
            </pre>
          );
        }
        if (/^[-*] \[[ xX]\] /m.test(block)) {
          return (
            <ul key={key} className="my-2 grid gap-1">
              {block.split("\n").map((line) => {
                const checked = /^[-*] \[[xX]\] /.test(line);
                const text = line.replace(/^[-*] \[[ xX]\] /, "");
                return (
                  <li key={line} className="flex items-start gap-2">
                    <input type="checkbox" checked={checked} readOnly className="mt-1 size-3.5" />
                    <span>{renderInlineCitations(text, chunkCount, onCite)}</span>
                  </li>
                );
              })}
            </ul>
          );
        }
        if (/^[-*] /m.test(block)) {
          return (
            <ul key={key} className="my-2 list-disc space-y-1 pl-5">
              {block.split("\n").map((line) => (
                <li key={line}>{renderInlineCitations(line.replace(/^[-*] /, ""), chunkCount, onCite)}</li>
              ))}
            </ul>
          );
        }
        if (/^\d+\. /m.test(block)) {
          return (
            <ol key={key} className="my-2 list-decimal space-y-1 pl-5">
              {block.split("\n").map((line) => (
                <li key={line}>{renderInlineCitations(line.replace(/^\d+\. /, ""), chunkCount, onCite)}</li>
              ))}
            </ol>
          );
        }
        if (block.includes("\n|") && block.includes("|")) {
          return (
            <pre key={key} className="my-3 overflow-x-auto rounded-lg border border-border bg-muted p-3 text-xs">
              {block}
            </pre>
          );
        }
        return (
          <p key={key} className="my-2">
            {renderInlineCitations(block, chunkCount, onCite)}
          </p>
        );
      })}
    </>
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
