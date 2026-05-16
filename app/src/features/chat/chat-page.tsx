import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { BookOpen, Clock3, FileText, type LucideIcon, Search } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ChatInput, type ChatState } from "@/features/chat/chat-input";
import type { ChatMessage } from "@/features/chat/chat-messages";
import { ChatMessages } from "@/features/chat/chat-messages";
import { useChatStore } from "@/features/chat/chat-store";
import { EmptyPrompts } from "@/features/chat/empty-prompts";
import { useChatQuestionSuggestions, useGenerateChatQuestions } from "@/hooks/use-chat";
import { useCollections } from "@/hooks/use-collections";
import { usePreferences, useUpdatePreferences } from "@/hooks/use-preferences";
import { streamChat } from "@/lib/chat-stream";
import { queryKeys } from "@/lib/query-keys";
import type { QueryTimings, ChatMessage as ServerChatMessage } from "@/types/bigrag";

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
  selectFirstCollection: (collections: readonly { name: string }[]) => void,
) => {
  useEffect(() => {
    if (!current) selectFirstCollection(collections);
  }, [collections, current, selectFirstCollection]);
};

const timingNumber = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : 0;

const normalizeTimings = (timings: unknown): QueryTimings | undefined => {
  if (!timings || typeof timings !== "object") return undefined;
  const raw = timings as Record<string, unknown>;
  return {
    embed_ms: timingNumber(raw.embed_ms),
    search_ms: timingNumber(raw.search_ms),
    rerank_ms: timingNumber(raw.rerank_ms),
    cache_ms: timingNumber(raw.cache_ms),
    total_ms: timingNumber(raw.total_ms),
    cache_hit: raw.cache_hit === true,
  };
};

const timingsFromRetrieval = (message: ServerChatMessage): QueryTimings | undefined => {
  return normalizeTimings(message.retrieval.timings);
};

