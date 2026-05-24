import { KeyRound, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DataTable } from "@/components/ui/data-table";
import { Page } from "@/components/ui/page";
import { apiKeyColumns } from "@/features/api-keys/api-key-columns";
import { CreateApiKeyModal } from "@/features/api-keys/create-api-key-modal";
import { CreatedKeyModal } from "@/features/api-keys/created-key-modal";
import {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
  useRotateApiKey,
  useUpdateApiKey,
} from "@/hooks/use-api-keys";
import { useCollections } from "@/hooks/use-collections";
import type { ApiKey, CreatedApiKey } from "@/types/bigrag";

export const ApiKeysPage = () => {
  const { data, isPending } = useApiKeys();
  const { data: collectionsData } = useCollections();
  const create = useCreateApiKey();
  const rotate = useRotateApiKey();
  const toggle = useUpdateApiKey();
  const revoke = useDeleteApiKey();

  const collections = collectionsData?.collections ?? [];

  const [addOpen, setAddOpen] = useState(false);
  const [newKey, setNewKey] = useState<CreatedApiKey | null>(null);
  const [deleteFor, setDeleteFor] = useState<ApiKey | null>(null);

  const rotateKey = async (id: string) => {
    try {
      const rotated = await rotate.mutateAsync(id);
      setNewKey(rotated);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Rotate failed");
    }
  };

  const columns = apiKeyColumns({
    onToggle: (id, active) => toggle.mutate({ active, id }),
    onRotate: rotateKey,
    rotatePending: rotate.isPending,
    onDelete: setDeleteFor,
  });

  return (
    <Page.Shell>
      <Page.Header
        title="API keys"
        description="Mint long-lived keys for external services, shown once at creation."
        className="mb-0"
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
        emptyDescription="Create a key for external services that need to call the bigRAG API."
        keyExtractor={(k) => k.id}
        loading={isPending}
        loadingMessage="Loading keys…"
      />

      <CreateApiKeyModal
        collections={collections}
        creating={create.isPending}
        onClose={() => setAddOpen(false)}
        onSubmit={async (body) => {
          try {
            const created = await create.mutateAsync(body);
            setNewKey(created);
            setAddOpen(false);
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Failed");
            throw err;
          }
        }}
        open={addOpen}
      />

      <CreatedKeyModal createdKey={newKey} onClose={() => setNewKey(null)} />

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
    </Page.Shell>
  );
};
