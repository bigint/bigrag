import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient, SEARCH_TIMEOUT_MS } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { EmbeddingPreset } from "@/types/bigrag";

const KEY = queryKeys.embeddingPresets();
type EmbeddingPresetsOptions = { readonly enabled?: boolean };

export const useEmbeddingPresets = ({ enabled = true }: EmbeddingPresetsOptions = {}) =>
  useQuery({
    queryKey: KEY,
    queryFn: () =>
      apiClient.get<{ presets: EmbeddingPreset[]; total: number }>("v1/admin/embedding-presets"),
    enabled,
  });

export type EmbeddingPresetBody = {
  name: string;
  provider: "openai" | "openai_compatible" | "cohere" | "voyage";
  model: string;
  api_key: string;
  base_url?: string | null;
  dimension: number;
};

export const useCreateEmbeddingPreset = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EmbeddingPresetBody) =>
      apiClient.post<EmbeddingPreset>("v1/admin/embedding-presets", body, {
        timeoutMs: SEARCH_TIMEOUT_MS,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("Embedding preset created");
    },
    onError: errorToast("Failed to create preset"),
  });
};

export const useUpdateEmbeddingPreset = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Partial<EmbeddingPresetBody>) =>
      apiClient.patch<EmbeddingPreset>(`v1/admin/embedding-presets/${id}`, body, {
        timeoutMs: SEARCH_TIMEOUT_MS,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("Preset updated");
    },
    onError: errorToast("Failed to update preset"),
  });
};

export const useTestEmbeddingPreset = () =>
  useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id?: string;
      provider: EmbeddingPresetBody["provider"];
      model: string;
      api_key?: string | null;
      base_url?: string | null;
    }) =>
      id
        ? apiClient.post<{ status: string; message: string }>(
            `v1/admin/embedding-presets/${id}/test`,
            undefined,
            { timeoutMs: SEARCH_TIMEOUT_MS },
          )
        : apiClient.post<{ status: string; message: string }>(
            "v1/admin/embedding-presets/test",
            body,
            { timeoutMs: SEARCH_TIMEOUT_MS },
          ),
    onSuccess: () => toast.success("Embedding provider connected"),
    onError: errorToast("Connection test failed"),
  });

export const useDeleteEmbeddingPreset = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete<{ status: string }>(`v1/admin/embedding-presets/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("Preset deleted");
    },
  });
};
