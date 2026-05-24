import { Link } from "@tanstack/react-router";
import { Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FileType } from "@/features/collections/documents/file-type";
import { formatBytes, formatRelative } from "@/lib/format";
import type { Document, DocumentStatus } from "@/types/bigrag";

const statusVariant: Record<DocumentStatus, "success" | "warning" | "info" | "error"> = {
  ready: "success",
  processing: "info",
  pending: "warning",
  failed: "error",
};

interface DocumentsTableProps {
  readonly name: string;
  readonly documents: Document[];
  readonly total: number | null;
  readonly selected: Set<string>;
  readonly allVisibleSelected: boolean;
  readonly onToggleVisibleSelection: () => void;
  readonly onToggleDocumentSelection: (id: string) => void;
  readonly onDelete: (doc: { id: string; filename: string }) => void;
}

export const DocumentsTable = ({
  name,
  documents,
  total,
  selected,
  allVisibleSelected,
  onToggleVisibleSelection,
  onToggleDocumentSelection,
  onDelete,
}: DocumentsTableProps) => (
  <div className="overflow-hidden rounded-xl border border-border bg-card">
    <div className="border-b border-border">
      <div className="grid grid-cols-[auto_1fr_auto_auto_auto_auto] gap-4 px-4 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        <input
          aria-label="Select visible documents"
          checked={allVisibleSelected}
          className="size-4 rounded border-border"
          onChange={onToggleVisibleSelection}
          type="checkbox"
        />
        <span>Filename</span>
        <span className="text-right">Size</span>
        <span className="text-right">Chunks</span>
        <span className="text-right">Updated</span>
        <span className="w-6" />
      </div>
      {total != null && total > documents.length && (
        <div className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
          Showing {documents.length.toLocaleString()} of {total.toLocaleString()} documents.
        </div>
      )}
    </div>
    <ul className="divide-y divide-border">
      {documents.map((d) => (
        <li
          key={d.id}
          className="group grid grid-cols-[auto_1fr_auto_auto_auto_auto] items-center gap-4 px-4 py-3 hover:bg-muted [content-visibility:auto] [contain-intrinsic-size:auto_3.5rem]"
        >
          <input
            aria-label={`Select ${d.filename}`}
            checked={selected.has(d.id)}
            className="size-4 rounded border-border"
            onChange={() => onToggleDocumentSelection(d.id)}
            type="checkbox"
          />
          <Link
            params={{ docId: d.id, name }}
            to="/collections/$name/documents/$docId"
            className="flex min-w-0 items-center gap-3"
          >
            <FileType type={d.file_type} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{d.filename}</div>
              <div className="mt-0.5 flex items-center gap-2">
                <Badge dot variant={statusVariant[d.status]}>
                  {d.status}
                </Badge>
                {d.error_message && (
                  <span className="truncate text-xs text-destructive">{d.error_message}</span>
                )}
              </div>
            </div>
          </Link>
          <span className="text-right text-sm tabular-nums text-muted-foreground">
            {formatBytes(d.file_size)}
          </span>
          <span className="text-right text-sm tabular-nums text-muted-foreground">
            {d.chunk_count}
          </span>
          <span className="text-right text-sm text-muted-foreground">
            {formatRelative(d.updated_at)}
          </span>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Delete"
            onClick={(e) => {
              e.preventDefault();
              onDelete({ id: d.id, filename: d.filename });
            }}
          >
            <Trash2 className="size-4" />
          </Button>
        </li>
      ))}
    </ul>
  </div>
);
