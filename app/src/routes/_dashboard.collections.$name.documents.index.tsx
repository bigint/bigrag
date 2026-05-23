import { createFileRoute } from "@tanstack/react-router";
import { DocumentsTab } from "@/features/collections/documents-tab";
import { decodeCollectionName } from "@/features/collections/use-collection-name";
import type { DocumentListOrder, DocumentListSort } from "@/hooks/use-documents";

const statuses = new Set(["", "pending", "processing", "ready", "failed"]);
const sorts = new Set([
  "created_at",
  "updated_at",
  "filename",
  "file_size",
  "chunk_count",
  "status",
]);
const orders = new Set(["asc", "desc"]);

type DocumentsSearch = {
  order?: DocumentListOrder;
  q?: string;
  sort?: DocumentListSort;
  status?: string;
};

const stringValue = (value: unknown) => (typeof value === "string" ? value : "");

const validateSearch = (search: Record<string, unknown>): DocumentsSearch => {
  const status = stringValue(search.status);
  const sort = stringValue(search.sort);
  const order = stringValue(search.order);
  const q = stringValue(search.q).slice(0, 200);
  return {
    ...(orders.has(order) && order !== "desc" ? { order: order as DocumentListOrder } : {}),
    ...(q ? { q } : {}),
    ...(sorts.has(sort) && sort !== "created_at" ? { sort: sort as DocumentListSort } : {}),
    ...(statuses.has(status) && status ? { status } : {}),
  };
};

const DocumentsRoute = () => {
  const { name: rawName } = Route.useParams();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const name = decodeCollectionName(rawName);
  const filters = {
    order: search.order ?? "desc",
    q: search.q ?? "",
    sort: search.sort ?? "created_at",
    status: search.status ?? "",
  };
  return (
    <DocumentsTab
      filters={filters}
      name={name}
      onFiltersChange={(next) =>
        navigate({
          search: (prev) => ({ ...prev, ...next }),
          replace: true,
        })
      }
    />
  );
};

export const Route = createFileRoute("/_dashboard/collections/$name/documents/")({
  component: DocumentsRoute,
  validateSearch,
});
