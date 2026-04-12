"use client";

import { BookOpen } from "lucide-react";
import { memo, useEffect, useRef } from "react";
import { cn } from "@/lib/cn";
import type { QueryResult } from "@/types/bigrag";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: {
    collection: string;
    chunks: QueryResult[];
  };
};

interface Props {
  messages: ChatMessage[];
  isStreaming: boolean;
}

const Bubble = memo(({ message, isStreaming }: { message: ChatMessage; isStreaming: boolean }) => {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
      {!isUser && message.meta && (
        <div className="mb-1.5 flex items-center gap-1.5 rounded-md border border-border/60 bg-muted/60 px-2.5 py-1 text-[11px] text-muted-foreground">
          <BookOpen className="size-3 shrink-0" />
          <span>
            Retrieved {message.meta.chunks.length} chunks from{" "}
            <span className="font-medium text-foreground">{message.meta.collection}</span>
          </span>
        </div>
      )}
      <div
        className={cn(
          "max-w-[80%] whitespace-pre-wrap rounded-xl px-4 py-2.5 text-sm leading-relaxed",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
        )}
      >
        {message.content}
        {isStreaming && (
          <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-current align-text-bottom" />
        )}
      </div>
      {!isUser && message.meta && message.meta.chunks.length > 0 && (
        <details className="mt-1 text-xs">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            View sources
          </summary>
          <ol className="mt-2 space-y-1.5">
            {message.meta.chunks.map((c, i) => (
              <li
                key={c.id}
                className="rounded-md border border-border bg-card p-2 text-xs leading-snug"
              >
                <div className="mb-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                  <span className="font-mono font-semibold text-foreground">[{i + 1}]</span>
                  <span>score {c.score.toFixed(3)}</span>
                  {c.document_id && (
                    <span className="truncate font-mono">
                      {c.document_id.slice(0, 8)}#{c.chunk_index}
                    </span>
                  )}
                </div>
                <p className="line-clamp-4 whitespace-pre-wrap text-muted-foreground">{c.text}</p>
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
});
Bubble.displayName = "Bubble";

export const ChatMessages = ({ messages, isStreaming }: Props) => {
  const bottomRef = useRef<HTMLDivElement>(null);

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
            isStreaming={isStreaming && i === messages.length - 1 && m.role === "assistant"}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
