import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { toast } from "sonner";
import { useRealtimeSnapshotQuery } from "@/hooks/use-realtime-snapshot-query";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { Chunk, Document, UploadSession, UploadSessionFileResponse } from "@/types/bigrag";

type DocListResponse = {
  documents: Document[];
  total: number | null;
  next_cursor: string | null;
};
export type DocumentListSort =
  | "created_at"
  | "updated_at"
  | "filename"
  | "file_size"
  | "chunk_count"
  | "status";
export type DocumentListOrder = "asc" | "desc";
export type DocumentListFilters = {
  q?: string;
  status?: string;
  sort?: DocumentListSort;
  order?: DocumentListOrder;
  limit?: number;
  offset?: number;
};

const uploadSessionFileName = (file: File) =>
  (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;

const uploadSessionClientId = (file: File, index: number) =>
  `${index}:${uploadSessionFileName(file)}:${file.size}:${file.lastModified}`;

const documentListLimit = 1000;
const chunkListLimit = 1000;
const uploadConcurrency = 4;

export const useDocuments = (collection: string, filters: DocumentListFilters = {}) => {
  const limit = filters.limit ?? documentListLimit;
  const offset = filters.offset ?? 0;
  const q = filters.q?.trim() || undefined;
  const status = filters.status || undefined;
  const sort = filters.sort ?? "created_at";
  const order = filters.order ?? "desc";
  const queryKey = useMemo(
    () => queryKeys.documents.list({ collection, q, status, sort, order, limit, offset }),
    [collection, limit, offset, order, q, sort, status],
  );
  const realtimeParams = useMemo(
    () => ({ collection, limit, offset, order, q, sort, status }),
    [collection, limit, offset, order, q, sort, status],
  );
  return useRealtimeSnapshotQuery<DocListResponse>({
    queryKey,
    queryFn: ({ signal }) =>
      apiClient.get<DocListResponse>(`v1/collections/${encodeURIComponent(collection)}/documents`, {
        searchParams: {
          limit,
          offset,
          order,
          q,
          sort,
          status,
          include_total: true,
        },
        signal,
      }),
    enabled: !!collection,
    topic: "admin.collections.documents",
    params: realtimeParams,
  });
};

export const useDocument = (collection: string, docId: string) => {
  const queryKey = useMemo(
    () => queryKeys.documents.one({ collection, id: docId }),
    [collection, docId],
  );
  return useRealtimeSnapshotQuery<Document>({
    queryKey,
    queryFn: ({ signal }) =>
      apiClient.get<Document>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}`,
        { signal },
      ),
    enabled: !!collection && !!docId,
    topic: "admin.collections.documents.detail",
    params: { collection, document_id: docId },
    closeWhen: (doc) => doc.status === "ready" || doc.status === "failed",
  });
};

export const useChunks = (collection: string, docId: string) =>
  useQuery({
    queryKey: queryKeys.documents.chunks({ collection, id: docId }),
    queryFn: ({ signal }) =>
      apiClient.get<{ chunks: Chunk[]; total: number }>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}/chunks`,
        { searchParams: { limit: chunkListLimit }, signal },
      ),
    enabled: !!collection && !!docId,
  });

export const useUploadSession = (collection: string, sessionId: string | null) => {
  const queryKey = useMemo(
    () => queryKeys.documents.uploadSession({ collection, id: sessionId }),
    [collection, sessionId],
  );
  const enabled = Boolean(collection && sessionId);
  return useRealtimeSnapshotQuery<UploadSession>({
    queryKey,
    queryFn: ({ signal }) =>
      apiClient.get<UploadSession>(
        `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${sessionId}`,
        { signal },
      ),
    enabled,
    topic: "admin.collections.upload_session",
    params: { collection, session_id: sessionId ?? "" },
    pollIntervalMs: 2_000,
    closeWhen: (session) =>
      session.status === "complete" || session.status === "failed" || session.status === "canceled",
  });
};

export const useUploadSessionDocuments = (
  collection: string,
  options?: { onSessionStart?: (session: UploadSession) => void },
) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (files: File[]) => {
      const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
      const session = await apiClient.post<UploadSession>(
        `v1/collections/${encodeURIComponent(collection)}/upload-sessions`,
        {
          total_files: files.length,
          total_bytes: totalBytes,
          metadata: {},
        },
      );
      options?.onSessionStart?.(session);
      const errors: { filename: string; error: string }[] = [];
      let next = 0;
      const uploadNext = async () => {
        while (next < files.length) {
          const index = next;
          next += 1;
          const file = files[index];
          const form = new FormData();
          form.append("client_item_id", uploadSessionClientId(file, index));
          form.append("file", file, uploadSessionFileName(file));
          try {
            await apiClient.postForm<UploadSessionFileResponse>(
              `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${session.id}/files`,
              form,
            );
          } catch (err) {
            errors.push({
              filename: uploadSessionFileName(file),
              error: err instanceof Error ? err.message : "Upload failed",
            });
          }
        }
      };
      const workers = Array.from({ length: Math.min(uploadConcurrency, files.length) }, uploadNext);
      await Promise.all(workers);
      const sessionPath = `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${session.id}`;
      const finalSession =
        errors.length < files.length
          ? await apiClient.post<UploadSession>(`${sessionPath}/complete`)
          : await apiClient.get<UploadSession>(sessionPath);
      return { errors, session: finalSession };
    },
    onSuccess: ({ errors, session }) => {
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      qc.invalidateQueries({
        queryKey: queryKeys.documents.uploadSession({ collection, id: session.id }),
      });
      if (errors.length) {
        toast.warning(`${errors.length} file${errors.length === 1 ? "" : "s"} need retry`);
      } else {
        toast.success(
          `Queued ${session.uploaded_files} file${session.uploaded_files === 1 ? "" : "s"}`,
        );
      }
    },
    onError: errorToast("Upload session failed"),
  });
};

export const useCancelUploadSession = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiClient.post<{ status: string; message: string }>(
        `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${sessionId}/cancel`,
      ),
    onSuccess: (_res, sessionId) => {
      qc.invalidateQueries({
        queryKey: queryKeys.documents.uploadSession({ collection, id: sessionId }),
      });
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      toast.success("Upload session canceled");
    },
    onError: errorToast("Cancel failed"),
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
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      toast.success("Document deleted");
    },
  });
};

export const useBatchDeleteDocuments = (collection: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (documentIds: string[]) =>
      apiClient.post<{
        status: string;
        deleted: number;
        errors: { document_id: string; error: string }[];
      }>(`v1/collections/${encodeURIComponent(collection)}/documents/batch/delete`, {
        document_ids: documentIds,
      }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: queryKeys.documents.lists() });
      const failed = res.errors.length;
      if (failed) {
        toast.warning(`${res.deleted} deleted, ${failed} failed`);
      } else {
        toast.success(`${res.deleted} document${res.deleted === 1 ? "" : "s"} deleted`);
      }
    },
    onError: errorToast("Bulk delete failed"),
  });
};
