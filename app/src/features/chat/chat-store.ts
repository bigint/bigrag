import { create } from "zustand";
import type { ChatMessage } from "@/features/chat/chat-messages";

export type ChatStoreState = {
  collection: string;
  isStreaming: boolean;
  messages: ChatMessage[];
  appendMessages: (messages: ChatMessage[]) => void;
  clearMessages: () => void;
  selectCollection: (collection: string) => void;
  selectFirstCollection: (collections: readonly { name: string }[]) => void;
  setStreaming: (isStreaming: boolean) => void;
  setMessages: (messages: ChatMessage[]) => void;
  updateMessage: (id: string, update: (message: ChatMessage) => ChatMessage) => void;
};

const initialState = {
  collection: "",
  isStreaming: false,
  messages: [],
} satisfies Pick<ChatStoreState, "collection" | "isStreaming" | "messages">;

if (typeof window !== "undefined") {
  try {
    window.localStorage.removeItem("bigrag-chat");
  } catch {}
}

export const useChatStore = create<ChatStoreState>()((set) => ({
  ...initialState,
  appendMessages: (messages) =>
    set((state) => ({
      messages: [...state.messages, ...messages],
    })),
  clearMessages: () =>
    set({
      isStreaming: false,
      messages: [],
    }),
  selectCollection: (collection) =>
    set((state) => ({
      collection,
      messages: state.collection === collection ? state.messages : [],
      isStreaming: false,
    })),
  selectFirstCollection: (collections) =>
    set((state) => {
      const first = collections[0];
      if (state.collection || !first) return state;
      return { collection: first.name };
    }),
  setMessages: (messages) => set({ messages }),
  setStreaming: (isStreaming) => set({ isStreaming }),
  updateMessage: (id, update) =>
    set((state) => ({
      messages: state.messages.map((message) => (message.id === id ? update(message) : message)),
    })),
}));
