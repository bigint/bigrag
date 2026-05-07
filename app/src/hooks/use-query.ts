import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import type { QueryResult } from "@/types/bigrag";

type QueryBody = {
  query: string;
  top_k?: number;
  min_score?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
  rerank?: boolean;
  filters?: Record<string, unknown>;
};

type QueryResponse = {
  results: QueryResult[];
  query: string;
  collection: string;
  total: number;
};

export const useRunQuery = (collection: string) =>
  useMutation({
    mutationFn: (body: QueryBody) =>
      apiClient.post<QueryResponse>(`v1/collections/${encodeURIComponent(collection)}/query`, body),
  });
