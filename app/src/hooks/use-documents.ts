"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import type { Chunk, Document } from "@/types/bigrag";

type DocListResponse = { documents: Document[]; total: number };

export const docsKey = (collection: string) => ["documents", collection] as const;

export const useDocuments = (collection: string, status?: string) =>
  useQuery({
    queryKey: [...docsKey(collection), { status: status ?? "all" }],
    queryFn: () =>
      apiClient.get<DocListResponse>(`v1/collections/${encodeURIComponent(collection)}/documents`, {
        limit: 100,
        ...(status ? { status } : {}),
      }),
    enabled: !!collection,
    refetchInterval: 5_000,
  });

export const useDocument = (collection: string, docId: string) =>
  useQuery({
    queryKey: [...docsKey(collection), docId],
    queryFn: () =>
      apiClient.get<Document>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}`,
      ),
    enabled: !!collection && !!docId,
    refetchInterval: (q) => {
      const status = (q.state.data as Document | undefined)?.status;
      return status === "pending" || status === "processing" ? 2_000 : false;
    },
  });

export const useChunks = (collection: string, docId: string) =>
  useQuery({
    queryKey: [...docsKey(collection), docId, "chunks"],
    queryFn: () =>
      apiClient.get<{ chunks: Chunk[]; total: number }>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}/chunks`,
        { limit: 200 },
      ),
    enabled: !!collection && !!docId,
  });

export const useUploadDocuments = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (files: File[]) => {
      const form = new FormData();
      for (const f of files) form.append("files", f);
      return apiClient.postForm<{ documents: Document[]; total: number }>(
        `v1/collections/${encodeURIComponent(collection)}/documents/batch/upload`,
        form,
      );
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: docsKey(collection) });
      toast.success(`Queued ${res.total} document${res.total === 1 ? "" : "s"} for ingestion`);
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Upload failed"),
  });
};

export const useDeleteDocument = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) =>
      apiClient.delete<{ status: string }>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: docsKey(collection) });
      toast.success("Document deleted");
    },
  });
};

export const useReprocessDocument = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) =>
      apiClient.post<{ status: string }>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}/reprocess`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: docsKey(collection) });
      toast.success("Reprocessing queued");
    },
  });
};
