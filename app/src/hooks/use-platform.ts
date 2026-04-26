"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { PlatformStats, ReadinessReport } from "@/types/bigrag";

export const usePlatformStats = () =>
  useQuery({
    queryKey: queryKeys.platform.stats(),
    queryFn: () => apiClient.get<PlatformStats>("v1/stats"),
    refetchInterval: 15_000,
  });

export const useReadiness = () =>
  useQuery({
    queryKey: queryKeys.platform.readiness(),
    queryFn: async (): Promise<ReadinessReport> => {
      const res = await fetch("/api/bigrag/health/ready", {
        credentials: "include",
      });

      if (res.status !== 200 && res.status !== 503) {
        throw new Error(`readiness probe: HTTP ${res.status}`);
      }
      return (await res.json()) as ReadinessReport;
    },
    refetchInterval: 30_000,
    retry: false,
  });

export const useEmbeddingModels = () =>
  useQuery({
    queryKey: queryKeys.platform.embeddingModels(),
    queryFn: () =>
      apiClient.get<{
        models: { provider: string; model: string; dimension: number; description: string }[];
      }>("v1/embeddings/models"),
  });
