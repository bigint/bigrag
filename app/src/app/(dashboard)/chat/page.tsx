"use client";

import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, MessageSquare, Plus, RotateCcw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import {
  useChatConversation,
  useChatConversations,
  useDeleteChatConversation,
} from "@/hooks/use-chat";
import { useCollections } from "@/hooks/use-collections";
import { usePreferences, useUpdatePreferences } from "@/hooks/use-preferences";
import { streamChat } from "@/lib/chat-stream";
import { cn } from "@/lib/cn";
import { queryKeys } from "@/lib/query-keys";
import type {
  ChatConversation,
  QueryTimings,
  ChatMessage as ServerChatMessage,
} from "@/types/bigrag";
import { ChatInput, type ChatState } from "./components/chat-input";
import type { ChatMessage } from "./components/chat-messages";
import { ChatMessages } from "./components/chat-messages";
import { EmptyPrompts } from "./components/empty-prompts";

const newId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

const DEFAULT_SYSTEM =
  "You are bigRAG's grounded chat assistant. Answer using only the retrieved context. " +
  "If the context does not contain the answer, say you do not know. Cite every factual " +
  "claim with bracketed source numbers like [1] or [2].";

const DEFAULT_STATE: ChatState = {
  hasOpenAIKey: false,
  model: "gpt-4o-mini",
  topK: 5,
  temperature: 0.2,
  searchMode: "semantic",
  rerank: false,
  systemPrompt: DEFAULT_SYSTEM,
};

const useSelectFirstCollection = (
  collections: { name: string }[],
  current: string,
  setCurrent: (name: string) => void,
) => {
  useEffect(() => {
    const first = collections[0];
    if (!current && first) setCurrent(first.name);
  }, [collections, current, setCurrent]);
};

const timingsFromRetrieval = (message: ServerChatMessage): QueryTimings | undefined => {
  const timings = message.retrieval.timings;
  if (!timings || typeof timings !== "object") return undefined;
  return timings as QueryTimings;
};

const toUiMessage = (
  message: ServerChatMessage,
  conversation: ChatConversation,
): ChatMessage | null => {
  if (message.role === "system") return null;
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    status: message.status,
    errorMessage: message.error_message,
    meta:
      message.role === "assistant"
        ? {
            collection: conversation.collection,
            sources: message.sources,
            timings: timingsFromRetrieval(message),
          }
        : undefined,
  };
};

