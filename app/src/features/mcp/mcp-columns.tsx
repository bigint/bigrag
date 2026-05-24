import { Plug, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Column } from "@/components/ui/data-table";
import { Tooltip } from "@/components/ui/tooltip";
import { formatRelativeOrNever } from "@/lib/format";
import type { McpServer } from "@/types/bigrag";

interface McpColumnsOptions {
  readonly onOpenDetail: (id: string) => void;
  readonly onDelete: (server: McpServer) => void;
}

export const mcpColumns = ({ onOpenDetail, onDelete }: McpColumnsOptions): Column<McpServer>[] => [
  {
    header: "Title",
    key: "title",
    render: (s) => (
      <button
        className="flex items-center gap-2 text-left font-medium text-sm hover:underline"
        onClick={() => onOpenDetail(s.id)}
        type="button"
      >
        <Plug className="size-4 shrink-0 text-muted-foreground" /> {s.title}
      </button>
    ),
  },
  {
    header: "Server name",
    key: "server_name",
    className: "font-mono text-xs text-muted-foreground",
    render: (s) => s.server_name,
  },
  {
    header: "Scope",
    key: "scope",
    render: (s) =>
      s.collection ? (
        <Badge variant="neutral">{s.collection}</Badge>
      ) : (
        <span className="text-muted-foreground text-xs">all collections</span>
      ),
  },
  {
    header: "Key prefix",
    key: "key_prefix",
    className: "font-mono text-xs text-muted-foreground",
    render: (s) => `${s.key_prefix}…`,
  },
  {
    header: "Last used",
    key: "last_used_at",
    className: "text-muted-foreground",
    render: (s) => formatRelativeOrNever(s.last_used_at),
  },
  {
    header: "Actions",
    headerClassName: "text-right",
    className: "text-right",
    key: "actions",
    render: (s) => (
      <div className="flex items-center justify-end gap-2">
        <Tooltip content="Delete">
          <Button
            aria-label="Delete"
            className="hover:bg-destructive/10 hover:text-destructive"
            onClick={() => onDelete(s)}
            size="sm"
            variant="ghost"
          >
            <Trash2 className="size-4" />
          </Button>
        </Tooltip>
      </div>
    ),
  },
];
