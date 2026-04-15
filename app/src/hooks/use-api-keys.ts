"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { ApiKey, CreatedApiKey } from "@/types/bigrag";

const KEY = ["api-keys"] as const;

export const useApiKeys = () =>
  useQuery({
    queryKey: KEY,
    queryFn: () => apiClient.get<{ keys: ApiKey[]; total: number }>("v1/admin/api-keys"),
  });

export const useCreateApiKey = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; expires_at?: string | null; collection?: string | null }) =>
      apiClient.post<CreatedApiKey>("v1/admin/api-keys", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create"),
  });
};

export const useUpdateApiKey = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: string;
      name?: string;
      active?: boolean;
      collection?: string | null;
    }) => apiClient.patch<ApiKey>(`v1/admin/api-keys/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
};

export const useDeleteApiKey = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<{ status: string }>(`v1/admin/api-keys/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("Key revoked");
    },
  });
};
