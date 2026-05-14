import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

type ChatPrefs = {
  openai_key?: string;
  has_openai_key?: boolean;
  model?: string;
  top_k?: number;
  temperature?: number;
  system_prompt?: string;
  search_mode?: "semantic" | "keyword" | "hybrid";
  rerank?: boolean;
};

type Preferences = {
  chat?: ChatPrefs;
};

const KEY = queryKeys.preferences();
let preferencesMutationVersion = 0;

export const usePreferences = () =>
  useQuery({
    queryKey: KEY,
    queryFn: () => apiClient.get<{ data: Preferences }>("v1/auth/preferences"),
    staleTime: 30_000,
  });

export const useUpdatePreferences = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Preferences) =>
      apiClient.put<{ data: Preferences }>("v1/auth/preferences", { data: patch }),
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: KEY });
      const version = ++preferencesMutationVersion;
      const previous = qc.getQueryData<{ data: Preferences }>(KEY);
      const publicPatch = (prefs?: ChatPrefs) => {
        if (prefs?.openai_key === undefined) return prefs;
        const { openai_key: _openaiKey, ...rest } = prefs;
        return rest;
      };
      qc.setQueryData<{ data: Preferences }>(KEY, (old) => ({
        data: {
          ...(old?.data ?? {}),
          ...patch,
          chat: {
            ...(old?.data?.chat ?? {}),
            ...(publicPatch(patch.chat) ?? {}),
          },
        },
      }));
      return { previous, version };
    },
    onError: (_err, _patch, ctx) => {
      if (ctx?.previous && ctx.version === preferencesMutationVersion) {
        qc.setQueryData(KEY, ctx.previous);
      }
    },
    onSuccess: (data, _patch, ctx) => {
      if (ctx?.version === preferencesMutationVersion) {
        qc.setQueryData(KEY, data);
      }
    },
    onSettled: (_data, _err, _patch, ctx) => {
      if (ctx?.version === preferencesMutationVersion) {
        qc.invalidateQueries({ queryKey: KEY });
      }
    },
  });
};
