"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import type { PlatformStats, ReadinessReport } from "@/types/bigrag";

export const usePlatformStats = () =>
  useQuery({
    queryKey: ["platform", "stats"],
    queryFn: () => apiClient.get<PlatformStats>("v1/stats"),
    refetchInterval: 15_000,
  });

export const useReadiness = () =>
  useQuery({
    queryKey: ["platform", "readiness"],
    queryFn: () => apiClient.get<ReadinessReport>("health/ready"),
    refetchInterval: 30_000,
    retry: false,
  });

export const useEmbeddingModels = () =>
  useQuery({
    queryKey: ["platform", "embedding-models"],
    queryFn: () =>
      apiClient.get<{
        models: { provider: string; model: string; dimension: number; description: string }[];
      }>("v1/embeddings/models"),
  });