const ChatPage = () => {
  const queryClient = useQueryClient();
  const prefsQuery = usePreferences();
  const updatePrefs = useUpdatePreferences();
  const conversationsQuery = useChatConversations();
  const deleteConversation = useDeleteChatConversation();
  const { data: collectionsData, isPending: collectionsLoading } = useCollections();
  const collections = useMemo(() => collectionsData?.collections ?? [], [collectionsData]);
  const [collection, setCollection] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const detailQuery = useChatConversation(conversationId);
  const activeConversation = detailQuery.data?.conversation ?? null;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useSelectFirstCollection(collections, collection, setCollection);

  useEffect(() => {
    if (!conversationId || isStreaming || !detailQuery.data) return;
    setMessages(
      detailQuery.data.messages
        .map((message) => toUiMessage(message, detailQuery.data.conversation))
        .filter((message): message is ChatMessage => Boolean(message)),
    );
  }, [conversationId, detailQuery.data, isStreaming]);

  const state: ChatState = useMemo(() => {
    const chat = prefsQuery.data?.data.chat ?? {};
    return {
      hasOpenAIKey: Boolean(chat.has_openai_key || chat.openai_key),
      model: chat.model ?? DEFAULT_STATE.model,
      topK: typeof chat.top_k === "number" ? chat.top_k : DEFAULT_STATE.topK,
      temperature:
        typeof chat.temperature === "number" ? chat.temperature : DEFAULT_STATE.temperature,
      searchMode: chat.search_mode ?? DEFAULT_STATE.searchMode,
      rerank: typeof chat.rerank === "boolean" ? chat.rerank : DEFAULT_STATE.rerank,
      systemPrompt: chat.system_prompt ?? DEFAULT_STATE.systemPrompt,
    };
  }, [prefsQuery.data]);

  const patchState = (patch: Partial<ChatState> & { openaiKey?: string }) => {
    const mapped: Record<string, unknown> = {};
    if (patch.openaiKey !== undefined) mapped.openai_key = patch.openaiKey;
    if (patch.model !== undefined) mapped.model = patch.model;
    if (patch.topK !== undefined) mapped.top_k = patch.topK;
    if (patch.temperature !== undefined) mapped.temperature = patch.temperature;
    if (patch.searchMode !== undefined) mapped.search_mode = patch.searchMode;
    if (patch.rerank !== undefined) mapped.rerank = patch.rerank;
    if (patch.systemPrompt !== undefined) mapped.system_prompt = patch.systemPrompt;
    updatePrefs.mutate(
      { chat: mapped },
      {
        onSuccess: () => {
          if (patch.openaiKey !== undefined) {
            toast.success(patch.openaiKey ? "OpenAI key saved" : "OpenAI key cleared");
          }
        },
        onError: (error) => {
          if (patch.openaiKey !== undefined) {
            toast.error(error instanceof Error ? error.message : "Could not save OpenAI key");
          }
        },
      },
    );
  };

  const currentCollection = activeConversation?.collection ?? collection;

  const stopStreaming = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  };

  const startNewChat = () => {
    stopStreaming();
    setConversationId(null);
    setMessages([]);
  };

  const handleCollectionChange = (name: string) => {
    if (conversationId) {
      setConversationId(null);
      setMessages([]);
    }
    setCollection(name);
  };

  const handleSend = async (text: string) => {
    if (!state.hasOpenAIKey) {
      toast.error("Add your OpenAI API key first");
      return;
    }
    if (!currentCollection) {
      toast.error("Pick a collection first");
      return;
    }

    const userId = newId();
    const assistantId = newId();
    const userMsg: ChatMessage = { id: userId, role: "user", content: text };
    const assistantMsg: ChatMessage = { id: assistantId, role: "assistant", content: "" };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;
    let nextConversationId = conversationId;
    const refreshPreferencesIfCredentialError = (message: string) => {
      if (message.includes("OpenAI rejected") || message.includes("Save an OpenAI API key")) {
        queryClient.invalidateQueries({ queryKey: queryKeys.preferences() });
      }
    };

    try {
      await streamChat({
        signal: controller.signal,
        body: {
          message: text,
          conversation_id: conversationId,
          collection: conversationId ? undefined : currentCollection,
          model_provider: "openai",
          model: state.model,
          temperature: state.temperature,
          top_k: state.topK,
          search_mode: state.searchMode,
          rerank: state.rerank,
          system_prompt: state.systemPrompt,
        },
        onEvent: (event) => {
          if (event.event === "conversation") {
            nextConversationId = event.data.id;
            setConversationId(event.data.id);
            return;
          }
          if (event.event === "user_message") {
            setMessages((prev) =>
              prev.map((m) => (m.id === userId ? { ...m, id: event.data.id } : m)),
            );
            return;
          }
          if (event.event === "sources") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      meta: {
                        collection: event.data.collection,
                        sources: event.data.sources,
                        timings: event.data.timings,
                      },
                    }
                  : m,
              ),
            );
            return;
          }
          if (event.event === "delta") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + event.data.delta } : m,
              ),
            );
            return;
          }
          if (event.event === "assistant_message") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      id: event.data.id,
                      content: event.data.content,
                      status: event.data.status,
                      errorMessage: event.data.error_message,
                      meta: {
                        collection: currentCollection,
                        sources: event.data.sources,
                        timings: timingsFromRetrieval(event.data),
                      },
                    }
                  : m,
              ),
            );
            return;
          }
          if (event.event === "done") {
            queryClient.invalidateQueries({ queryKey: queryKeys.chat.list() });
            queryClient.invalidateQueries({
              queryKey: queryKeys.chat.detail(event.data.conversation.id),
            });
            return;
          }
          if (event.event === "error") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, status: "error", errorMessage: event.data.error }
                  : m,
              ),
            );
            refreshPreferencesIfCredentialError(event.data.error);
            toast.error(event.data.error);
          }
        },
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
      } else {
        const message = err instanceof Error ? err.message : "Chat request failed";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, status: "error", errorMessage: message } : m,
          ),
        );
        refreshPreferencesIfCredentialError(message);
        toast.error(message);
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      queryClient.invalidateQueries({ queryKey: queryKeys.chat.list() });
      if (nextConversationId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.chat.detail(nextConversationId) });
      }
    }
  };

  const conversations = conversationsQuery.data?.conversations ?? [];

  return (
    <div className="relative flex min-h-0 flex-1 overflow-hidden bg-background">
      <ConversationRail
        conversations={conversations}
        deletingId={deleteConversation.variables ?? null}
        onDelete={(id) => {
          if (id === conversationId) startNewChat();
          deleteConversation.mutate(id);
        }}
        onNew={startNewChat}
        onSelect={(id) => {
          stopStreaming();
          setConversationId(id);
        }}
        selectedId={conversationId}
      />

      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        {messages.length > 0 && (
          <div className="absolute top-5 right-3 z-20 hidden lg:block">
            <Button disabled={isStreaming} onClick={startNewChat} size="sm" variant="ghost">
              <RotateCcw className="size-3.5" />
              New chat
            </Button>
          </div>
        )}
        {collectionsLoading || prefsQuery.isPending || conversationsQuery.isPending ? (
          <div className="flex flex-1 items-center justify-center">
            <Spinner size="lg" />
          </div>
        ) : collections.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
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
              description="Ingest documents first, then chat with them here."
              icon={<BookOpen className="size-6" />}
              title="No collections yet"
            />
          </div>
        ) : detailQuery.isFetching && conversationId && messages.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <Spinner size="lg" />
          </div>
        ) : (
          <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
            {messages.length === 0 ? (
              <EmptyPrompts
                onSelect={handleSend}
                disabled={!state.hasOpenAIKey || !currentCollection}
              />
            ) : (
              <ChatMessages isStreaming={isStreaming} messages={messages} />
            )}
            <ChatInput
              collection={currentCollection ?? ""}
              collections={collections}
              disabled={!state.hasOpenAIKey || !currentCollection}
              isStreaming={isStreaming}
              onCollectionChange={handleCollectionChange}
              onPatch={patchState}
              onSend={handleSend}
              onStop={stopStreaming}
              saving={updatePrefs.isPending}
              state={state}
            />
          </div>
        )}
      </div>
    </div>
  );
};

