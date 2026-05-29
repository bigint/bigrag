import { useCallback, useEffect, useMemo } from "react";
import { toast } from "sonner";
import { useShallow } from "zustand/react/shallow";
import type { ChatState } from "@/features/chat/chat-input";
import { defaultChatState } from "@/features/chat/chat-page-defaults";
import { useChatStore } from "@/features/chat/chat-store";
import { useChatStreaming } from "@/features/chat/use-chat-streaming";
import { useChatQuestionSuggestions, useGenerateChatQuestions } from "@/hooks/use-chat";
import { useCollections } from "@/hooks/use-collections";
import { usePreferences, useUpdatePreferences } from "@/hooks/use-preferences";

const useSelectAvailableCollection = (
  collections: { name: string }[],
  current: string,
  selectCollection: (collection: string) => void,
) => {
  useEffect(() => {
    const first = collections[0]?.name ?? "";
    if (!current && first) {
      selectCollection(first);
      return;
    }
    if (current && !collections.some((item) => item.name === current)) {
      selectCollection(first);
    }
  }, [collections, current, selectCollection]);
};

export const useChatPageController = () => {
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
      setMessages: state.setMessages,
      setStreaming: state.setStreaming,
      updateMessage: state.updateMessage,
    })),
  );

  useSelectAvailableCollection(collections, collection, selectCollection);

  const state: ChatState = useMemo(() => {
    const chat = prefsQuery.data?.data.chat ?? {};
    return {
      hasOpenAIKey: Boolean(chat.has_openai_key || chat.openai_key),
      model: chat.model ?? defaultChatState.model,
      topK: typeof chat.top_k === "number" ? chat.top_k : defaultChatState.topK,
      temperature:
        typeof chat.temperature === "number" ? chat.temperature : defaultChatState.temperature,
      searchMode: chat.search_mode ?? defaultChatState.searchMode,
      rerank: typeof chat.rerank === "boolean" ? chat.rerank : defaultChatState.rerank,
      multimodal:
        typeof chat.multimodal === "boolean" ? chat.multimodal : defaultChatState.multimodal,
      systemPrompt: chat.system_prompt ?? defaultChatState.systemPrompt,
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
      if (patch.multimodal !== undefined) mapped.multimodal = patch.multimodal;
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
  const { handleSend, stopStreaming } = useChatStreaming({
    appendMessages,
    collection,
    isStreaming,
    setStreaming,
    state,
    updateMessage,
  });

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

  return {
    collection,
    collections,
    disabled: !state.hasOpenAIKey || !collection,
    generateQuestionsPending: generateQuestions.isPending,
    handleClear,
    handleCollectionChange,
    handleEditUserMessage,
    handleGenerateQuestions,
    handleRegenerate,
    handleSend,
    isStreaming,
    loading: collectionsLoading || prefsQuery.isPending,
    messages,
    patchState,
    questions: questionsQuery.data?.questions ?? [],
    saving: updatePrefs.isPending,
    state,
    stopStreaming,
  };
};
