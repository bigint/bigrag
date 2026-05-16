import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  buildQuestionSuggestions,
  questionChunkOffset,
  readyQuestionDocuments,
} from "@/features/chat/question-suggestions";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { ChatDetailResponse, ChatListResponse, Chunk, Document } from "@/types/bigrag";

export const useChatConversations = () =>
  useQuery({
    queryKey: queryKeys.chat.list(),
    queryFn: () => apiClient.get<ChatListResponse>("v1/chat", { limit: 100 }),
    staleTime: 10_000,
  });

export const useChatConversation = (id: string | null) =>
  useQuery({
    queryKey: queryKeys.chat.detail({ id }),
    queryFn: () => apiClient.get<ChatDetailResponse>(`v1/chat/${id}`),
    enabled: Boolean(id),
  });

export const useDeleteChatConversation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<{ status: "deleted" }>(`v1/chat/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.chat.list() });
      toast.success("Conversation deleted");
    },
    onError: errorToast("Failed to delete conversation"),
  });
};

export const useGenerateChatQuestions = () =>
  useMutation({
    mutationFn: async ({ collection }: { collection: string }) => {
      const encodedCollection = encodeURIComponent(collection);
      const response = await apiClient.get<{ documents: Document[]; total: number }>(
        `v1/collections/${encodedCollection}/documents`,
        { limit: 1000, status: "ready" },
      );
      const documents = readyQuestionDocuments(response.documents);
      const chunkResults = await Promise.all(
        documents.map((document) =>
          apiClient
            .get<{ chunks: Chunk[]; total: number }>(
              `v1/collections/${encodedCollection}/documents/${encodeURIComponent(document.id)}/chunks`,
              { limit: 24, offset: questionChunkOffset(document) },
            )
            .catch(() => ({ chunks: [], total: 0 })),
        ),
      );
      return buildQuestionSuggestions({
        chunks: chunkResults.flatMap((result) => result.chunks),
        collection,
        documents: response.documents,
      });
    },
    onError: errorToast("Failed to generate questions"),
  });
