import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useMemo } from "react";
import { toast } from "sonner";
import {
  type RealtimeSnapshotSubscription,
  useRealtimeSnapshotQuery,
  useRealtimeSnapshotSubscriptions,
} from "@/hooks/use-realtime-snapshot-query";
import { apiClient } from "@/lib/api";
import { errorToast } from "@/lib/mutation-toast";
import { queryKeys } from "@/lib/query-keys";
import type { Chunk, Document, UploadSession, UploadSessionFileResponse } from "@/types/bigrag";
import type { Paginated } from "@/types/pagination";

type DocListResponse = Paginated<"documents", Document>;
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
type DocumentPageParam = {
  cursor: string | null;
  offset: number;
  mode: "cursor" | "offset";
};
type DocumentStatusUpdate = Pick<
  Document,
  "chunk_count" | "error_message" | "id" | "multimodal_element_count" | "progress" | "status"
>;
type BatchStatusResponse = {
  documents: DocumentStatusUpdate[];
  total: number;
};
type InfiniteDocumentsData = InfiniteData<DocListResponse>;

const uploadSessionFileName = (file: File) =>
  (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;

const uploadSessionClientId = (file: File, index: number) =>
  `${index}:${uploadSessionFileName(file)}:${file.size}:${file.lastModified}`;

const documentListLimit = 1000;
const chunkListLimit = 1000;
const uploadConcurrency = 4;
const documentStatusBatchSize = 100;
const activeDocumentStatuses = new Set<Document["status"]>(["pending", "processing"]);

const batchStatusPath = (collection: string) =>
  `v1/collections/${encodeURIComponent(collection)}/documents/batch/status`;

const chunkDocumentIds = (ids: string[]) => {
  const chunks: string[][] = [];
  for (let index = 0; index < ids.length; index += documentStatusBatchSize) {
    chunks.push(ids.slice(index, index + documentStatusBatchSize));
  }
  return chunks;
};

const watchedDocumentIds = (data: InfiniteDocumentsData | undefined) => {
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const page of data?.pages ?? []) {
    for (const document of page.documents) {
      if (!activeDocumentStatuses.has(document.status) || seen.has(document.id)) continue;
      seen.add(document.id);
      ids.push(document.id);
    }
  }
  return ids;
};

const documentStatusSubscriptions = (
  collection: string,
  ids: string[],
): RealtimeSnapshotSubscription[] =>
  chunkDocumentIds(ids).map((documentIds, index) => ({
    key: `${collection}:${index}:${documentIds.join(",")}`,
    topic: "admin.collections.documents.batch_status",
    params: { collection, document_ids: documentIds },
  }));

const documentListSubscription = ({
  collection,
  limit,
  order,
  q,
  sort,
  status,
}: {
  collection: string;
  limit: number;
  order: DocumentListOrder;
  q?: string;
  sort: DocumentListSort;
  status?: string;
}): RealtimeSnapshotSubscription => ({
  key: `${collection}:${limit}:${order}:${q ?? ""}:${sort}:${status ?? ""}`,
  topic: "admin.collections.documents",
  params: {
    collection,
    include_total: true,
    limit,
    offset: 0,
    order,
    q,
    sort,
    status,
  },
});

const mergeDocumentStatusUpdates = (
  current: InfiniteDocumentsData | undefined,
  updates: DocumentStatusUpdate[],
): InfiniteDocumentsData | undefined => {
  if (!current || updates.length === 0) return current;
  const updatesById = new Map(updates.map((document) => [document.id, document]));
  let changed = false;
  const pages = current.pages.map((page) => {
    let pageChanged = false;
    const documents = page.documents.map((document) => {
      const update = updatesById.get(document.id);
      if (!update) return document;
      const unchanged =
        document.status === update.status &&
        document.error_message === update.error_message &&
        document.chunk_count === update.chunk_count &&
        document.multimodal_element_count === update.multimodal_element_count &&
        document.progress === update.progress;
      if (unchanged) return document;
      pageChanged = true;
      return {
        ...document,
        chunk_count: update.chunk_count,
        error_message: update.error_message,
        multimodal_element_count: update.multimodal_element_count,
        progress: update.progress,
        status: update.status,
      };
    });
    if (!pageChanged) return page;
    changed = true;
    return { ...page, documents };
  });
  return changed ? { ...current, pages } : current;
};

const mergeDocumentListSnapshot = (
  current: InfiniteDocumentsData | undefined,
  snapshot: DocListResponse,
  firstPageParam: DocumentPageParam,
  limit: number,
): InfiniteDocumentsData => {
  if (!current || current.pages.length === 0) {
    return { pageParams: [firstPageParam], pages: [snapshot] };
  }
  const existingTotal = current.pages.find((page) => page.total !== null)?.total ?? null;
  const firstPage = { ...snapshot, total: snapshot.total ?? existingTotal };
  const firstPageIds = new Set(firstPage.documents.map((document) => document.id));
  const previousDocuments = current.pages
    .flatMap((page) => page.documents)
    .filter((document) => !firstPageIds.has(document.id));
  const pages = [firstPage];
  let previousIndex = 0;
  for (let pageIndex = 1; pageIndex < current.pages.length; pageIndex += 1) {
    const pageSize = Math.min(limit, current.pages[pageIndex]?.documents.length ?? limit);
    const documents = previousDocuments.slice(previousIndex, previousIndex + pageSize);
    previousIndex += pageSize;
    if (documents.length === 0) break;
    pages.push({ ...current.pages[pageIndex], documents });
  }
  return {
    ...current,
    pageParams: current.pageParams.slice(0, pages.length),
    pages,
  };
};

