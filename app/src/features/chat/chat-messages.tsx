import type { ChatSource } from "@bigrag/client";
import { Link } from "@tanstack/react-router";
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
import {
  Children,
  cloneElement,
  isValidElement,
  type MutableRefObject,
  memo,
  type ReactNode,
  type RefObject,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/cn";
import type { QueryTimings } from "@/types/bigrag";

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
const MARKDOWN_PLUGINS = [remarkGfm];

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

type CitationChildProps = {
  children?: ReactNode;
};

const renderCitedChildren = (
  children: ReactNode,
  chunkCount: number,
  onCite: (n: number) => void,
): ReactNode =>
  Children.map(children, (child) => {
    if (typeof child === "string") {
      return renderInlineCitations(child, chunkCount, onCite);
    }
    if (!isValidElement<CitationChildProps>(child)) {
      return child;
    }
    if (child.type === "code" || child.type === "pre" || child.type === "a") {
      return child;
    }
    if (child.props.children === undefined) {
      return child;
    }
    return cloneElement(child, {
      children: renderCitedChildren(child.props.children, chunkCount, onCite),
    });
  });

const markdownComponents = (chunkCount: number, onCite: (n: number) => void): Components => ({
  a: ({ children, href }) => (
    <a
      className="font-semibold text-primary underline underline-offset-2 hover:text-primary/80"
      href={href}
      rel={href ? "noreferrer" : undefined}
      target={href ? "_blank" : undefined}
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-border pl-4 text-muted-foreground">
      {renderCitedChildren(children, chunkCount, onCite)}
    </blockquote>
  ),
  code: ({ children, className }) => (
    <code className={cn("rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.92em]", className)}>
      {children}
    </code>
  ),
  h1: ({ children }) => (
    <h1 className="mt-4 mb-2 text-xl font-semibold leading-7">
      {renderCitedChildren(children, chunkCount, onCite)}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-4 mb-2 text-lg font-semibold leading-7">
      {renderCitedChildren(children, chunkCount, onCite)}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-3 mb-1.5 text-base font-semibold leading-7">
      {renderCitedChildren(children, chunkCount, onCite)}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="mt-3 mb-1.5 text-sm font-semibold leading-6">
      {renderCitedChildren(children, chunkCount, onCite)}
    </h4>
  ),
  input: ({ checked }) => (
    <input
      checked={Boolean(checked)}
      className="mr-2 size-3.5 align-text-top"
      readOnly
      type="checkbox"
    />
  ),
  li: ({ children, className }) => (
    <li className={cn("pl-1", className)}>{renderCitedChildren(children, chunkCount, onCite)}</li>
  ),
  ol: ({ children, start }) => (
    <ol className="my-2 list-decimal space-y-1 pl-5" start={start}>
      {children}
    </ol>
  ),
  p: ({ children }) => <p className="my-2">{renderCitedChildren(children, chunkCount, onCite)}</p>,
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-lg bg-muted p-3 text-sm leading-6 [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-border">
      <table className="min-w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  td: ({ children }) => (
    <td className="border-border border-t px-3 py-2 align-top">
      {renderCitedChildren(children, chunkCount, onCite)}
    </td>
  ),
  th: ({ children }) => (
    <th className="bg-muted px-3 py-2 text-left font-semibold">
      {renderCitedChildren(children, chunkCount, onCite)}
    </th>
  ),
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
});

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

    const jumpToSource = useCallback(
      (n: number) => {
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
      },
      [message.meta?.sources],
    );

    const sourceCount = message.meta?.sources.length ?? 0;
    const hasError = message.status === "error" && Boolean(message.errorMessage);

    return (
      <article className="min-w-0 w-full">
        <div className="min-w-0 rounded-xl border border-border bg-card p-4">
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
              "text-[15px] leading-7 text-foreground",
              hasError &&
                "whitespace-pre-wrap rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm leading-6",
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

          <SourcesPanel
            detailsRef={detailsRef}
            highlight={highlight}
            message={message}
            sourceRefs={sourceRefs}
          />
        </div>
      </article>
    );
  },
);
AssistantMessage.displayName = "AssistantMessage";

const SourcesPanel = ({
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

const UserMessage = ({
  content,
  id,
  onEdit,
}: {
  content: string;
  id: string;
  onEdit?: (messageId: string, content: string) => void;
}) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);

  const openEdit = () => {
    setDraft(content);
    setEditing(true);
  };

  const submitEdit = () => {
    const trimmed = draft.trim();
    if (!trimmed || !onEdit) {
      setEditing(false);
      return;
    }
    onEdit(id, trimmed);
    setEditing(false);
  };

  return (
    <article className="group ml-auto max-w-[min(42rem,88%)] rounded-xl bg-muted px-4 py-3 text-sm font-semibold leading-6 text-foreground">
      <div className="flex items-start gap-3">
        <span className="whitespace-pre-wrap">{content}</span>
        {onEdit && (
          <button
            type="button"
            className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 hover:bg-background hover:text-foreground group-hover:opacity-100"
            onClick={openEdit}
            aria-label="Edit message"
          >
            <FilePenLine className="size-3.5" />
          </button>
        )}
      </div>
      <Modal
        open={editing}
        onClose={() => setEditing(false)}
        title="Edit message"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button onClick={submitEdit} disabled={!draft.trim()}>
              Save & resend
            </Button>
          </>
        }
      >
        <Textarea autoFocus onChange={(e) => setDraft(e.target.value)} rows={5} value={draft} />
      </Modal>
    </article>
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
    <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-6 md:px-6 lg:px-10">
      <div className="mx-auto flex min-w-0 max-w-4xl flex-col gap-4" role="log">
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

const MarkdownContent = memo(
  ({
    chunkCount,
    content,
    onCite,
  }: {
    chunkCount: number;
    content: string;
    onCite: (n: number) => void;
  }) => {
    const components = useMemo(() => markdownComponents(chunkCount, onCite), [chunkCount, onCite]);
    return (
      <ReactMarkdown components={components} remarkPlugins={MARKDOWN_PLUGINS}>
        {content}
      </ReactMarkdown>
    );
  },
);
MarkdownContent.displayName = "MarkdownContent";

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
