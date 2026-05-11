import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";
import { useSseSnapshotQuery } from "@/hooks/use-sse-snapshot-query";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type {
  Chunk,
  Document,
  DocumentProgress,
  DocumentStatus,
  UploadSession,
  UploadSessionFileResponse,
} from "@/types/rag-computer";

type DocListResponse = { documents: Document[]; total: number };

type BatchStatusItem = {
  id: string;
  status: DocumentStatus;
  error_message: string | null;
  chunk_count: number;
  progress: DocumentProgress | null;
};

type BatchStatusResponse = { documents: BatchStatusItem[]; total: number };

export type BatchDocumentProgress = DocumentProgress & {
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  document_status: DocumentStatus;
  error_message: string | null;
  receivedAt: number;
};

const fallbackProgress = (collection: string, doc: Document): DocumentProgress => {
  if (doc.status === "ready") {
    return {
      document_id: doc.id,
      collection_name: collection,
      step: "complete",
      status: "complete",
      message: `Ready - ${doc.chunk_count} chunks`,
      progress: 1,
      detail: { chunks: doc.chunk_count },
    };
  }
  if (doc.status === "failed") {
    return {
      document_id: doc.id,
      collection_name: collection,
      step: "failed",
      status: "failed",
      message: doc.error_message ?? "Ingestion failed",
      progress: 0,
      detail: {},
    };
  }
  if (doc.status === "processing") {
    return {
      document_id: doc.id,
      collection_name: collection,
      step: "processing",
      status: "processing",
      message: "Processing document",
      progress: 0.05,
      detail: {},
    };
  }
  return {
    document_id: doc.id,
    collection_name: collection,
    step: "queued",
    status: "pending",
    message: "Queued for ingestion",
    progress: 0,
    detail: {},
  };
};

const progressFromDocument = (
  collection: string,
  doc: Document,
  receivedAt = 0,
): BatchDocumentProgress => {
  const progress = doc.progress ?? fallbackProgress(collection, doc);
  return {
    ...progress,
    document_status: doc.status,
    filename: doc.filename,
    file_type: doc.file_type,
    file_size: doc.file_size,
    chunk_count: doc.chunk_count,
    error_message: doc.error_message,
    receivedAt,
  };
};

const progressFromStatus = (
  collection: string,
  doc: Document,
  status: BatchStatusItem,
): BatchDocumentProgress =>
  progressFromDocument(
    collection,
    {
      ...doc,
      status: status.status,
      error_message: status.error_message,
      chunk_count: status.chunk_count,
      progress: status.progress,
    },
    Date.now(),
  );

const isTerminalProgress = (progress: BatchDocumentProgress) =>
  progress.document_status === "ready" || progress.document_status === "failed";

const isCompleteProgress = (progress: BatchDocumentProgress) =>
  progress.status === "complete" || progress.document_status === "ready";

const isFailedProgress = (progress: BatchDocumentProgress) =>
  progress.status === "failed" || progress.document_status === "failed";

