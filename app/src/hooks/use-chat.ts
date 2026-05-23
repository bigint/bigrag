import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";

type ChatQuestionSuggestionsResponse = {
  collection: string;
  generated_at: string | null;
  model: string | null;
  questions: string[];
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
