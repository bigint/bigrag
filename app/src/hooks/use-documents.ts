import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { toast } from "sonner";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { Chunk, Document, UploadSession, UploadSessionFileResponse } from "@/types/bigrag";

type DocListResponse = { documents: Document[]; total: number };

const uploadSessionFileName = (file: File) =>
  (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;

const uploadSessionClientId = (file: File, index: number) =>
  `${index}:${uploadSessionFileName(file)}:${file.size}:${file.lastModified}`;

const documentListLimit = 1000;
const chunkListLimit = 1000;
const uploadConcurrency = 4;

export const useDocuments = (collection: string, status?: string) => {
  const queryKey = useMemo(
    () => queryKeys.documents.list({ collection, status }),
    [collection, status],
  );
  const path = useMemo(() => {
    const params = new URLSearchParams({ limit: String(documentListLimit) });
    if (status) params.set("status", status);
    return `v1/admin/realtime/collections/${encodeURIComponent(collection)}/documents?${params}`;
  }, [collection, status]);
  return useSseSnapshotQuery<DocListResponse>({
    queryKey,
    queryFn: () =>
      apiClient.get<DocListResponse>(`v1/collections/${encodeURIComponent(collection)}/documents`, {
        limit: documentListLimit,
        ...(status ? { status } : {}),
      }),
    enabled: !!collection,
    path,
  });
};

export const useDocument = (collection: string, docId: string) => {
  const queryKey = useMemo(
    () => queryKeys.documents.one({ collection, id: docId }),
    [collection, docId],
  );
  return useSseSnapshotQuery<Document>({
    queryKey,
    queryFn: () =>
      apiClient.get<Document>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}`,
      ),
    enabled: !!collection && !!docId,
    path: `v1/admin/realtime/collections/${encodeURIComponent(collection)}/documents/${docId}`,
    closeWhen: (doc) => doc.status === "ready" || doc.status === "failed",
  });
};

export const useChunks = (collection: string, docId: string) =>
  useQuery({
    queryKey: queryKeys.documents.chunks({ collection, id: docId }),
    queryFn: () =>
      apiClient.get<{ chunks: Chunk[]; total: number }>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}/chunks`,
        { limit: chunkListLimit },
      ),
    enabled: !!collection && !!docId,
  });

export const useUploadSession = (collection: string, sessionId: string | null) => {
  const queryKey = useMemo(
    () => queryKeys.documents.uploadSession({ collection, id: sessionId }),
    [collection, sessionId],
  );
  const enabled = Boolean(collection && sessionId);
  return useSseSnapshotQuery<UploadSession>({
    queryKey,
    queryFn: () =>
      apiClient.get<UploadSession>(
        `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${sessionId}`,
      ),
    enabled,
    path: `v1/admin/realtime/collections/${encodeURIComponent(collection)}/upload-sessions/${sessionId}`,
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
      const finalSession = errors.length
        ? await apiClient.get<UploadSession>(sessionPath)
        : await apiClient.post<UploadSession>(`${sessionPath}/complete`);
      return { errors, session: finalSession };
    },
    onSuccess: ({ errors, session }) => {
      qc.invalidateQueries({ queryKey: queryKeys.documents.list({ collection }) });
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
      qc.invalidateQueries({ queryKey: queryKeys.documents.list({ collection }) });
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
      qc.invalidateQueries({ queryKey: queryKeys.documents.list({ collection }) });
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
    onSuccess: (_res, docId) => {
      qc.invalidateQueries({ queryKey: queryKeys.documents.list({ collection }) });
      qc.invalidateQueries({ queryKey: queryKeys.documents.one({ collection, id: docId }) });
      toast.success("Reprocessing queued");
    },
  });
};
