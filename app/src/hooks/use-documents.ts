import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { apiClient } from "@/lib/api";
import type { DocumentPageParam } from "@/lib/document-cache";
import { fetchDocumentList } from "@/lib/documents-api";
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
const statusPollMs = 5_000;
const terminalDocumentStatuses = new Set<Document["status"]>(["ready", "failed"]);

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
  return useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      fetchDocumentList(
        collection,
        { limit, offset, order, q, sort, status, include_total: true },
        signal,
      ),
    enabled: !!collection,
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

  return query;
};

export const useDocument = (collection: string, docId: string) => {
  const queryKey = useMemo(
    () => queryKeys.documents.one({ collection, id: docId }),
    [collection, docId],
  );
  return useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      apiClient.get<Document>(
        `v1/collections/${encodeURIComponent(collection)}/documents/${docId}`,
        { signal },
      ),
    enabled: !!collection && !!docId,
    refetchInterval: (query) => {
      const doc = query.state.data;
      return doc && terminalDocumentStatuses.has(doc.status) ? false : statusPollMs;
    },
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
