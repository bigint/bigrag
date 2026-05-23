import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { apiUrl } from "@/config/runtime";
import { useRealtimeSnapshotQuery } from "@/hooks/use-realtime-snapshot-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { PlatformStats, ReadinessReport } from "@/types/bigrag";

export const usePlatformStats = () => {
  const queryKey = useMemo(() => queryKeys.platform.stats(), []);
  return useRealtimeSnapshotQuery<PlatformStats>({
    queryKey,
    queryFn: () => apiClient.get<PlatformStats>("v1/stats"),
    topic: "admin.platform.stats",
  });
};

export const useReadiness = () => {
  const queryKey = useMemo(() => queryKeys.platform.readiness(), []);
  return useRealtimeSnapshotQuery<ReadinessReport>({
    queryKey,
    queryFn: async (): Promise<ReadinessReport> => {
      const res = await fetch(apiUrl("health/ready"), {
        credentials: "include",
      });

      if (res.status !== 200 && res.status !== 503) {
        throw new Error(`readiness probe: HTTP ${res.status}`);
      }
      return (await res.json()) as ReadinessReport;
    },
    topic: "admin.platform.readiness",
  });
};

export const useEmbeddingModels = () =>
  useQuery({
    queryKey: queryKeys.platform.embeddingModels(),
    queryFn: () =>
      apiClient.get<{
        models: { provider: string; model: string; dimension: number; description: string }[];
      }>("v1/embeddings/models"),
  });
