import { useForm, useStore } from "@tanstack/react-form";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import {
  DEFAULT_MODELS,
  defaultPresetFormValues,
  embeddingModelOptions,
  PROVIDER_OPTIONS,
  type Provider,
  presetBodyFromValues,
  selectedEmbeddingDimension,
  validatePresetFormValues,
} from "@/features/models/preset-form-state";
import {
  type EmbeddingPresetBody,
  useCreateEmbeddingPreset,
  useUpdateEmbeddingPreset,
} from "@/hooks/use-embedding-presets";
import { useEmbeddingModels } from "@/hooks/use-platform";
import { errorText, firstString, submitWith } from "@/lib/form";
import type { EmbeddingPreset } from "@/types/bigrag";

interface Props {
  open: boolean;
  onClose: () => void;
  editing: EmbeddingPreset | null;
}

export const PresetForm = ({ open, onClose, editing }: Props) => {
  const isEdit = !!editing;
  const create = useCreateEmbeddingPreset();
  const update = useUpdateEmbeddingPreset();
  const { data: catalog } = useEmbeddingModels();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const form = useForm({
    defaultValues: defaultPresetFormValues(editing),
    validators: {
      onSubmit: ({ value }) => validatePresetFormValues(value, editing),
    },
    onSubmit: async ({ value }) => {
      setSubmitError(null);
      const dimension = selectedEmbeddingDimension({
        editing,
        model: value.model,
        models: catalog?.models,
        provider: value.provider,
      });
      const body = presetBodyFromValues(value, dimension);
      try {
        if (isEdit && editing) {
          await update.mutateAsync({ id: editing.id, ...body });
        } else {
          await create.mutateAsync(body as EmbeddingPresetBody);
        }
        onClose();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Something went wrong";
        setSubmitError(message);
        toast.error(message);
      }
    },
  });
  const values = useStore(form.store, (state) => state.values);

  useEffect(() => {
    if (!open) return;
    form.reset(defaultPresetFormValues(editing));
    setSubmitError(null);
  }, [editing, form, open]);

  const modelOptions = embeddingModelOptions(catalog?.models, values.provider);
  const selectedDimension = selectedEmbeddingDimension({
    editing,
    model: values.model,
    models: catalog?.models,
    provider: values.provider,
  });

  const isPending = create.isPending || update.isPending;

  return (
    <Modal onClose={onClose} open={open} title={isEdit ? "Edit preset" : "New embedding preset"}>
      <form
        className="space-y-4"
        noValidate
        onSubmit={submitWith(
          () => form.handleSubmit(),
          () => {
            setSubmitError(null);
          },
        )}
      >
        <form.Subscribe selector={(state) => state.errors}>
          {(errors) => {
            const formError = submitError ?? firstString(errors);
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
              description="A short label shown when creating collections — e.g. 'OpenAI small'."
              error={errorText(field.state.meta.errors)}
              label="Name"
              onBlur={field.handleBlur}
              onChange={(event) => field.handleChange(event.target.value)}
              placeholder="OpenAI small"
              required
              value={field.state.value}
            />
          )}
        </form.Field>
        <div className="space-y-4">
          <form.Field name="provider">
            {(field) => (
              <Select
                label="Provider"
                onChange={(value) => {
                  const provider = value as Provider;
                  field.handleChange(provider);
                  form.setFieldValue("model", DEFAULT_MODELS[provider].model);
                }}
                options={PROVIDER_OPTIONS}
                value={field.state.value}
              />
            )}
          </form.Field>
          <form.Field
            name="model"
            validators={{
              onSubmit: ({ value }) => (value.trim() ? undefined : "Model is required"),
            }}
          >
            {(field) => (
              <Select
                error={errorText(field.state.meta.errors)}
                label="Model"
                onChange={field.handleChange}
                options={
                  modelOptions.length > 0
                    ? modelOptions
                    : [{ value: field.state.value, label: field.state.value || "Loading…" }]
                }
                value={field.state.value}
              />
            )}
          </form.Field>
        </div>
        <form.Field
          name="apiKey"
          validators={{
            onSubmit: ({ value }) => (isEdit || value.trim() ? undefined : "API key is required"),
          }}
        >
          {(field) => (
            <Input
              description={
                isEdit
                  ? "Leave blank to keep the existing key."
                  : "Stored server-side; used whenever a collection references this preset."
              }
              error={errorText(field.state.meta.errors)}
              label="Provider API key"
              onBlur={field.handleBlur}
              onChange={(event) => field.handleChange(event.target.value)}
              placeholder={isEdit ? "••••••••" : "sk-..."}
              type="password"
              value={field.state.value}
            />
          )}
        </form.Field>
        <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2 text-xs">
          <span className="text-muted-foreground">Embedding dimension</span>
          <span className="font-mono tabular-nums">{selectedDimension}</span>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button onClick={onClose} type="button" variant="secondary">
            Cancel
          </Button>
          <Button type="submit" disabled={isPending}>
            {isPending
              ? isEdit
                ? "Saving…"
                : "Creating…"
              : isEdit
                ? "Save changes"
                : "Create preset"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
