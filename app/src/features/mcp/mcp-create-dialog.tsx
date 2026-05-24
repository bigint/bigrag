import { useForm, useStore } from "@tanstack/react-form";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import {
  defaultMcpCreateFormValues,
  MCP_UNSCOPED,
  mcpCreateBodyFromValues,
  mcpServerNameFromTitle,
  slugifyMcpServerName,
} from "@/features/mcp/mcp-form-state";
import { useCreateMcpServer } from "@/hooks/use-mcp-servers";
import { errorText, submitWith } from "@/lib/form";
import type { CreatedMcpServer } from "@/types/bigrag";

interface McpCreateDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (created: CreatedMcpServer) => void;
  collections: { name: string }[];
}

export const McpCreateDialog = ({
  open,
  onClose,
  onCreated,
  collections,
}: McpCreateDialogProps) => {
  const create = useCreateMcpServer();
  const [autoSlug, setAutoSlug] = useState(true);
  const form = useForm({
    defaultValues: defaultMcpCreateFormValues(),
    onSubmit: async ({ value }) => {
      try {
        const created = await create.mutateAsync(mcpCreateBodyFromValues(value));
        onClose();
        onCreated(created);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed");
      }
    },
  });
  const values = useStore(form.store, (state) => state.values);

  useEffect(() => {
    if (!open) {
      form.reset(defaultMcpCreateFormValues());
      setAutoSlug(true);
    }
  }, [form, open]);

  useEffect(() => {
    if (autoSlug) form.setFieldValue("serverName", mcpServerNameFromTitle(values.title));
  }, [autoSlug, form, values.title]);

  return (
    <Modal onClose={onClose} open={open} size="md" title="New MCP server">
      <form className="space-y-4" noValidate onSubmit={submitWith(() => form.handleSubmit())}>
        <form.Field
          name="title"
          validators={{
            onSubmit: ({ value }) => (value.trim() ? undefined : "Title is required"),
          }}
        >
          {(field) => (
            <Input
              autoFocus
              description="Shown in the admin UI; also the suggested Name in Claude."
              error={errorText(field.state.meta.errors)}
              label="Title"
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
              placeholder="Product docs"
              required
              value={field.state.value}
            />
          )}
        </form.Field>
        <form.Field
          name="serverName"
          validators={{
            onSubmit: ({ value }) => (value.trim() ? undefined : "Server name is required"),
          }}
        >
          {(field) => (
            <Input
              description="mcpServers key in the client config. Lowercase, alphanumeric + dashes."
              error={errorText(field.state.meta.errors)}
              label="Server name"
              onBlur={field.handleBlur}
              onChange={(e) => {
                setAutoSlug(false);
                field.handleChange(slugifyMcpServerName(e.target.value));
              }}
              placeholder="bigrag-product-docs"
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
                { value: MCP_UNSCOPED, label: "All collections (full workspace)" },
                ...collections.map((c) => ({ value: c.name, label: c.name })),
              ]}
              value={field.state.value}
            />
          )}
        </form.Field>
        <p className="text-xs text-muted-foreground">
          Creating this MCP mints a fresh bigRAG API key scoped to it. The full key is shown once —
          copy it into your MCP client immediately. You can rotate the key any time.
        </p>
        <div className="flex justify-end gap-2 pt-1">
          <Button onClick={onClose} type="button" variant="secondary">
            Cancel
          </Button>
          <Button disabled={create.isPending} type="submit">
            {create.isPending ? "Creating…" : "Create MCP"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
