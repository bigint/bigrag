import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { ChatDetailResponse, ChatListResponse } from "@/types/bigrag";

export type ChatQuestionSuggestionsResponse = {
  collection: string;
  generated_at: string | null;
  model: string | null;
  questions: string[];
};

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

export const useChatQuestionSuggestions = (collection: string) =>
  useQuery({
    queryKey: queryKeys.chat.questions({ collection }),
    queryFn: () =>
      apiClient.get<ChatQuestionSuggestionsResponse>("v1/chat/question-suggestions", {
        collection,
      }),
    enabled: Boolean(collection),
  });

export const useGenerateChatQuestions = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { collection: string; model?: string; temperature?: number }) =>
      apiClient.post<ChatQuestionSuggestionsResponse>("v1/chat/question-suggestions", body),
    onSuccess: (response) => {
      queryClient.setQueryData(
        queryKeys.chat.questions({ collection: response.collection }),
        response,
      );
    },
    onError: errorToast("Failed to generate questions"),
  });
};
