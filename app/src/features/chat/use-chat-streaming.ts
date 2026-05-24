import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { toast } from "sonner";
import type { ChatState } from "@/features/chat/chat-input";
import type { ChatMessage } from "@/features/chat/chat-messages";
import { createChatMessageId } from "@/features/chat/chat-page-defaults";
import { normalizeTimings, timingsFromRetrieval } from "@/features/chat/chat-page-timings";
import type { useChatStore } from "@/features/chat/chat-store";
import { streamChat } from "@/lib/chat-stream";
import { queryKeys } from "@/lib/query-keys";

type ChatStoreState = ReturnType<typeof useChatStore.getState>;

type ChatStreamingOptions = {
  appendMessages: ChatStoreState["appendMessages"];
  collection: string;
  isStreaming: boolean;
  setStreaming: ChatStoreState["setStreaming"];
  state: ChatState;
  updateMessage: ChatStoreState["updateMessage"];
};

export const useChatStreaming = ({
  appendMessages,
  collection,
  isStreaming,
  setStreaming,
  state,
  updateMessage,
}: ChatStreamingOptions) => {
  const queryClient = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      abortRef.current?.abort();
      abortRef.current = null;
      setStreaming(false);
    },
    [setStreaming],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, [setStreaming]);

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

      const userId = createChatMessageId();
      const assistantId = createChatMessageId();
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
            multimodal: state.multimodal,
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
      state.multimodal,
      state.rerank,
      state.searchMode,
      state.systemPrompt,
      state.temperature,
      state.topK,
      updateMessage,
    ],
  );

  return { handleSend, stopStreaming };
};
