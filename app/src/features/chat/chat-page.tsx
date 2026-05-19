import { Button, Spinner } from "@atelier/ui";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { BookOpen, Clock3, FileText, type LucideIcon, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";
import { useShallow } from "zustand/react/shallow";
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
  const {
    appendMessages,
    clearMessages,
    collection,
    isStreaming,
    messages,
    selectCollection,
    selectFirstCollection,
    setMessages,
    setStreaming,
    updateMessage,
  } = useChatStore(
    useShallow((state) => ({
      appendMessages: state.appendMessages,
      clearMessages: state.clearMessages,
      collection: state.collection,
      isStreaming: state.isStreaming,
      messages: state.messages,
      selectCollection: state.selectCollection,
      selectFirstCollection: state.selectFirstCollection,
      setMessages: state.setMessages,
      setStreaming: state.setStreaming,
      updateMessage: state.updateMessage,
    })),
  );
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

  const patchState = useCallback(
    (patch: Partial<ChatState> & { openaiKey?: string }) => {
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
    },
    [updatePrefs],
  );

  const questionsQuery = useChatQuestionSuggestions(collection);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, [setStreaming]);

  const handleCollectionChange = useCallback(
    (name: string) => {
      selectCollection(name);
    },
    [selectCollection],
  );

  const handleGenerateQuestions = useCallback(() => {
    if (!collection) return;
    generateQuestions.mutate({
      collection: collection,
      model: state.model,
      temperature: state.temperature,
    });
  }, [collection, generateQuestions, state.model, state.temperature]);

  const handleSend = useCallback(
    async (text: string) => {
      if (isStreaming) return;
      if (!state.hasOpenAIKey) {
        toast.error("Add your OpenAI API key first");
        return;
      }
      if (!collection) {
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
      let deltaBuffer = "";
      let deltaFrame: number | null = null;
      const flushDelta = () => {
        deltaFrame = null;
        if (!deltaBuffer) return;
        const delta = deltaBuffer;
        deltaBuffer = "";
        updateMessage(currentAssistantId, (message) => ({
          ...message,
          content: message.content + delta,
        }));
      };
      const enqueueDelta = (delta: string) => {
        deltaBuffer += delta;
        if (deltaFrame === null) {
          deltaFrame = window.requestAnimationFrame(flushDelta);
        }
      };
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
            collection: collection,
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
              enqueueDelta(event.data.delta);
              return;
            }
            if (event.event === "assistant_message") {
              flushDelta();
              updateMessage(currentAssistantId, (message) => ({
                ...message,
                id: event.data.id,
                content: event.data.content,
                status: event.data.status,
                errorMessage: event.data.error_message,
                meta: {
                  collection: collection,
                  sources: event.data.sources,
                  timings: timingsFromRetrieval(event.data),
                },
              }));
              currentAssistantId = event.data.id;
              return;
            }
            if (event.event === "error") {
              flushDelta();
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
          flushDelta();
          updateMessage(currentAssistantId, (chatMessage) => ({
            ...chatMessage,
            status: "stopped",
          }));
        } else {
          const message = err instanceof Error ? err.message : "Chat request failed";
          flushDelta();
          updateMessage(currentAssistantId, (chatMessage) => ({
            ...chatMessage,
            status: "error",
            errorMessage: message,
          }));
          refreshPreferencesIfCredentialError(message);
          toast.error(message);
        }
      } finally {
        if (deltaFrame !== null) {
          window.cancelAnimationFrame(deltaFrame);
          flushDelta();
        }
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [
      appendMessages,
      collection,
      isStreaming,
      queryClient,
      setStreaming,
      state.hasOpenAIKey,
      state.model,
      state.rerank,
      state.searchMode,
      state.systemPrompt,
      state.temperature,
      state.topK,
      updateMessage,
    ],
  );

  const handleClear = useCallback(() => {
    stopStreaming();
    clearMessages();
  }, [clearMessages, stopStreaming]);

  const resendFrom = useCallback(
    (messageIndex: number, content: string) => {
      const currentMessages = useChatStore.getState().messages;
      setMessages(currentMessages.slice(0, messageIndex));
      void handleSend(content);
    },
    [handleSend, setMessages],
  );

  const handleEditUserMessage = useCallback(
    (messageId: string, content: string) => {
      const currentMessages = useChatStore.getState().messages;
      const index = currentMessages.findIndex((message) => message.id === messageId);
      if (index < 0) return;
      resendFrom(index, content);
    },
    [resendFrom],
  );

  const handleRegenerate = useCallback(
    (messageId: string) => {
      const currentMessages = useChatStore.getState().messages;
      const assistantIndex = currentMessages.findIndex((message) => message.id === messageId);
      if (assistantIndex < 0) return;
      let userIndex = -1;
      for (let index = assistantIndex - 1; index >= 0; index -= 1) {
        if (currentMessages[index].role === "user") {
          userIndex = index;
          break;
        }
      }
      if (userIndex < 0) return;
      resendFrom(userIndex, currentMessages[userIndex].content);
    },
    [resendFrom],
  );

  const loading = collectionsLoading || prefsQuery.isPending;
  const disabled = !state.hasOpenAIKey || !collection;

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
                collection={collection}
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
              collection={collection}
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
