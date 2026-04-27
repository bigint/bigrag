"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

type PlaygroundPrefs = {
  openai_key?: string;
  model?: string;
  top_k?: number;
  temperature?: number;
  system_prompt?: string;
};

type Preferences = {
  playground?: PlaygroundPrefs;
};

const KEY = queryKeys.preferences();

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
      const previous = qc.getQueryData<{ data: Preferences }>(KEY);
      qc.setQueryData<{ data: Preferences }>(KEY, (old) => ({
        data: {
          ...(old?.data ?? {}),
          ...patch,
          playground: {
            ...(old?.data?.playground ?? {}),
            ...(patch.playground ?? {}),
          },
        },
      }));
      return { previous };
    },
    onError: (_err, _patch, ctx) => {
      if (ctx?.previous) qc.setQueryData(KEY, ctx.previous);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: KEY }),
  });
};
