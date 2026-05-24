import { useStore } from "@tanstack/react-form";
import { Link } from "@tanstack/react-router";
import { useEffect, useMemo } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Textarea } from "@/components/ui/textarea";
import {
  type CreateCollectionFormValues,
  createCollectionBodyFromValues,
  defaultCreateCollectionFormValues,
} from "@/features/collections/collection-form-state";
import { AdvancedSafeguards } from "@/features/collections/create-collection/advanced-safeguards";
import {
  DEFAULT_METADATA_SCHEMA,
  useCreateCollectionForm,
} from "@/features/collections/create-collection/create-collection-form";
import { EmbeddingPresetField } from "@/features/collections/create-collection/embedding-preset-field";
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
  const form = useCreateCollectionForm(async (value) => {
    try {
      await create.mutateAsync(createCollectionBodyFromValues(value));
      onClose();
      form.reset(defaultCreateCollectionFormValues());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create");
    }
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

  const toggleTenantGuard = (enabled: boolean) => {
    form.setFieldValue("tenantGuardEnabled", enabled);
    if (enabled && !values.tenantField.trim()) form.setFieldValue("tenantField", "tenant_id");
  };

  const toggleMetadataSchema = (enabled: boolean) => {
    form.setFieldValue("metadataSchemaEnabled", enabled);
    if (enabled && !values.metadataSchemaText.trim()) {
      form.setFieldValue("metadataSchemaText", DEFAULT_METADATA_SCHEMA);
    }
  };

  const toggleMultimodal = (enabled: boolean) => {
    form.setFieldValue("multimodalEnabled", enabled);
    if (!enabled) form.setFieldValue("multimodalEnrichmentEnabled", false);
  };

  const toggleMultimodalEnrichment = (enabled: boolean) => {
    form.setFieldValue("multimodalEnrichmentEnabled", enabled);
    if (enabled) form.setFieldValue("multimodalEnabled", true);
  };

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
        <EmbeddingPresetField
          error={presetsError}
          form={form}
          hasPresets={presets.length > 0}
          isError={presetsIsError}
          onRetry={() => refetchPresets()}
          options={options}
          pending={presetsPending}
        />
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
        <AdvancedSafeguards
          form={form}
          onToggleMetadataSchema={toggleMetadataSchema}
          onToggleMultimodal={toggleMultimodal}
          onToggleMultimodalEnrichment={toggleMultimodalEnrichment}
          onToggleTenantGuard={toggleTenantGuard}
          values={values}
        />
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
