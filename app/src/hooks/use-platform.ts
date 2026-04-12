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

/**
 * /health/ready returns 503 when any component is degraded (e.g. no
 * embedding API key). The body still carries per-service booleans, so
 * we parse both the 200 and the 503 cases and let the UI render the
 * real state.
 */
export const useReadiness = () =>
  useQuery({
    queryKey: ["platform", "readiness"],
    queryFn: async (): Promise<ReadinessReport> => {
      const res = await fetch("/api/bigrag/health/ready", {
        credentials: "include",
      });
      // Accept either 200 (ok) or 503 (degraded) — both carry a JSON
      // body with the same shape. Anything else is a real error.
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
    queryKey: ["platform", "embedding-models"],
    queryFn: () =>
      apiClient.get<{
        models: { provider: string; model: string; dimension: number; description: string }[];
      }>("v1/embeddings/models"),
  });
