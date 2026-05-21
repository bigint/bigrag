import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { toast } from "sonner";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type {
  VectorMigrationJob,
  VectorMigrationJobListResponse,
  VectorMigrationProvider,
} from "@/types/bigrag";

type VectorMigrationListOptions = {
  readonly collection?: string;
};

type StatusResponse = {
  readonly status: string;
  readonly message?: string;
};

type VectorStorageOverview = {
  fallback_provider: string;
  configured_providers: VectorMigrationProvider[];
  provider_health: Record<string, { configured: boolean; status: string; error: string | null }>;
  collections: {
    name: string;
    provider: VectorMigrationProvider;
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
    queryKey: queryKeys.vectorStorageOverview(),
    queryFn: () => apiClient.get<VectorStorageOverview>("v1/admin/vector-storage/overview"),
    staleTime: 15_000,
  });

export const useVectorMigrations = ({ collection }: VectorMigrationListOptions = {}) => {
  const queryKey = useMemo(() => queryKeys.vectorMigrations({ collection }), [collection]);
  const searchParams = collection ? { collection } : undefined;
  const path = collection
    ? `v1/admin/realtime/vector-migrations?collection=${encodeURIComponent(collection)}`
    : "v1/admin/realtime/vector-migrations";

  return useSseSnapshotQuery<VectorMigrationJobListResponse>({
    queryKey,
    queryFn: () =>
      apiClient.get<VectorMigrationJobListResponse>(
        "v1/admin/vector-storage/migrations",
        searchParams,
      ),
    path,
  });
};

export const useStartVectorMigration = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { collection: string; target_provider: VectorMigrationProvider }) =>
      apiClient.post<VectorMigrationJob>("v1/admin/vector-storage/migrations", body),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.vectorMigrations({}) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.vectorMigrations({ collection: job.collection_name }),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.collections.all() });
      queryClient.invalidateQueries({
        queryKey: queryKeys.collections.one({ name: job.collection_name }),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.vectorStorageOverview() });
      toast.success("Vector migration started");
    },
    onError: errorToast("Failed to start migration"),
  });
};

export const useDeleteVectorMigration = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (job: VectorMigrationJob) =>
      apiClient.delete<StatusResponse>(
        `v1/admin/vector-storage/migrations/${encodeURIComponent(job.id)}`,
      ),
    onSuccess: (response, job) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.vectorMigrations({}) });
      queryClient.invalidateQueries({
        queryKey: queryKeys.vectorMigrations({ collection: job.collection_name }),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.collections.all() });
      queryClient.invalidateQueries({
        queryKey: queryKeys.collections.one({ name: job.collection_name }),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.vectorStorageOverview() });
      toast.success(response.message ?? "Vector migration deleted");
    },
    onError: errorToast("Failed to delete migration"),
  });
};
