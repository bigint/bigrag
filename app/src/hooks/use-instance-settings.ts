import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { InstanceSettingsResponse } from "@/types/bigrag";

type SettingsBody = { values: Record<string, unknown> };

export const useInstanceSettings = () =>
  useQuery({
    queryKey: queryKeys.instanceSettings(),
    queryFn: () => apiClient.get<InstanceSettingsResponse>("admin/settings"),
    retry: false,
  });

export const useUpdateInstanceSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SettingsBody) =>
      apiClient.put<InstanceSettingsResponse>("admin/settings", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.instanceSettings() });
      qc.invalidateQueries({ queryKey: queryKeys.platform.readiness() });
      toast.success("Settings saved");
    },
    onError: errorToast("Could not save settings"),
  });
};

export const useTestInstanceSettings = () =>
  useMutation({
    mutationFn: (body: SettingsBody) =>
      apiClient.post<{ status: string; checked: string[]; message: string }>(
        "admin/settings/test",
        body,
      ),
    onSuccess: (result) => {
      toast.success(result.message || "Settings validated");
    },
    onError: errorToast("Settings validation failed"),
  });

export const useResetInstanceSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (keys: string[]) =>
      apiClient.post<{ status: string; message: string }>("admin/settings/reset", { keys }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.instanceSettings() });
      toast.success("Settings reset");
    },
    onError: errorToast("Could not reset settings"),
  });
};