const uploadSessionFileName = (file: File) =>
  (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;

const uploadSessionClientId = (file: File, index: number) =>
  `${index}:${uploadSessionFileName(file)}:${file.size}:${file.lastModified}`;

const uploadConcurrency = 4;

export const useDocuments = (collection: string, status?: string) => {
  const queryKey = useMemo(
    () => queryKeys.documents.list({ collection, status }),
    [collection, status],
  );
  const path = useMemo(() => {
    const params = new URLSearchParams({ limit: "100" });
    if (status) params.set("status", status);
    return `v1/admin/realtime/collections/${encodeURIComponent(collection)}/documents?${params}`;
  }, [collection, status]);
  return useSseSnapshotQuery<DocListResponse>({
    queryKey,
    queryFn: () =>
      apiClient.get<DocListResponse>(`v1/collections/${encodeURIComponent(collection)}/documents`, {
        limit: 100,
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
      qc.invalidateQueries({ queryKey: queryKeys.documents.list({ collection }) });
      toast.success(`Queued ${res.total} document${res.total === 1 ? "" : "s"} for ingestion`);
    },
    onError: errorToast("Upload failed"),
  });
};

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
      const completed = await apiClient.post<UploadSession>(
        `v1/collections/${encodeURIComponent(collection)}/upload-sessions/${session.id}/complete`,
      );
      return { errors, session: completed };
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

export const useBatchDocumentProgress = (collection: string, documents: Document[]) => {
  const qc = useQueryClient();
  const failedRef = useRef<Set<string>>(new Set());
  const completedBatchRef = useRef<string | null>(null);
  const activeBatchRef = useRef<string | null>(null);
  const documentIds = useMemo(() => documents.map((doc) => doc.id), [documents]);
  const idsKey = documentIds.join(",");
  const batchKey = `${collection}:${idsKey}`;
  const enabled = Boolean(collection && documentIds.length);
  const queryKey = useMemo(
    () => queryKeys.documents.batchStatus({ collection, ids: idsKey }),
    [collection, idsKey],
  );
  const path = useMemo(() => {
    const params = new URLSearchParams();
    for (const id of documentIds) params.append("document_ids", id);
    return `v1/admin/realtime/collections/${encodeURIComponent(collection)}/documents/batch-status?${params}`;
  }, [collection, documentIds]);

  const query = useSseSnapshotQuery<BatchStatusResponse>({
    queryKey,
    queryFn: () =>
      apiClient.post<BatchStatusResponse>(
        `v1/collections/${encodeURIComponent(collection)}/documents/batch/status`,
        { document_ids: documentIds },
      ),
    enabled,
    path,
    closeWhen: (response) =>
      response.documents.length >= documentIds.length &&
      response.documents.every((doc) => doc.status === "ready" || doc.status === "failed"),
  });

  const statusDocuments = query.data?.documents;
  const items = useMemo(() => {
    const statusById = new Map(statusDocuments?.map((doc) => [doc.id, doc]) ?? []);
    return documents.map((doc) => {
      const status = statusById.get(doc.id);
      return status
        ? progressFromStatus(collection, doc, status)
        : progressFromDocument(collection, doc);
    });
  }, [collection, documents, statusDocuments]);
  const completedCount = items.filter(isCompleteProgress).length;
  const failedCount = items.filter(isFailedProgress).length;
  const terminalCount = items.filter(isTerminalProgress).length;
  const done = items.length > 0 && terminalCount === items.length;

  useEffect(() => {
    if (activeBatchRef.current !== batchKey) {
      activeBatchRef.current = batchKey;
      failedRef.current = new Set();
      completedBatchRef.current = null;
    }

    for (const item of items) {
      if (isFailedProgress(item) && !failedRef.current.has(item.document_id)) {
        failedRef.current.add(item.document_id);
        void qc.invalidateQueries({ queryKey: queryKeys.documents.list({ collection }) });
        void qc.invalidateQueries({
          queryKey: queryKeys.documents.one({ collection, id: item.document_id }),
        });
      }
    }

    if (done && completedBatchRef.current !== batchKey) {
      completedBatchRef.current = batchKey;
      void qc.invalidateQueries({ queryKey: queryKeys.documents.list({ collection }) });
    }
  }, [batchKey, collection, done, items, qc]);

  const active =
    items
      .filter((item) => !isTerminalProgress(item))
      .slice()
      .sort((a, b) => b.receivedAt - a.receivedAt)[0] ??
    items.slice().sort((a, b) => b.receivedAt - a.receivedAt)[0] ??
    null;
  const progress = items.length
    ? Math.round((items.reduce((sum, item) => sum + item.progress, 0) / items.length) * 100)
    : 0;

  return {
    active,
    completedCount,
    done,
    failedCount,
    items,
    progress,
    streaming: enabled && !done && query.streaming,
    total: documents.length,
  };
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
