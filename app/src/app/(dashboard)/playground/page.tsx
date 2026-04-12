"use client";

import { BookOpen, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { useCollections } from "@/hooks/use-collections";
import { usePreferences, useUpdatePreferences } from "@/hooks/use-preferences";
import { apiClient } from "@/lib/api";
import { streamOpenAI } from "@/lib/openai-stream";
import type { QueryResult } from "@/types/bigrag";
import { ChatInput, type PlaygroundState } from "./components/chat-input";
import type { ChatMessage } from "./components/chat-messages";
import { ChatMessages } from "./components/chat-messages";
import { EmptyPrompts } from "./components/empty-prompts";

const newId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const DEFAULT_SYSTEM =
  "You are a helpful assistant. Answer the user's question using ONLY the context below. " +
  "If the answer isn't in the context, say you don't know — don't make things up. " +
  "Cite chunk numbers like [1], [2] when you use them.";

const DEFAULT_STATE: PlaygroundState = {
  openaiKey: "",
  model: "gpt-4o-mini",
  topK: 5,
  temperature: 0.2,
  systemPrompt: DEFAULT_SYSTEM,
};

const PlaygroundPage = () => {
  const prefsQuery = usePreferences();
  const updatePrefs = useUpdatePreferences();
  const { data: collectionsData, isPending: collectionsLoading } = useCollections();
  const collections = useMemo(() => collectionsData?.collections ?? [], [collectionsData]);

  const state: PlaygroundState = useMemo(() => {
    const p = prefsQuery.data?.data.playground ?? {};
    return {
      openaiKey: p.openai_key ?? DEFAULT_STATE.openaiKey,
      model: p.model ?? DEFAULT_STATE.model,
      topK: typeof p.top_k === "number" ? p.top_k : DEFAULT_STATE.topK,
      temperature: typeof p.temperature === "number" ? p.temperature : DEFAULT_STATE.temperature,
      systemPrompt: p.system_prompt ?? DEFAULT_STATE.systemPrompt,
    };
  }, [prefsQuery.data]);

  const patchState = (patch: Partial<PlaygroundState>) => {
    const mapped: Record<string, unknown> = {};
    if (patch.openaiKey !== undefined) mapped.openai_key = patch.openaiKey;
    if (patch.model !== undefined) mapped.model = patch.model;
    if (patch.topK !== undefined) mapped.top_k = patch.topK;
    if (patch.temperature !== undefined) mapped.temperature = patch.temperature;
    if (patch.systemPrompt !== undefined) mapped.system_prompt = patch.systemPrompt;
    updatePrefs.mutate({ playground: mapped });
  };

  const [collection, setCollection] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const first = collections[0];
    if (!collection && first) setCollection(first.name);
  }, [collections, collection]);

  const stopStreaming = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  };

  const handleSend = async (text: string) => {
    if (!state.openaiKey) {
      toast.error("Add your OpenAI API key first");
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
        { query: text, top_k: state.topK },
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
        apiKey: state.openaiKey,
        model: state.model,
        temperature: state.temperature,
        signal: controller.signal,
        messages: [
          { role: "system", content: state.systemPrompt },
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
        // user pressed stop — keep partial response
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

      {collectionsLoading || prefsQuery.isPending ? (
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
            <EmptyPrompts onSelect={handleSend} disabled={!state.openaiKey || !collection} />
          ) : (
            <ChatMessages isStreaming={isStreaming} messages={messages} />
          )}
          <ChatInput
            collection={collection}
            collections={collections}
            disabled={!state.openaiKey || !collection}
            isStreaming={isStreaming}
            onCollectionChange={setCollection}
            onPatch={patchState}
            onSend={handleSend}
            onStop={stopStreaming}
            saving={updatePrefs.isPending}
            state={state}
          />
        </div>
      )}
    </div>
  );
};

export default PlaygroundPage;