const subscriptionDocumentIds = (subscription: RealtimeSnapshotSubscription) => {
  const value = subscription.params?.document_ids;
  if (Array.isArray(value)) return value;
  if (typeof value === "string") {
    return value
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);
  }
  return [];
};

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

export const useInfiniteDocuments = (collection: string, filters: DocumentListFilters = {}) => {
  const queryClient = useQueryClient();
  const limit = filters.limit ?? documentListLimit;
  const q = filters.q?.trim() || undefined;
  const status = filters.status || undefined;
  const sort = filters.sort ?? "created_at";
  const order = filters.order ?? "desc";
  const mode: DocumentPageParam["mode"] = sort === "created_at" ? "cursor" : "offset";
  const initialPageParam = useMemo<DocumentPageParam>(
    () => ({ cursor: null, offset: 0, mode }),
    [mode],
  );
  const queryKey = useMemo(
    () => queryKeys.documents.infiniteList({ collection, q, status, sort, order, limit }),
    [collection, limit, order, q, sort, status],
  );

  const query = useInfiniteQuery({
    queryKey,
    initialPageParam,
    queryFn: ({ pageParam, signal }) =>
      apiClient.get<DocListResponse>(`v1/collections/${encodeURIComponent(collection)}/documents`, {
        searchParams: {
          limit,
          order,
          q,
          sort,
          status,
          include_total: pageParam.offset === 0,
          cursor: pageParam.mode === "cursor" ? pageParam.cursor : undefined,
          offset: pageParam.mode === "offset" ? pageParam.offset : undefined,
        },
        signal,
      }),
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.reduce((sum, page) => sum + page.documents.length, 0);
      if (mode === "cursor") {
        return lastPage.next_cursor ? { cursor: lastPage.next_cursor, offset: loaded, mode } : null;
      }
      const total = pages.find((page) => page.total !== null)?.total;
      if (total !== undefined && total !== null && loaded >= total) return null;
      return lastPage.documents.length >= limit ? { cursor: null, offset: loaded, mode } : null;
    },
    enabled: !!collection,
    retry: false,
  });
  const subscriptions = useMemo(
    () => documentStatusSubscriptions(collection, watchedDocumentIds(query.data)),
    [collection, query.data],
  );
  const listSubscription = useMemo(
    () => documentListSubscription({ collection, limit, order, q, sort, status }),
    [collection, limit, order, q, sort, status],
  );
  const applyListPayload = (payload: DocListResponse) => {
    queryClient.setQueryData<InfiniteDocumentsData>(queryKey, (current) =>
      mergeDocumentListSnapshot(current, payload, initialPageParam, limit),
    );
  };
  const applyStatusPayload = (
    payload: BatchStatusResponse,
    subscription: RealtimeSnapshotSubscription,
  ) => {
    const documentIds = subscriptionDocumentIds(subscription);
    queryClient.setQueryData<InfiniteDocumentsData>(queryKey, (current) =>
      mergeDocumentStatusUpdates(current, payload.documents),
    );
    if (documentIds.length > payload.documents.length) {
      void queryClient.invalidateQueries({ queryKey });
    }
  };

  useRealtimeSnapshotSubscriptions<BatchStatusResponse>({
    enabled: !!collection && subscriptions.length > 0,
    pollIntervalMs: 5_000,
    subscriptions,
    onSnapshot: (payload, subscription) => {
      applyStatusPayload(payload, subscription);
    },
    onUnavailable: (subscription) => {
      const documentIds = subscriptionDocumentIds(subscription);
      if (documentIds.length === 0) {
        void queryClient.invalidateQueries({ queryKey });
        return;
      }
      void apiClient
        .post<BatchStatusResponse>(batchStatusPath(collection), { document_ids: documentIds })
        .then((payload) => {
          applyStatusPayload(payload, subscription);
        })
        .catch(() => {
          void queryClient.invalidateQueries({ queryKey });
        });
    },
  });

  useRealtimeSnapshotSubscriptions<DocListResponse>({
    enabled: !!collection,
    pollIntervalMs: 5_000,
    subscriptions: [listSubscription],
    onSnapshot: applyListPayload,
    onUnavailable: () => {
      void apiClient
        .get<DocListResponse>(`v1/collections/${encodeURIComponent(collection)}/documents`, {
          searchParams: {
            include_total: true,
            limit,
            offset: 0,
            order,
            q,
            sort,
            status,
          },
        })
        .then(applyListPayload)
        .catch(() => {
          void queryClient.invalidateQueries({ queryKey });
        });
    },
  });

  return query;
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
