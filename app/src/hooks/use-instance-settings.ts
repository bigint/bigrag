import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { InstanceSettingsResponse } from "@/types/bigrag";

type SettingsBody = { values: Record<string, unknown> };
type InstanceSettingsOptions = { readonly enabled?: boolean };

export const useInstanceSettings = ({ enabled = true }: InstanceSettingsOptions = {}) =>
  useQuery({
    queryKey: queryKeys.instanceSettings(),
    queryFn: () => apiClient.get<InstanceSettingsResponse>("v1/admin/settings"),
    enabled,
    retry: false,
  });

export const useUpdateInstanceSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SettingsBody) =>
      apiClient.put<InstanceSettingsResponse>("v1/admin/settings", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.instanceSettings() });
      qc.invalidateQueries({ queryKey: queryKeys.platform.readiness() });
      toast.success("Settings saved");
    },
    onError: errorToast("Could not validate or save settings"),
  });
};

export const usePurgeEmbeddingCache = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<{ status: string; message: string }>(
        "v1/admin/settings/embedding-cache/purge",
      ),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: queryKeys.instanceSettings() });
      toast.success(result.message || "Embedding cache purged");
    },
    onError: errorToast("Could not purge embedding cache"),
  });
};
