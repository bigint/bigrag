import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { apiUrl } from "@/config/runtime";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { PlatformStats, ReadinessReport } from "@/types/bigrag";

const statusPollMs = 5_000;

export type OverviewStatus = {
  platform: PlatformStats;
  readiness: ReadinessReport;
};

export const useOverviewStatus = () =>
  useQuery({
    queryKey: queryKeys.platform.overviewStatus(),
    queryFn: () => apiClient.get<OverviewStatus>("v1/status/overview"),
    refetchInterval: statusPollMs,
  });

export const usePlatformStats = () => {
  const queryKey = useMemo(() => queryKeys.platform.stats(), []);
  return useQuery({
    queryKey,
    queryFn: () => apiClient.get<PlatformStats>("v1/stats"),
    refetchInterval: statusPollMs,
  });
};

export const useReadiness = () => {
  const queryKey = useMemo(() => queryKeys.platform.readiness(), []);
  return useQuery({
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
    refetchInterval: statusPollMs,
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
