import type { ChatConversation, ChatCreateBody, ChatMessage, ChatSource } from "@bigrag/client";

export type ChatListResponse = {
  conversations: ChatConversation[];
  total: number;
};

export type ChatDetailResponse = {
  conversation: ChatConversation;
  messages: ChatMessage[];
};

export type { ChatConversation, ChatCreateBody, ChatMessage, ChatSource };