export const ChatPage = () => {
  const queryClient = useQueryClient();
  const prefsQuery = usePreferences();
  const updatePrefs = useUpdatePreferences();
  const generateQuestions = useGenerateChatQuestions();
  const { data: collectionsData, isPending: collectionsLoading } = useCollections();
  const collections = useMemo(() => collectionsData?.collections ?? [], [collectionsData]);
  const collection = useChatStore((state) => state.collection);
  const messages = useChatStore((state) => state.messages);
  const isStreaming = useChatStore((state) => state.isStreaming);
  const appendMessages = useChatStore((state) => state.appendMessages);
  const clearMessages = useChatStore((state) => state.clearMessages);
  const selectCollection = useChatStore((state) => state.selectCollection);
  const selectFirstCollection = useChatStore((state) => state.selectFirstCollection);
  const setMessages = useChatStore((state) => state.setMessages);
  const setStreaming = useChatStore((state) => state.setStreaming);
  const updateMessage = useChatStore((state) => state.updateMessage);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      abortRef.current?.abort();
      abortRef.current = null;
      setStreaming(false);
    },
    [setStreaming],
  );

  useSelectFirstCollection(collections, collection, selectFirstCollection);

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

  const currentCollection = collection;
  const currentCollectionName = currentCollection;
  const questionsQuery = useChatQuestionSuggestions(currentCollectionName);

  const stopStreaming = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  };

  const handleCollectionChange = (name: string) => {
    selectCollection(name);
  };

  const handleGenerateQuestions = () => {
    if (!currentCollectionName) return;
    generateQuestions.mutate({
      collection: currentCollectionName,
      model: state.model,
      temperature: state.temperature,
    });
  };

  const handleSend = async (text: string) => {
    if (isStreaming) return;
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
    let currentAssistantId = assistantId;
    const userMsg: ChatMessage = { id: userId, role: "user", content: text };
    const assistantMsg: ChatMessage = { id: assistantId, role: "assistant", content: "" };
    appendMessages([userMsg, assistantMsg]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;
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
          collection: currentCollection,
          model_provider: "openai",
          model: state.model,
          temperature: state.temperature,
          top_k: state.topK,
          search_mode: state.searchMode,
          rerank: state.rerank,
          system_prompt: state.systemPrompt,
        },
        onEvent: (event) => {
          if (event.event === "sources") {
            updateMessage(currentAssistantId, (message) => ({
              ...message,
              meta: {
                collection: event.data.collection,
                sources: event.data.sources,
                timings: normalizeTimings(event.data.timings),
              },
            }));
            return;
          }
          if (event.event === "delta") {
            updateMessage(currentAssistantId, (message) => ({
              ...message,
              content: message.content + event.data.delta,
            }));
            return;
          }
          if (event.event === "assistant_message") {
            updateMessage(currentAssistantId, (message) => ({
              ...message,
              id: event.data.id,
              content: event.data.content,
              status: event.data.status,
              errorMessage: event.data.error_message,
              meta: {
                collection: currentCollection,
                sources: event.data.sources,
                timings: timingsFromRetrieval(event.data),
              },
            }));
            currentAssistantId = event.data.id;
            return;
          }
          if (event.event === "error") {
            updateMessage(currentAssistantId, (message) => ({
              ...message,
              status: "error",
              errorMessage: event.data.error,
            }));
            refreshPreferencesIfCredentialError(event.data.error);
            toast.error(event.data.error);
          }
        },
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        updateMessage(currentAssistantId, (chatMessage) => ({
          ...chatMessage,
          status: "stopped",
        }));
      } else {
        const message = err instanceof Error ? err.message : "Chat request failed";
        updateMessage(currentAssistantId, (chatMessage) => ({
          ...chatMessage,
          status: "error",
          errorMessage: message,
        }));
        refreshPreferencesIfCredentialError(message);
        toast.error(message);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const handleClear = () => {
    stopStreaming();
    clearMessages();
  };

  const resendFrom = (messageIndex: number, content: string) => {
    setMessages(messages.slice(0, messageIndex));
    void handleSend(content);
  };

  const handleEditUserMessage = (messageId: string, content: string) => {
    const index = messages.findIndex((message) => message.id === messageId);
    if (index < 0) return;
    resendFrom(index, content);
  };

  const handleRegenerate = (messageId: string) => {
    const assistantIndex = messages.findIndex((message) => message.id === messageId);
    if (assistantIndex < 0) return;
    const userIndex = messages
      .slice(0, assistantIndex)
      .findLastIndex((message) => message.role === "user");
    if (userIndex < 0) return;
    resendFrom(userIndex, messages[userIndex].content);
  };

  const loading = collectionsLoading || prefsQuery.isPending;
  const disabled = !state.hasOpenAIKey || !currentCollection;

  return (
    <div className="relative flex min-h-0 flex-1 overflow-hidden bg-background">
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {loading ? (
          <LoadingState />
        ) : collections.length === 0 ? (
          <NoCollectionsState />
        ) : (
          <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
            {messages.length === 0 ? (
              <EmptyPrompts
                collection={currentCollectionName}
                collectionCount={collections.length}
                disabled={disabled}
                hasOpenAIKey={state.hasOpenAIKey}
                isGeneratingQuestions={generateQuestions.isPending}
                onGenerateQuestions={handleGenerateQuestions}
                onSelect={handleSend}
                questions={questionsQuery.data?.questions ?? []}
              />
            ) : (
              <ChatMessages
                isStreaming={isStreaming}
                messages={messages}
                onClear={handleClear}
                onEditUserMessage={handleEditUserMessage}
                onRegenerate={handleRegenerate}
                onResume={handleRegenerate}
              />
            )}
            <ChatInput
              collection={currentCollectionName}
              collections={collections}
              disabled={disabled}
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
      </section>
    </div>
  );
};

const LoadingState = ({ label = "Loading chat" }: { label?: string }) => (
  <div className="flex flex-1 items-center justify-center">
    <div className="flex items-center gap-3 rounded-2xl border border-border bg-background px-4 py-3 text-sm font-semibold">
      <Spinner />
      {label}
    </div>
  </div>
);

const NoCollectionsState = () => (
  <div className="flex flex-1 items-center justify-center px-4 py-8">
    <div className="w-full max-w-xl rounded-xl border border-border bg-background p-6 text-center">
      <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-2xl border border-border bg-muted">
        <BookOpen className="size-6 text-muted-foreground" />
      </div>
      <h2 className="text-lg font-semibold">No collections available</h2>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
        Create or ingest a collection first. Chat needs indexed documents before it can retrieve
        evidence.
      </p>
      <div className="mt-5">
        <Link to="/collections">
          <Button>
            <FileText className="size-4" />
            Open collections
          </Button>
        </Link>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
        <NoCollectionMetric icon={BookOpen} label="Create" />
        <NoCollectionMetric icon={Clock3} label="Ingest" />
        <NoCollectionMetric icon={Search} label="Query" />
      </div>
    </div>
  </div>
);

const NoCollectionMetric = ({ icon: Icon, label }: { icon: LucideIcon; label: string }) => (
  <div className="rounded-2xl border border-border bg-muted/40 px-2 py-2">
    <Icon className="mx-auto mb-1 size-3.5" />
    {label}
  </div>
);
