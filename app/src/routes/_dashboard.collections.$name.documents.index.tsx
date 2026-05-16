import { createFileRoute } from "@tanstack/react-router";
import { DocumentsTab } from "@/features/collections/documents-tab";
import type { DocumentListOrder, DocumentListSort } from "@/hooks/use-documents";

const statuses = new Set(["", "pending", "processing", "ready", "failed"]);
const sorts = new Set(["created_at", "updated_at", "filename", "file_size", "chunk_count", "status"]);
const orders = new Set(["asc", "desc"]);

type DocumentsSearch = {
  order: DocumentListOrder;
  page: number;
  q: string;
  sort: DocumentListSort;
  status: string;
};

const stringValue = (value: unknown) => (typeof value === "string" ? value : "");

const validateSearch = (search: Record<string, unknown>): DocumentsSearch => {
  const status = stringValue(search.status);
  const sort = stringValue(search.sort);
  const order = stringValue(search.order);
  const page = Number(search.page);
  return {
    order: orders.has(order) ? (order as DocumentListOrder) : "desc",
    page: Number.isFinite(page) && page > 0 ? Math.floor(page) : 1,
    q: stringValue(search.q).slice(0, 200),
    sort: sorts.has(sort) ? (sort as DocumentListSort) : "created_at",
    status: statuses.has(status) ? status : "",
  };
};

const DocumentsRoute = () => {
  const { name: rawName } = Route.useParams();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const name = decodeURIComponent(rawName);
  return (
    <DocumentsTab
      filters={search}
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
