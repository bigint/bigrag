import { Plus, Send, Trash2, Webhook as WebhookIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Tooltip } from "@/components/ui/tooltip";
import type { Webhook } from "@/types/rag-computer";

interface Props {
  webhooks: Webhook[];
  loading: boolean;
  onAdd: () => void;
  onTest: (id: string) => void;
  onDelete: (id: string) => void;
}

export const WebhookList = ({ webhooks, loading, onAdd, onTest, onDelete }: Props) => {
  const columns: Column<Webhook>[] = [
    {
      header: "URL",
      key: "url",
      render: (w) => (
        <Tooltip content={w.url}>
          <span className="block max-w-[320px] truncate font-mono text-xs">{w.url}</span>
        </Tooltip>
      ),
    },
    {
      header: "Events",
      key: "events",
      render: (w) => (
        <Badge variant="neutral">
          {w.events.length} {w.events.length === 1 ? "event" : "events"}
        </Badge>
      ),
    },
    {
      header: "Status",
      key: "active",
      render: (w) => (
        <Badge dot variant={w.active ? "success" : "neutral"}>
          {w.active ? "Active" : "Paused"}
        </Badge>
      ),
    },
    {
      className: "text-right",
      header: "Actions",
      headerClassName: "text-right",
      key: "actions",
      render: (w) => (
        <div className="flex items-center justify-end gap-1">
          <Tooltip content="Send test payload">
            <Button
              aria-label="Test webhook"
              onClick={() => onTest(w.id)}
              size="sm"
              variant="ghost"
            >
              <Send className="size-4" />
            </Button>
          </Tooltip>
          <Tooltip content="Delete webhook">
            <Button
              aria-label="Delete webhook"
              className="hover:bg-destructive/10 hover:text-destructive"
              onClick={() => onDelete(w.id)}
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

  return (
    <DataTable
      columns={columns}
      data={webhooks}
      emptyAction={
        <Button onClick={onAdd}>
          <Plus className="size-4" />
          Add your first webhook
        </Button>
      }
      emptyIcon={<WebhookIcon className="size-6" />}
      emptyTitle="No webhooks yet"
      emptyDescription="Receive callbacks when documents ingest, fail, or collections change."
      keyExtractor={(w) => w.id}
      loading={loading}
      loadingMessage="Loading webhooks…"
    />
  );
};
