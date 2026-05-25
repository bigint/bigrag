import { RefreshCw, Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Tooltip } from "@/components/ui/tooltip";
import type { DocumentListOrder, DocumentListSort } from "@/hooks/use-documents";

const statusOptions = [
  { value: "all", label: "All statuses" },
  { value: "ready", label: "Ready" },
  { value: "processing", label: "Processing" },
  { value: "pending", label: "Pending" },
  { value: "failed", label: "Failed" },
];
const sortOptions: { value: DocumentListSort; label: string }[] = [
  { value: "created_at", label: "Created" },
  { value: "updated_at", label: "Updated" },
  { value: "filename", label: "Filename" },
  { value: "file_size", label: "Size" },
  { value: "chunk_count", label: "Chunks" },
  { value: "status", label: "Status" },
];
const orderOptions: { value: DocumentListOrder; label: string }[] = [
  { value: "desc", label: "Desc" },
  { value: "asc", label: "Asc" },
];

interface DocumentsToolbarProps {
  readonly q: string;
  readonly status: string;
  readonly sort: DocumentListSort;
  readonly order: DocumentListOrder;
  readonly onFiltersChange: (
    next: Partial<{ q: string; status: string; sort: DocumentListSort; order: DocumentListOrder }>,
  ) => void;
  readonly loadedLabel: string;
  readonly selectedCount: number;
  readonly onClearSelection: () => void;
  readonly onBulkDelete: () => void;
  readonly onRefresh: () => void;
  readonly refreshPending: boolean;
}

export const DocumentsToolbar = ({
  q,
  status,
  sort,
  order,
  onFiltersChange,
  loadedLabel,
  selectedCount,
  onClearSelection,
  onBulkDelete,
  onRefresh,
  refreshPending,
}: DocumentsToolbarProps) => {
  const [qDraft, setQDraft] = useState(q);

  useEffect(() => {
    setQDraft(q);
  }, [q]);

  return (
    <Card className="rounded-xl">
      <CardContent className="flex flex-col gap-3 p-4">
        <form
          className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_160px_140px_120px_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            onFiltersChange({ q: qDraft.trim() });
          }}
        >
          <Input
            aria-label="Search documents"
            maxLength={200}
            onChange={(event) => setQDraft(event.target.value)}
            placeholder="Search filename, type, id, or error"
            trailing={<Search className="size-4" />}
            value={qDraft}
          />
          <Select
            aria-label="Status"
            onChange={(value) => onFiltersChange({ status: value === "all" ? "" : value })}
            options={statusOptions}
            value={status || "all"}
          />
          <Select
            aria-label="Sort"
            onChange={(value) => onFiltersChange({ sort: value as DocumentListSort })}
            options={sortOptions}
            value={sort}
          />
          <Select
            aria-label="Order"
            onChange={(value) => onFiltersChange({ order: value as DocumentListOrder })}
            options={orderOptions}
            value={order}
          />
          <div className="flex items-center gap-2">
            <Button type="submit">Apply</Button>
            {(q || status) && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setQDraft("");
                  onFiltersChange({ q: "", status: "" });
                }}
              >
                Clear
              </Button>
            )}
          </div>
        </form>
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span>{loadedLabel}</span>
            <Tooltip content="Refresh documents">
              <Button
                aria-label="Refresh documents"
                disabled={refreshPending}
                onClick={onRefresh}
                size="icon"
                variant="ghost"
              >
                {refreshPending ? <Spinner size="sm" /> : <RefreshCw className="size-4" />}
              </Button>
            </Tooltip>
          </div>
          {selectedCount > 0 && (
            <div className="flex items-center gap-2">
              <span>{selectedCount} selected</span>
              <Button size="sm" variant="secondary" onClick={onClearSelection}>
                Clear selection
              </Button>
              <Button size="sm" variant="destructive" onClick={onBulkDelete}>
                <Trash2 className="size-4" />
                Delete selected
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
