import { useForm, useStore } from "@tanstack/react-form";
import { Link } from "@tanstack/react-router";
import { ArrowRight, Cpu } from "lucide-react";
import { useEffect, useMemo } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  createCollectionBodyFromValues,
  defaultCreateCollectionFormValues,
  validateCreateCollectionFormValues,
} from "@/features/collections/collection-form-state";
import { useCreateCollection } from "@/hooks/use-collections";
import { useEmbeddingPresets } from "@/hooks/use-embedding-presets";
import { errorText, firstString, submitWith } from "@/lib/form";

type Props = { open: boolean; onClose: () => void };

export const CreateCollectionModal = ({ open, onClose }: Props) => {
  const create = useCreateCollection();
  const { data: presetsData } = useEmbeddingPresets();
  const form = useForm({
    defaultValues: defaultCreateCollectionFormValues(),
    validators: {
      onSubmit: ({ value }) => validateCreateCollectionFormValues(value),
    },
    onSubmit: async ({ value }) => {
      try {
        await create.mutateAsync(createCollectionBodyFromValues(value));
        onClose();
        form.setFieldValue("name", "");
        form.setFieldValue("description", "");
        form.setFieldValue("presetId", "");
        form.setFieldValue("vectorStoreProvider", "qdrant");
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
            onSubmit: ({ value }) => (value ? undefined : "Name is required"),
          }}
        >
          {(field) => (
            <Input
              autoFocus
              description="Lowercase letters, numbers, dashes and underscores."
              error={errorText(field.state.meta.errors)}
              label="Name"
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
              placeholder="product-docs"
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
        {presets.length === 0 ? (
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
                value < 128 || value > 10000
                  ? "Chunk size must be between 128 and 10000"
                  : undefined,
            }}
          >
            {(field) => (
              <Input
                error={errorText(field.state.meta.errors)}
                label="Chunk size"
                max={10000}
                min={128}
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
  { value: "turbopuffer", label: "turbopuffer" },
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
