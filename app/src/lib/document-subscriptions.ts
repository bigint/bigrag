import type { RealtimeSnapshotSubscription } from "@/hooks/use-realtime-subscriptions";
import { chunkDocumentIds } from "@/lib/document-cache";
import type { DocumentListOrder, DocumentListSort } from "@/types/bigrag";

export const documentStatusSubscriptions = (
  collection: string,
  ids: string[],
): RealtimeSnapshotSubscription[] =>
  chunkDocumentIds(ids).map((documentIds, index) => ({
    key: `${collection}:${index}:${documentIds.join(",")}`,
    topic: "admin.collections.documents.batch_status",
    params: { collection, document_ids: documentIds },
  }));

export const documentListSubscription = ({
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

export const subscriptionDocumentIds = (subscription: RealtimeSnapshotSubscription) => {
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
