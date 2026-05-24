import { useForm } from "@tanstack/react-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  API_KEY_UNSCOPED,
  type ApiKeyFormValues,
  apiKeyBodyFromValues,
  defaultApiKeyFormValues,
  validateApiKeyFormValues,
} from "@/features/api-keys/api-key-form-state";
import { errorText, firstString, submitWith } from "@/lib/form";

interface CreateApiKeyModalProps {
  open: boolean;
  onClose: () => void;
  collections: { name: string }[];
  creating: boolean;
  onSubmit: (body: ReturnType<typeof apiKeyBodyFromValues>) => Promise<void>;
}

export const CreateApiKeyModal = ({
  open,
  onClose,
  collections,
  creating,
  onSubmit,
}: CreateApiKeyModalProps) => {
  const form = useForm({
    defaultValues: defaultApiKeyFormValues(),
    validators: {
      onSubmit: ({ value }: { value: ApiKeyFormValues }) => validateApiKeyFormValues(value),
    },
    onSubmit: async ({ value }) => {
      await onSubmit(apiKeyBodyFromValues(value));
      form.reset(defaultApiKeyFormValues());
    },
  });

  return (
    <Modal onClose={onClose} open={open} title="New API key">
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
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={creating}>
            {creating ? "Creating…" : "Create key"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
