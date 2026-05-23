import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { toast } from "sonner";
import { useRealtimeSnapshotQuery } from "@/hooks/use-realtime-snapshot-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { BackupJob, BackupJobListResponse } from "@/types/bigrag";

export const useBackups = () => {
  const queryKey = useMemo(() => queryKeys.backups(), []);
  return useRealtimeSnapshotQuery<BackupJobListResponse>({
    queryKey,
    queryFn: () => apiClient.get<BackupJobListResponse>("v1/admin/backups"),
    topic: "admin.backups",
  });
};

export const useStartBackup = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { label?: string }) =>
      apiClient.post<BackupJob>("v1/admin/backups", { label: body.label ?? "" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.backups() });
      toast.success("Backup started");
    },
  });
};
