"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { EmbeddingPreset } from "@/types/bigrag";

const KEY = ["embedding-presets"] as const;

export const useEmbeddingPresets = () =>
  useQuery({
    queryKey: KEY,
    queryFn: () =>
      apiClient.get<{ presets: EmbeddingPreset[]; total: number }>("v1/admin/embedding-presets"),
  });

export type EmbeddingPresetBody = {
  name: string;
  provider: "openai" | "cohere";
  model: string;
  api_key: string;
  base_url?: string | null;
  dimension: number;
};

export const useCreateEmbeddingPreset = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EmbeddingPresetBody) =>
      apiClient.post<EmbeddingPreset>("v1/admin/embedding-presets", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("Embedding preset created");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create preset"),
  });
};

export const useUpdateEmbeddingPreset = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Partial<EmbeddingPresetBody>) =>
      apiClient.patch<EmbeddingPreset>(`v1/admin/embedding-presets/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("Preset updated");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to update preset"),
  });
};

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
