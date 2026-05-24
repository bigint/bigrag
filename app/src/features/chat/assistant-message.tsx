import {
  AlertTriangle,
  BookOpen,
  Copy,
  Database,
  Play,
  RotateCcw,
  Search,
  Zap,
} from "lucide-react";
import { type MutableRefObject, memo, useCallback, useEffect, useRef, useState } from "react";
import { type ChatMessage, formatWholeMs } from "@/features/chat/chat-message-types";
import { MarkdownContent } from "@/features/chat/markdown/cited-markdown";
import { SourcesPanel } from "@/features/chat/sources-panel";
import { cn } from "@/lib/cn";

const useHighlightTimerCleanup = (highlightTimer: MutableRefObject<number | null>) => {
  useEffect(
    () => () => {
      if (highlightTimer.current !== null) window.clearTimeout(highlightTimer.current);
    },
    [highlightTimer],
  );
};

export const AssistantMessage = memo(
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
