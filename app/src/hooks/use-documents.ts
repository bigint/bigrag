import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useRealtimeSnapshotQuery } from "@/hooks/use-realtime-snapshot-query";
import {
  type RealtimeSnapshotSubscription,
  useRealtimeSnapshotSubscriptions,
} from "@/hooks/use-realtime-subscriptions";
import { apiClient } from "@/lib/api";
import {
  type BatchStatusResponse,
  type DocListResponse,
  type DocumentPageParam,
  type InfiniteDocumentsData,
  mergeDocumentListSnapshot,
  mergeDocumentStatusUpdates,
  watchedDocumentIds,
} from "@/lib/document-cache";
import {
  documentListSubscription,
  documentStatusSubscriptions,
  subscriptionDocumentIds,
} from "@/lib/document-subscriptions";
import { fetchBatchStatus, fetchDocumentList } from "@/lib/documents-api";
import { queryKeys } from "@/lib/query-keys";
import type {
  Chunk,
  Document,
  DocumentListFilters,
  DocumentListOrder,
  DocumentListSort,
} from "@/types/bigrag";

export { useBatchDeleteDocuments, useDeleteDocument } from "@/hooks/use-document-mutations";
export {
  useCancelUploadSession,
  useUploadSession,
  useUploadSessionDocuments,
} from "@/hooks/use-upload-session-documents";
export type { DocumentListFilters, DocumentListOrder, DocumentListSort };

const documentListLimit = 1000;
const chunkListLimit = 1000;

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
      fetchDocumentList(
        collection,
        { limit, offset, order, q, sort, status, include_total: true },
        signal,
      ),
    enabled: !!collection,
    topic: "admin.collections.documents",
    params: realtimeParams,
  });
};

const useInfiniteDocumentsRealtime = ({
  collection,
  initialPageParam,
  limit,
  order,
  q,
  queryData,
  queryKey,
  sort,
  status,
}: {
  collection: string;
  initialPageParam: DocumentPageParam;
  limit: number;
  order: DocumentListOrder;
  q?: string;
  queryData: InfiniteDocumentsData | undefined;
  queryKey: ReturnType<typeof queryKeys.documents.infiniteList>;
  sort: DocumentListSort;
  status?: string;
}) => {
  const queryClient = useQueryClient();
  const subscriptions = useMemo(
    () => documentStatusSubscriptions(collection, watchedDocumentIds(queryData)),
    [collection, queryData],
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
      void fetchBatchStatus(collection, documentIds)
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
      void fetchDocumentList(collection, {
        include_total: true,
        limit,
        offset: 0,
        order,
        q,
        sort,
        status,
      })
        .then(applyListPayload)
        .catch(() => {
          void queryClient.invalidateQueries({ queryKey });
        });
    },
  });
};

export const useInfiniteDocuments = (collection: string, filters: DocumentListFilters = {}) => {
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
      fetchDocumentList(
        collection,
        {
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
      ),
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

  useInfiniteDocumentsRealtime({
    collection,
    initialPageParam,
    limit,
    order,
    q,
    queryData: query.data,
    queryKey,
    sort,
    status,
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
