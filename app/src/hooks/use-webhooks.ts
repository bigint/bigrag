"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { Webhook } from "@/types/bigrag";

const KEY = queryKeys.webhooks();

export const useWebhooks = () =>
  useQuery({
    queryKey: KEY,
    queryFn: () => apiClient.get<{ webhooks: Webhook[] }>("v1/admin/webhooks"),
  });

export const useCreateWebhook = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      url: string;
      events: string[];
      collections?: string[] | null;
      description?: string;
    }) => apiClient.post<Webhook & { secret: string }>("v1/admin/webhooks", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
    onError: errorToast("Failed to create webhook"),
  });
};

export const useDeleteWebhook = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<{ status: string }>(`v1/admin/webhooks/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
      toast.success("Webhook removed");
    },
  });
};

export const useTestWebhook = () =>
  useMutation({
    mutationFn: (id: string) =>
      apiClient.post<{ status: string; status_code: number; error?: string }>(
        `v1/admin/webhooks/${id}/test`,
      ),
    onSuccess: (res) =>
      res.status === "delivered"
        ? toast.success(`Test delivered — HTTP ${res.status_code}`)
        : toast.error(`Test failed — ${res.error ?? "unknown"}`),
  });
