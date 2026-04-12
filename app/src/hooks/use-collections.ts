"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { Collection, CollectionStats } from "@/types/bigrag";

type ListResponse = { collections: Collection[]; total: number };

export const collectionsKey = ["collections"] as const;

export const useCollections = () =>
  useQuery({
    queryKey: collectionsKey,
    queryFn: () => apiClient.get<ListResponse>("v1/collections", { limit: 200 }),
    staleTime: 15_000,
  });

export const useCollection = (name: string) =>
  useQuery({
    queryKey: [...collectionsKey, name],
    queryFn: () => apiClient.get<Collection>(`v1/collections/${encodeURIComponent(name)}`),
    enabled: !!name,
  });

export const useCollectionStats = (name: string) =>
  useQuery({
    queryKey: [...collectionsKey, name, "stats"],
    queryFn: () =>
      apiClient.get<CollectionStats>(`v1/collections/${encodeURIComponent(name)}/stats`),
    enabled: !!name,
    refetchInterval: 10_000,
  });

export type CreateCollectionBody = {
  name: string;
  description?: string;
  embedding_preset_id?: string | null;
  embedding_provider?: "openai" | "cohere";
  embedding_model?: string;
  embedding_api_key?: string;
  embedding_base_url?: string | null;
  dimension?: number;
  chunk_size?: number;
  chunk_overlap?: number;
  reranking_enabled?: boolean;
  reranking_model?: string;
  reranking_api_key?: string | null;
  default_top_k?: number;
  default_search_mode?: "semantic" | "keyword" | "hybrid";
  metadata?: Record<string, unknown>;
};

export const useCreateCollection = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateCollectionBody) => apiClient.post<Collection>("v1/collections", body),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: collectionsKey });
      toast.success(`Collection "${c.name}" created`);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to create"),
  });
};

export const useUpdateCollection = (name: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<CreateCollectionBody>) =>
      apiClient.put<Collection>(`v1/collections/${encodeURIComponent(name)}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectionsKey });
      toast.success("Collection updated");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to update"),
  });
};

export const useDeleteCollection = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      apiClient.delete<{ status: string }>(`v1/collections/${encodeURIComponent(name)}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectionsKey });
      toast.success("Collection deleted");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to delete"),
  });
};

export const useTruncateCollection = (name: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<{ status: string }>(`v1/collections/${encodeURIComponent(name)}/truncate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: collectionsKey });
      toast.success("All documents removed from collection");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to truncate"),
  });
};
