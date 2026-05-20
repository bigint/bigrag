import { useForm, useStore } from "@tanstack/react-form";
import { Link } from "@tanstack/react-router";
import { ArrowRight, Cpu } from "lucide-react";
import { useEffect, useMemo } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  type CreateCollectionFormValues,
  createCollectionBodyFromValues,
  defaultCreateCollectionFormValues,
  validateCreateCollectionFormValues,
} from "@/features/collections/collection-form-state";
import { useCreateCollection } from "@/hooks/use-collections";
import { useEmbeddingPresets } from "@/hooks/use-embedding-presets";
import { errorText, firstString, submitWith } from "@/lib/form";

type Props = { open: boolean; onClose: () => void };
type ResettableCreateCollectionForm = {
  reset: (values: CreateCollectionFormValues) => void;
};

export const CreateCollectionModal = ({ open, onClose }: Props) => {
  const create = useCreateCollection();
  const {
    data: presetsData,
    error: presetsError,
    isError: presetsIsError,
    isPending: presetsPending,
    refetch: refetchPresets,
  } = useEmbeddingPresets();
  const form = useForm({
    defaultValues: defaultCreateCollectionFormValues(),
    validators: {
      onSubmit: ({ value }) => validateCreateCollectionFormValues(value),
    },
    onSubmit: async ({ value }) => {
      try {
        await create.mutateAsync(createCollectionBodyFromValues(value));
        onClose();
        form.reset(defaultCreateCollectionFormValues());
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to create");
      }
    },
  });
  const values = useStore(form.store, (state) => state.values);

  const presets = presetsData?.presets ?? [];
  const options = useMemo(
    () => [
      { value: "", label: presets.length ? "Select a preset…" : "No presets available" },
      ...presets.map((p) => ({
        value: p.id,
        label: `${p.name} — ${p.provider}/${p.model}`,
      })),
    ],
    [presets],
  );

  useDefaultEmbeddingPreset(open, presets, values.presetId, (presetId) =>
    form.setFieldValue("presetId", presetId),
  );
  useResetCreateCollectionForm(open, form, create.reset);

  return (
    <Modal onClose={onClose} open={open} title="New collection">
      <p className="mb-4 text-sm text-muted-foreground">
        Collections share a preset's provider, model, and API key. Manage presets on the{" "}
        <Link className="font-medium text-foreground underline" to="/models">
          Models
        </Link>{" "}
        page.
      </p>
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
            onSubmit: ({ value }) => {
              const trimmed = value.trim();
              if (!trimmed) return "Name is required";
              return /^[a-zA-Z][a-zA-Z0-9_]*$/.test(trimmed)
                ? undefined
                : "Start with a letter. Use letters, numbers, and underscores.";
            },
          }}
        >
          {(field) => (
            <Input
              autoFocus
              description="Start with a letter. Use letters, numbers, and underscores."
              error={errorText(field.state.meta.errors)}
              label="Name"
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
              placeholder="product_docs"
              required
              value={field.state.value}
            />
          )}
        </form.Field>
        <form.Field name="description">
          {(field) => (
            <Textarea
              label="Description"
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
              placeholder="Optional"
              value={field.state.value}
            />
          )}
        </form.Field>
        <form.Field name="vectorStoreProvider">
          {(field) => (
            <Select
              label="Vector storage"
              onChange={(value) =>
                field.handleChange(value === "turbopuffer" ? "turbopuffer" : "qdrant")
              }
              options={VECTOR_STORAGE_OPTIONS}
              value={field.state.value}
            />
          )}
        </form.Field>
        {presetsPending ? (
          <div className="flex items-center gap-3 rounded-md border border-border bg-muted/50 px-3 py-3 text-sm text-muted-foreground">
            <Spinner size="sm" />
            Loading embedding presets...
          </div>
        ) : presetsIsError ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-3 text-sm text-destructive">
            <div>
              {presetsError instanceof Error ? presetsError.message : "Failed to load presets"}
            </div>
            <Button
              className="mt-2"
              onClick={() => refetchPresets()}
              size="sm"
              type="button"
              variant="secondary"
            >
              Retry
            </Button>
          </div>
        ) : presets.length === 0 ? (
          <div className="flex items-start gap-3 rounded-md border border-border bg-muted/50 px-3 py-3 text-sm">
            <Cpu className="mt-0.5 size-4 text-muted-foreground" />
            <div className="flex-1">
              <div className="font-medium">No embedding presets yet</div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Create one to set provider, model, and API key once.
              </p>
            </div>
            <Link
              to="/models"
              className="inline-flex items-center gap-1 text-xs font-medium text-foreground"
            >
              Go to Models <ArrowRight className="size-3" />
            </Link>
          </div>
        ) : (
          <form.Field
            name="presetId"
            validators={{
              onSubmit: ({ value }) => (value ? undefined : "Pick an embedding preset first"),
            }}
          >
            {(field) => (
              <Select
                description="Provider, model, and API key are inherited from the selected preset."
                error={errorText(field.state.meta.errors)}
                label="Embedding preset"
                onChange={field.handleChange}
                options={options}
                value={field.state.value}
              />
            )}
          </form.Field>
        )}
        <div className="space-y-4">
          <form.Field
            name="chunkSize"
            validators={{
              onSubmit: ({ value }) =>
                value < 64 || value > 10000 ? "Chunk size must be between 64 and 10000" : undefined,
            }}
          >
            {(field) => (
              <Input
                error={errorText(field.state.meta.errors)}
                label="Chunk size"
                max={10000}
                min={64}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(Number(e.target.value))}
                type="number"
                value={field.state.value}
              />
            )}
          </form.Field>
          <form.Field
            name="chunkOverlap"
            validators={{
              onSubmit: ({ value }) =>
                value < 0 || value > 5000 ? "Chunk overlap must be between 0 and 5000" : undefined,
            }}
          >
            {(field) => (
              <Input
                error={errorText(field.state.meta.errors)}
                label="Chunk overlap"
                max={5000}
                min={0}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(Number(e.target.value))}
                type="number"
                value={field.state.value}
              />
            )}
          </form.Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <form.Field
            name="tenantField"
            validators={{
              onSubmit: ({ value }) =>
                value.trim().length > 64
                  ? "Tenant field must be 64 characters or fewer"
                  : undefined,
            }}
          >
            {(field) => (
              <Input
                description="Optional metadata key required on uploads and queries."
                error={errorText(field.state.meta.errors)}
                label="Tenant field"
                maxLength={64}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                placeholder="tenant_id"
                value={field.state.value}
              />
            )}
          </form.Field>
          <form.Field name="metadataSchemaText">
            {(field) => (
              <Textarea
                className="min-h-10"
                label="Metadata schema"
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                placeholder='{"type":"object"}'
                value={field.state.value}
              />
            )}
          </form.Field>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending || !values.presetId}>
            {create.isPending ? "Creating…" : "Create collection"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};

const VECTOR_STORAGE_OPTIONS = [
  { value: "qdrant", label: "Qdrant" },
  { value: "turbopuffer", label: "Turbopuffer" },
] as const;

const useDefaultEmbeddingPreset = (
  open: boolean,
  presets: readonly { id: string }[],
  presetId: string,
  setPresetId: (presetId: string) => void,
) => {
  useEffect(() => {
    const first = presets[0];
    if (open && first && !presetId) setPresetId(first.id);
  }, [open, presets, presetId, setPresetId]);
};

const useResetCreateCollectionForm = (
  open: boolean,
  form: ResettableCreateCollectionForm,
  resetMutation: () => void,
) => {
  useEffect(() => {
    if (!open) {
      form.reset(defaultCreateCollectionFormValues());
      resetMutation();
    }
  }, [form, open, resetMutation]);
};
