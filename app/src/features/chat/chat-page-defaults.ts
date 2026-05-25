import type { ChatState } from "@/features/chat/chat-input";

export const createChatMessageId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

export const defaultSystemPrompt =
  "You are bigRAG's grounded chat assistant. Answer using only the retrieved context. " +
  "If the context does not contain the answer, say you do not know. Cite every factual " +
  "claim with bracketed source numbers like [1] or [2].";

export const defaultChatState: ChatState = {
  hasOpenAIKey: false,
  model: "gpt-4.1",
  topK: 5,
  temperature: 0.2,
  searchMode: "semantic",
  rerank: false,
  multimodal: false,
  systemPrompt: defaultSystemPrompt,
};
