import { apiClient } from "@/lib/api";
import type { DocListResponse } from "@/lib/document-cache";
import type { DocumentListOrder, DocumentListSort } from "@/types/bigrag";

export type DocumentListQuery = {
  cursor?: string | null;
  include_total?: boolean;
  limit?: number;
  offset?: number;
  order?: DocumentListOrder;
  q?: string;
  sort?: DocumentListSort;
  status?: string;
};

export const fetchDocumentList = (
  collection: string,
  filters: DocumentListQuery,
  signal?: AbortSignal,
) =>
  apiClient.get<DocListResponse>(`v1/collections/${encodeURIComponent(collection)}/documents`, {
    searchParams: {
      cursor: filters.cursor,
      include_total: filters.include_total,
      limit: filters.limit,
      offset: filters.offset,
      order: filters.order,
      q: filters.q,
      sort: filters.sort,
      status: filters.status,
    },
    signal,
  });
