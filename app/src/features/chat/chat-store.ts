import { create } from "zustand";
import type { ChatMessage } from "@/features/chat/chat-messages";

export type ChatStoreState = {
  collection: string;
  conversationId: string | null;
  isStreaming: boolean;
  messages: ChatMessage[];
  appendMessages: (messages: ChatMessage[]) => void;
  hydrateConversationMessages: (conversationId: string, messages: ChatMessage[]) => void;
  replaceMessageId: (currentId: string, nextId: string) => void;
  selectCollection: (collection: string) => void;
  selectConversation: (conversationId: string) => void;
  selectFirstCollection: (collections: readonly { name: string }[]) => void;
  setConversationId: (conversationId: string | null) => void;
  setStreaming: (isStreaming: boolean) => void;
  startNewChat: () => void;
  updateMessage: (id: string, update: (message: ChatMessage) => ChatMessage) => void;
};

const initialState = {
  collection: "",
  conversationId: null,
  isStreaming: false,
  messages: [],
} satisfies Pick<ChatStoreState, "collection" | "conversationId" | "isStreaming" | "messages">;

export const useChatStore = create<ChatStoreState>((set) => ({
  ...initialState,
  appendMessages: (messages) =>
    set((state) => ({
      messages: [...state.messages, ...messages],
    })),
  hydrateConversationMessages: (conversationId, messages) =>
    set((state) => {
      if (state.conversationId !== conversationId || state.isStreaming) return state;
      return { messages };
    }),
  replaceMessageId: (currentId, nextId) =>
    set((state) => ({
      messages: state.messages.map((message) =>
        message.id === currentId ? { ...message, id: nextId } : message,
      ),
    })),
  selectCollection: (collection) =>
    set((state) => ({
      collection,
      conversationId: state.conversationId ? null : state.conversationId,
      messages: state.conversationId ? [] : state.messages,
    })),
  selectConversation: (conversationId) =>
    set({
      conversationId,
      isStreaming: false,
      messages: [],
    }),
  selectFirstCollection: (collections) =>
    set((state) => {
      const first = collections[0];
      if (state.collection || !first) return state;
      return { collection: first.name };
    }),
  setConversationId: (conversationId) => set({ conversationId }),
  setStreaming: (isStreaming) => set({ isStreaming }),
  startNewChat: () =>
    set({
      conversationId: null,
      isStreaming: false,
      messages: [],
    }),
  updateMessage: (id, update) =>
    set((state) => ({
      messages: state.messages.map((message) => (message.id === id ? update(message) : message)),
    })),
}));
