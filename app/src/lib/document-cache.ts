import type { InfiniteData } from "@tanstack/react-query";
import type { Document } from "@/types/bigrag";
import type { Paginated } from "@/types/pagination";

export type DocListResponse = Paginated<"documents", Document>;

export type DocumentPageParam = {
  cursor: string | null;
  offset: number;
  mode: "cursor" | "offset";
};

export type DocumentStatusUpdate = Pick<
  Document,
  "chunk_count" | "error_message" | "id" | "multimodal_element_count" | "progress" | "status"
>;

export type BatchStatusResponse = {
  documents: DocumentStatusUpdate[];
  total: number;
};

export type InfiniteDocumentsData = InfiniteData<DocListResponse>;

const documentStatusBatchSize = 100;
const activeDocumentStatuses = new Set<Document["status"]>(["pending", "processing"]);

export const chunkDocumentIds = (ids: string[]) => {
  const chunks: string[][] = [];
  for (let index = 0; index < ids.length; index += documentStatusBatchSize) {
    chunks.push(ids.slice(index, index + documentStatusBatchSize));
  }
  return chunks;
};

export const watchedDocumentIds = (data: InfiniteDocumentsData | undefined) => {
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

export const mergeDocumentStatusUpdates = (
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

export const mergeDocumentListSnapshot = (
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
