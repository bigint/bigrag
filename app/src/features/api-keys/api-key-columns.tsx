import { RotateCcw, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Column } from "@/components/ui/data-table";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import { formatRelativeOrNever } from "@/lib/format";
import type { ApiKey } from "@/types/bigrag";

interface ApiKeyColumnsOptions {
  readonly onToggle: (id: string, active: boolean) => void;
  readonly onRotate: (id: string) => void;
  readonly rotatePending: boolean;
  readonly onDelete: (key: ApiKey) => void;
}

export const apiKeyColumns = ({
  onToggle,
  onRotate,
  rotatePending,
  onDelete,
}: ApiKeyColumnsOptions): Column<ApiKey>[] => [
  {
    header: "Name",
    key: "name",
    render: (k) => <span className="text-sm font-medium">{k.name}</span>,
  },
  {
    header: "Prefix",
    key: "prefix",
    className: "font-mono text-xs text-muted-foreground",
    render: (k) => `${k.prefix}…`,
  },
  {
    header: "Scope",
    key: "scope",
    render: (k) => (
      <div className="flex flex-col gap-1">
        {k.collection ? (
          <Badge variant="neutral">{k.collection}</Badge>
        ) : (
          <span className="text-muted-foreground text-xs">All collections</span>
        )}
        <span className="text-xs text-muted-foreground">
          {k.scopes.length ? k.scopes.join(", ") : "Full access"}
        </span>
      </div>
    ),
  },
  {
    header: "Status",
    key: "status",
    render: (k) => (
      <Badge dot variant={k.active ? "success" : "neutral"}>
        {k.active ? "Active" : "Revoked"}
      </Badge>
    ),
  },
  {
    header: "Last used",
    key: "last_used_at",
    className: "text-muted-foreground",
    render: (k) => formatRelativeOrNever(k.last_used_at),
  },
  {
    header: "Expires",
    key: "expires_at",
    className: "text-muted-foreground",
    render: (k) => formatRelativeOrNever(k.expires_at),
  },
  {
    header: "Actions",
    headerClassName: "text-right",
    className: "text-right",
    key: "actions",
    render: (k) => (
      <div className="flex items-center justify-end gap-2">
        <Tooltip content={k.active ? "Disable key" : "Re-enable key"}>
          <Switch
            aria-label={k.active ? "Disable key" : "Re-enable key"}
            checked={k.active}
            onCheckedChange={(active) => onToggle(k.id, active)}
          />
        </Tooltip>
        <Tooltip content="Rotate key">
          <Button
            aria-label="Rotate"
            disabled={rotatePending}
            onClick={() => onRotate(k.id)}
            size="sm"
            variant="ghost"
          >
            <RotateCcw className="size-4" />
          </Button>
        </Tooltip>
        <Tooltip content="Delete key">
          <Button
            aria-label="Delete"
            className="hover:bg-destructive/10 hover:text-destructive"
            onClick={() => onDelete(k)}
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
