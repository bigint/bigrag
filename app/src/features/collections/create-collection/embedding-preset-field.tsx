import { Link } from "@tanstack/react-router";
import { ArrowRight, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import type { CreateCollectionForm } from "@/features/collections/create-collection/create-collection-form";
import { errorText } from "@/lib/form";

export const EmbeddingPresetField = ({
  form,
  options,
  pending,
  isError,
  error,
  onRetry,
  hasPresets,
}: {
  form: CreateCollectionForm;
  options: { value: string; label: string }[];
  pending: boolean;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  hasPresets: boolean;
}) => {
  if (pending) {
    return (
      <div className="flex items-center gap-3 rounded-md border border-border bg-muted/50 px-3 py-3 text-sm text-muted-foreground">
        <Spinner size="sm" />
        Loading embedding presets...
      </div>
    );
  }
  if (isError) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-3 text-sm text-destructive">
        <div>{error instanceof Error ? error.message : "Failed to load presets"}</div>
        <Button className="mt-2" onClick={onRetry} size="sm" type="button" variant="secondary">
          Retry
        </Button>
      </div>
    );
  }
  if (!hasPresets) {
    return (
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
    );
  }
  return (
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
  );
};
