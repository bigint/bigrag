"use client";

import { BookOpen, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { useCollections } from "@/hooks/use-collections";
import { apiClient } from "@/lib/api";
import { streamOpenAI } from "@/lib/openai-stream";
import { usePlaygroundStore } from "@/stores/playground";
import type { QueryResult } from "@/types/bigrag";
import { ChatInput } from "./components/chat-input";
import type { ChatMessage } from "./components/chat-messages";
import { ChatMessages } from "./components/chat-messages";
import { EmptyPrompts } from "./components/empty-prompts";

const newId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const PlaygroundPage = () => {
  const { openaiKey, model, topK, temperature, systemPrompt } = usePlaygroundStore();
  const { data, isPending } = useCollections();
  const collections = data?.collections ?? [];

  const [collection, setCollection] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-pick the first collection once available.
  useEffect(() => {
    if (!collection && collections.length > 0 && collections[0]) {
      setCollection(collections[0].name);
    }
  }, [collections, collection]);

  const stopStreaming = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  };

  const handleSend = async (text: string) => {
    if (!openaiKey) {
      toast.error("Paste your OpenAI API key first");
      return;
    }
    if (!collection) {
      toast.error("Pick a collection first");
      return;
    }

    const userMsg: ChatMessage = { id: newId(), role: "user", content: text };
    const assistantId = newId();
    const assistantMsg: ChatMessage = { id: assistantId, role: "assistant", content: "" };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    let chunks: QueryResult[] = [];
    try {
      const res = await apiClient.post<{ results: QueryResult[] }>(
        `v1/collections/${encodeURIComponent(collection)}/query`,
        { query: text, top_k: topK },
      );
      chunks = res.results;
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: `Retrieval failed: ${err instanceof Error ? err.message : "unknown error"}`,
              }
            : m,
        ),
      );
      setIsStreaming(false);
      return;
    }

    setMessages((prev) =>
      prev.map((m) => (m.id === assistantId ? { ...m, meta: { chunks, collection } } : m)),
    );

    const context = chunks.map((c, i) => `[${i + 1}] ${c.text}`).join("\n\n---\n\n");
    const contextBlock = context || "(no matching chunks were found)";

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamOpenAI({
        apiKey: openaiKey,
        model,
        temperature,
        signal: controller.signal,
        messages: [
          { role: "system", content: systemPrompt },
          {
            role: "system",
            content: `Context from collection "${collection}":\n\n${contextBlock}`,
          },
          { role: "user", content: text },
        ],
        onToken: (delta) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + delta } : m)),
          );
        },
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User pressed stop — leave partial response in place.
      } else {
        const message = err instanceof Error ? err.message : "OpenAI request failed";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content || `OpenAI error: ${message}` } : m,
          ),
        );
        toast.error(message);
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const clearMessages = () => {
    stopStreaming();
    setMessages([]);
  };

  return (
    <div className="flex h-[calc(100dvh-var(--spacing)*8)] flex-col md:-m-6 md:h-dvh md:p-6">
      <div className="flex items-center justify-between pb-4">
        <div>
          <h1 className="text-lg font-semibold">Playground</h1>
          <p className="text-sm text-muted-foreground">
            Chat your collection end-to-end — bigRAG retrieves, OpenAI answers.
          </p>
        </div>
        {messages.length > 0 && (
          <Button disabled={isStreaming} onClick={clearMessages} size="sm" variant="ghost">
            <RotateCcw className="size-3.5" />
            New chat
          </Button>
        )}
      </div>

      {isPending ? (
        <div className="flex flex-1 items-center justify-center rounded-xl border border-border">
          <Spinner size="lg" />
        </div>
      ) : collections.length === 0 ? (
        <div className="flex flex-1 items-center justify-center rounded-xl border border-border">
          <Empty
            action={
              <Link href="/collections">
                <Button>
                  <BookOpen className="size-4" />
                  Create a collection
                </Button>
              </Link>
            }
            bordered={false}
            description="Ingest some documents first, then come back here to chat with them."
            icon={<BookOpen className="size-6" />}
            title="No collections yet"
          />
        </div>
      ) : (
        <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border">
          {messages.length === 0 ? (
            <EmptyPrompts onSelect={handleSend} disabled={!openaiKey || !collection} />
          ) : (
            <ChatMessages isStreaming={isStreaming} messages={messages} />
          )}
          <ChatInput
            collection={collection}
            collections={collections}
            disabled={!openaiKey || !collection}
            isStreaming={isStreaming}
            onCollectionChange={setCollection}
            onSend={handleSend}
            onStop={stopStreaming}
          />
        </div>
      )}
    </div>
  );
};

export default PlaygroundPage;
