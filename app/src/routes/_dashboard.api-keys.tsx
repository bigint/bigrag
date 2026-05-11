import { createFileRoute } from "@tanstack/react-router";
import { Check, Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
  useUpdateApiKey,
} from "@/hooks/use-api-keys";
import { useCollections } from "@/hooks/use-collections";
import { formatRelative } from "@/lib/format";
import type { ApiKey, CreatedApiKey } from "@/types/rag-computer";

const UNSCOPED = "__all__";

export const Route = createFileRoute("/_dashboard/api-keys")({
  component: () => <ApiKeysPage />,
});

const ApiKeysPage = () => {
  const { data, isPending } = useApiKeys();
  const { data: collectionsData } = useCollections();
  const create = useCreateApiKey();
  const toggle = useUpdateApiKey();
  const revoke = useDeleteApiKey();

  const collections = collectionsData?.collections ?? [];

  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [collection, setCollection] = useState<string>(UNSCOPED);
  const [newKey, setNewKey] = useState<CreatedApiKey | null>(null);
  const [copied, setCopied] = useState(false);
  const [deleteFor, setDeleteFor] = useState<ApiKey | null>(null);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const created = await create.mutateAsync({
        name,
        collection: collection === UNSCOPED ? null : collection,
      });
      setNewKey(created);
      setName("");
      setCollection(UNSCOPED);
      setAddOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  const copy = async () => {
    if (!newKey) return;
    await navigator.clipboard.writeText(newKey.key);
    setCopied(true);
    toast.success("Copied");
    setTimeout(() => setCopied(false), 1800);
  };

  const columns: Column<ApiKey>[] = [
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
      render: (k) =>
        k.collection ? (
          <Badge variant="neutral">{k.collection}</Badge>
        ) : (
          <span className="text-muted-foreground text-xs">All collections</span>
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
      render: (k) => (k.last_used_at ? formatRelative(k.last_used_at) : "never"),
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
              onCheckedChange={(active) => toggle.mutate({ active, id: k.id })}
            />
          </Tooltip>
          <Tooltip content="Delete key">
            <Button
              aria-label="Delete"
              className="hover:bg-destructive/10 hover:text-destructive"
              onClick={() => setDeleteFor(k)}
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
    <div>
      <PageHeader
        title="API keys"
        description="Mint long-lived keys for external services, shown once at creation."
        actions={
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="size-4" /> New key
          </Button>
        }
      />

      <DataTable
        columns={columns}
        data={data?.keys ?? []}
        emptyAction={
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="size-4" /> Create your first key
          </Button>
        }
        emptyIcon={<KeyRound className="size-6" />}
        emptyTitle="No API keys yet"
        emptyDescription="Create a key for external services that need to call the rag.computer API."
        keyExtractor={(k) => k.id}
        loading={isPending}
        loadingMessage="Loading keys…"
      />

      <Modal onClose={() => setAddOpen(false)} open={addOpen} title="New API key">
        <form onSubmit={submit} className="space-y-4">
          <Input
            label="Name"
            description="A descriptive label — e.g. 'raven-production'."
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            required
          />
          <Select
            label="Collection scope"
            value={collection}
            onChange={setCollection}
            options={[
              { value: UNSCOPED, label: "All collections (full workspace)" },
              ...collections.map((c) => ({ value: c.name, label: c.name })),
            ]}
          />
          <p className="text-xs text-muted-foreground">
            Scoped keys can only use endpoints for the pinned collection. Cross-collection endpoints
            return 403.
          </p>
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="secondary" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create key"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal onClose={() => setNewKey(null)} open={!!newKey} title="Save this key">
        {newKey && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              This is the only time you'll see the full key. Copy it now.
            </p>
            <div className="break-all rounded-md border border-border bg-muted p-3 font-mono text-xs">
              {newKey.key}
            </div>
            <div className="flex justify-end">
              <Button onClick={copy} size="lg">
                {copied ? (
                  <>
                    <Check className="size-4" /> Copied
                  </>
                ) : (
                  <>
                    <Copy className="size-4" /> Copy key
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        confirmLabel="Revoke"
        description={
          deleteFor
            ? `Revoke "${deleteFor.name}"? Services using this key will stop working immediately.`
            : ""
        }
        loading={revoke.isPending}
        onClose={() => setDeleteFor(null)}
        onConfirm={async () => {
          if (!deleteFor) return;
          try {
            await revoke.mutateAsync(deleteFor.id);
            setDeleteFor(null);
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed");
          }
        }}
        open={!!deleteFor}
        title="Revoke API key"
      />
    </div>
  );
};
