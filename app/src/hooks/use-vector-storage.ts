import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export type VectorStorageOverview = {
  fallback_provider: string;
  configured_providers: string[];
  provider_health: Record<string, { configured: boolean; status: string; error: string | null }>;
  collections: {
    name: string;
    provider: "qdrant" | "turbopuffer";
    documents: number;
    chunks: number;
    bytes: number;
  }[];
  totals: {
    collections: number;
    documents: number;
    chunks: number;
    bytes: number;
  };
};

export const useVectorStorageOverview = () =>
  useQuery({
    queryKey: queryKeys.vectorStorage(),
    queryFn: () => apiClient.get<VectorStorageOverview>("v1/admin/vector-storage/overview"),
  });
