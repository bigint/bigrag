import { useForm } from "@tanstack/react-form";
import { Check, Copy, KeyRound, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Page } from "@/components/ui/page";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip } from "@/components/ui/tooltip";
import { bigragApiUrl } from "@/config/runtime";
import {
  API_KEY_UNSCOPED,
  apiKeyBodyFromValues,
  defaultApiKeyFormValues,
  validateApiKeyFormValues,
} from "@/features/api-keys/api-key-form-state";
import {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
  useRotateApiKey,
  useUpdateApiKey,
} from "@/hooks/use-api-keys";
import { useCollections } from "@/hooks/use-collections";
import { errorText, firstString, submitWith } from "@/lib/form";
import { formatRelative } from "@/lib/format";
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
  const [copied, setCopied] = useState(false);
  const [deleteFor, setDeleteFor] = useState<ApiKey | null>(null);
  const [testingKey, setTestingKey] = useState(false);
  const form = useForm({
    defaultValues: defaultApiKeyFormValues(),
    validators: {
      onSubmit: ({ value }) => validateApiKeyFormValues(value),
    },
    onSubmit: async ({ value }) => {
      try {
        const created = await create.mutateAsync(apiKeyBodyFromValues(value));
        setNewKey(created);
        form.reset(defaultApiKeyFormValues());
        setAddOpen(false);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed");
      }
    },
  });

  const copy = async () => {
    if (!newKey) return;
    await navigator.clipboard.writeText(newKey.key);
    setCopied(true);
    toast.success("Copied");
    setTimeout(() => setCopied(false), 1800);
  };

  const testNewKey = async () => {
    if (!newKey) return;
    setTestingKey(true);
    try {
      const response = await fetch(`${bigragApiUrl}/v1/auth/whoami`, {
        headers: { Authorization: `Bearer ${newKey.key}` },
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      toast.success("Key connected");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Key test failed");
    } finally {
      setTestingKey(false);
    }
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
      render: (k) => (k.last_used_at ? formatRelative(k.last_used_at) : "never"),
    },
    {
      header: "Expires",
      key: "expires_at",
      className: "text-muted-foreground",
      render: (k) => (k.expires_at ? formatRelative(k.expires_at) : "never"),
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
          <Tooltip content="Rotate key">
            <Button
              aria-label="Rotate"
              disabled={rotate.isPending}
              onClick={async () => {
                try {
                  const rotated = await rotate.mutateAsync(k.id);
                  setNewKey(rotated);
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : "Rotate failed");
                }
              }}
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

      <Modal onClose={() => setAddOpen(false)} open={addOpen} title="New API key">
        <form className="space-y-4" noValidate onSubmit={submitWith(() => form.handleSubmit())}>
          <form.Subscribe selector={(state) => state.errors}>
            {(errors) => {
              const formError = firstString(errors);
              return formError ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              ) : null;
            }}
          </form.Subscribe>
          <form.Field
            name="name"
            validators={{
              onSubmit: ({ value }) => (value.trim() ? undefined : "Name is required"),
            }}
          >
            {(field) => (
              <Input
                autoFocus
                description="A descriptive label — e.g. 'raven-production'."
                error={errorText(field.state.meta.errors)}
                label="Name"
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                required
                value={field.state.value}
              />
            )}
          </form.Field>
          <form.Field name="collection">
            {(field) => (
              <Select
                label="Collection scope"
                onChange={field.handleChange}
                options={[
                  { value: API_KEY_UNSCOPED, label: "All collections (full workspace)" },
                  ...collections.map((c) => ({ value: c.name, label: c.name })),
                ]}
                value={field.state.value}
              />
            )}
          </form.Field>
          <form.Field name="accessLevel">
            {(field) => (
              <Select
                label="Access level"
                onChange={(value) =>
                  field.handleChange(value as "full" | "read" | "write" | "custom")
                }
                options={[
                  { value: "full", label: "Full access" },
                  { value: "read", label: "Read/query only" },
                  { value: "write", label: "Upload/write" },
                  { value: "custom", label: "Custom scopes" },
                ]}
                value={field.state.value}
              />
            )}
          </form.Field>
          <form.Subscribe selector={(state) => state.values.accessLevel}>
            {(accessLevel) =>
              accessLevel === "custom" ? (
                <form.Field name="scopesText">
                  {(field) => (
                    <Textarea
                      description="Use one scope per line or comma-separated, e.g. collection:read."
                      error={errorText(field.state.meta.errors)}
                      label="Scopes"
                      onBlur={field.handleBlur}
                      onChange={(e) => field.handleChange(e.target.value)}
                      value={field.state.value}
                    />
                  )}
                </form.Field>
              ) : null
            }
          </form.Subscribe>
          <form.Field name="expiresPreset">
            {(field) => (
              <Select
                label="Expiration"
                onChange={(value) =>
                  field.handleChange(value as "never" | "7d" | "30d" | "90d" | "custom")
                }
                options={[
                  { value: "never", label: "Never" },
                  { value: "7d", label: "7 days" },
                  { value: "30d", label: "30 days" },
                  { value: "90d", label: "90 days" },
                  { value: "custom", label: "Custom date" },
                ]}
                value={field.state.value}
              />
            )}
          </form.Field>
          <form.Subscribe selector={(state) => state.values.expiresPreset}>
            {(expiresPreset) =>
              expiresPreset === "custom" ? (
                <form.Field name="customExpiresAt">
                  {(field) => (
                    <Input
                      error={errorText(field.state.meta.errors)}
                      label="Expiration date"
                      onBlur={field.handleBlur}
                      onChange={(e) => field.handleChange(e.target.value)}
                      type="datetime-local"
                      value={field.state.value}
                    />
                  )}
                </form.Field>
              ) : null
            }
          </form.Subscribe>
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
            <div className="flex justify-end gap-2">
              <Button onClick={testNewKey} size="lg" variant="secondary" disabled={testingKey}>
                {testingKey ? "Testing…" : "Test connection"}
              </Button>
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
    </Page.Shell>
  );
};