const ConversationRail = ({
  conversations,
  deletingId,
  onDelete,
  onNew,
  onSelect,
  selectedId,
}: {
  conversations: ChatConversation[];
  deletingId: string | null;
  onDelete: (id: string) => void;
  onNew: () => void;
  onSelect: (id: string) => void;
  selectedId: string | null;
}) => (
  <aside className="hidden w-72 shrink-0 flex-col border-r border-border bg-muted/40 lg:flex">
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-3 py-3">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <MessageSquare className="size-4" />
        Chats
      </div>
      <Button
        aria-label="New chat"
        className="size-8 p-0"
        onClick={onNew}
        size="sm"
        variant="ghost"
      >
        <Plus className="size-4" />
      </Button>
    </div>
    <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
      {conversations.length === 0 ? (
        <div className="px-2 py-8 text-center text-xs text-muted-foreground">
          Conversation history will appear here.
        </div>
      ) : (
        conversations.map((conversation) => (
          <div
            key={conversation.id}
            className={cn(
              "group flex items-center gap-1 rounded-2xl",
              selectedId === conversation.id && "bg-background",
            )}
          >
            <button
              type="button"
              onClick={() => onSelect(conversation.id)}
              className="min-w-0 flex-1 rounded-2xl px-3 py-2 text-left hover:bg-background"
            >
              <div className="truncate text-xs font-semibold">{conversation.title}</div>
              <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="truncate">{conversation.collection ?? "No collection"}</span>
                <span aria-hidden>·</span>
                <span>{conversation.message_count}</span>
              </div>
            </button>
            <button
              type="button"
              aria-label="Delete conversation"
              disabled={deletingId === conversation.id}
              onClick={() => onDelete(conversation.id)}
              className="mr-1 hidden size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-destructive/10 hover:text-destructive group-hover:flex focus-visible:flex focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>
        ))
      )}
    </div>
  </aside>
);

export default ChatPage;
