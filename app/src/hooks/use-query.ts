import { useMutation } from "@tanstack/react-query";
import { useRef } from "react";
import { apiClient, SEARCH_TIMEOUT_MS } from "@/lib/api";
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

export const useRunQuery = (collection: string) => {
  const controllerRef = useRef<AbortController | null>(null);
  const mutation = useMutation({
    mutationKey: ["query", collection],
    mutationFn: async (body: QueryBody) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      return apiClient.post<QueryResponse>(
        `v1/collections/${encodeURIComponent(collection)}/query`,
        body,
        { signal: controller.signal, timeoutMs: SEARCH_TIMEOUT_MS },
      );
    },
    onSettled: () => {
      controllerRef.current = null;
    },
  });
  return {
    ...mutation,
    cancel: () => controllerRef.current?.abort(),
  };
};
