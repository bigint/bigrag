import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import {
  type EmbeddingPresetBody,
  useCreateEmbeddingPreset,
  useUpdateEmbeddingPreset,
} from "@/hooks/use-embedding-presets";
import { useEmbeddingModels } from "@/hooks/use-platform";
import type { EmbeddingPreset } from "@/types/rag-computer";

interface Props {
  open: boolean;
  onClose: () => void;
  editing: EmbeddingPreset | null;
}

type Provider = "openai" | "cohere" | "voyage";

const DEFAULT_MODELS: Record<Provider, { model: string; dimension: number }> = {
  openai: { model: "text-embedding-3-small", dimension: 1536 },
  cohere: { model: "embed-english-v3.0", dimension: 1024 },
  voyage: { model: "voyage-3.5", dimension: 1024 },
};

export const PresetForm = ({ open, onClose, editing }: Props) => {
  const isEdit = !!editing;
  const create = useCreateEmbeddingPreset();
  const update = useUpdateEmbeddingPreset();
  const { data: catalog } = useEmbeddingModels();
  const {
    apiKey,
    error,
    model,
    name,
    provider,
    setApiKey,
    setError,
    setModel,
    setName,
    setProvider,
  } = usePresetFormDraft(open, editing);

  const modelOptions =
    catalog?.models
      .filter((m) => m.provider === provider)
      .map((m) => ({
        value: m.model,
        label: `${m.model} · ${m.dimension}d`,
      })) ?? [];

  const selectedDimension = useMemo(() => {
    const match = catalog?.models.find((m) => m.provider === provider && m.model === model);
    if (match) return match.dimension;
    if (editing && editing.model === model) return editing.dimension;
    return DEFAULT_MODELS[provider].dimension;
  }, [catalog, provider, model, editing]);

  const onSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) return setError("Name is required");
    if (!model.trim()) return setError("Model is required");
    if (!isEdit && !apiKey.trim()) return setError("API key is required");

    const body: Partial<EmbeddingPresetBody> = {
      name: name.trim(),
      provider,
      model: model.trim(),
      dimension: selectedDimension,
    };
    if (apiKey.trim()) body.api_key = apiKey.trim();

    try {
      if (isEdit && editing) {
        await update.mutateAsync({ id: editing.id, ...body });
      } else {
        await create.mutateAsync(body as EmbeddingPresetBody);
      }
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setError(message);
      toast.error(message);
    }
  };

  const isPending = create.isPending || update.isPending;

  return (
    <Modal onClose={onClose} open={open} title={isEdit ? "Edit preset" : "New embedding preset"}>
      <form className="space-y-4" onSubmit={onSubmit}>
        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        <Input
          label="Name"
          description="A short label shown when creating collections — e.g. 'OpenAI small'."
          autoFocus
          onChange={(e) => setName(e.target.value)}
          placeholder="OpenAI small"
          required
          value={name}
        />
        <div className="space-y-4">
          <Select
            label="Provider"
            value={provider}
            onChange={(v) => {
              const p = v as Provider;
              setProvider(p);
              setModel(DEFAULT_MODELS[p].model);
            }}
            options={[
              { value: "openai", label: "OpenAI" },
              { value: "cohere", label: "Cohere" },
              { value: "voyage", label: "Voyage AI" },
            ]}
          />
          <Select
            label="Model"
            value={model}
            onChange={setModel}
            options={
              modelOptions.length > 0
                ? modelOptions
                : [{ value: model, label: model || "Loading…" }]
            }
          />
        </div>
        <Input
          label="Provider API key"
          description={
            isEdit
              ? "Leave blank to keep the existing key."
              : "Stored server-side; used whenever a collection references this preset."
          }
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={isEdit ? "••••••••" : "sk-..."}
          type="password"
          value={apiKey}
        />
        <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2 text-xs">
          <span className="text-muted-foreground">Embedding dimension</span>
          <span className="font-mono tabular-nums">{selectedDimension}</span>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
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

const usePresetFormDraft = (open: boolean, editing: EmbeddingPreset | null) => {
  const [name, setName] = useState("");
  const [provider, setProvider] = useState<Provider>("openai");
  const [model, setModel] = useState("text-embedding-3-small");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (editing) {
      setName(editing.name);
      setProvider(editing.provider);
      setModel(editing.model);
      setApiKey("");
    } else {
      setName("");
      setProvider("openai");
      setModel(DEFAULT_MODELS.openai.model);
      setApiKey("");
    }
    setError(null);
  }, [editing, open]);

  return {
    apiKey,
    error,
    model,
    name,
    provider,
    setApiKey,
    setError,
    setModel,
    setName,
    setProvider,
  };
};
