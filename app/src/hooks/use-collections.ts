import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { toast } from "sonner";
import { useRealtimeSnapshotQuery } from "@/hooks/use-realtime-snapshot-query";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { Collection, CollectionStats } from "@/types/bigrag";

type ListResponse = {
  collections: Collection[];
  total: number | null;
  next_cursor: string | null;
};

const invalidateCollectionData = (queryClient: QueryClient, name: string) => {
  queryClient.invalidateQueries({ queryKey: queryKeys.collections.all() });
  queryClient.invalidateQueries({ queryKey: queryKeys.collections.one({ name }) });
  queryClient.invalidateQueries({ queryKey: queryKeys.collections.stats({ name }) });
  queryClient.invalidateQueries({ queryKey: queryKeys.documents.lists() });
};

export const useCollections = () =>
  useQuery({
    queryKey: queryKeys.collections.all(),
    queryFn: () => apiClient.get<ListResponse>("v1/collections", { limit: 200 }),
    staleTime: 15_000,
  });

export const useCollection = (name: string) =>
  useQuery({
    queryKey: queryKeys.collections.one({ name }),
    queryFn: () => apiClient.get<Collection>(`v1/collections/${encodeURIComponent(name)}`),
    enabled: !!name,
    staleTime: 15_000,
  });

export const useCollectionStats = (name: string) => {
  const queryKey = useMemo(() => queryKeys.collections.stats({ name }), [name]);
  return useRealtimeSnapshotQuery<CollectionStats>({
    queryKey,
    queryFn: () =>
      apiClient.get<CollectionStats>(`v1/collections/${encodeURIComponent(name)}/stats`),
    enabled: !!name,
    topic: "admin.collections.stats",
    params: { collection: name },
  });
};

type CreateCollectionBody = {
  name: string;
  description?: string;
  embedding_preset_id?: string | null;
  embedding_provider?: "openai" | "openai_compatible" | "cohere" | "voyage";
  embedding_model?: string;
  embedding_api_key?: string | null;
  embedding_base_url?: string | null;
  dimension?: number;
  chunk_size?: number;
  chunk_overlap?: number;
  reranking_enabled?: boolean;
  reranking_model?: string;
  reranking_api_key?: string | null;
  multimodal_enabled?: boolean;
  multimodal_enrichment_enabled?: boolean;
  default_top_k?: number;
  default_search_mode?: "semantic" | "keyword" | "hybrid";
  metadata?: Record<string, unknown>;
};

export const useCreateCollection = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateCollectionBody) => apiClient.post<Collection>("v1/collections", body),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: queryKeys.collections.all() });
      toast.success(`Collection "${c.name}" created`);
    },
    onError: errorToast("Failed to create"),
  });
};

export const useUpdateCollection = (name: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<CreateCollectionBody>) =>
      apiClient.put<Collection>(`v1/collections/${encodeURIComponent(name)}`, body),
    onSuccess: () => {
      invalidateCollectionData(qc, name);
      toast.success("Collection updated");
    },
    onError: errorToast("Failed to update"),
  });
};

export const useDeleteCollection = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      apiClient.delete<{ status: string }>(`v1/collections/${encodeURIComponent(name)}`),
    onSuccess: (_res, name) => {
      invalidateCollectionData(qc, name);
      toast.success("Collection deleted");
    },
    onError: errorToast("Failed to delete"),
  });
};

export const useTruncateCollection = (name: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<{ status: string }>(`v1/collections/${encodeURIComponent(name)}/truncate`),
    onSuccess: () => {
      invalidateCollectionData(qc, name);
      toast.success("All documents removed from collection");
    },
    onError: errorToast("Failed to truncate"),
  });
};
