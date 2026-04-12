"use client";

import { useEffect, useState } from "react";
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
import type { EmbeddingPreset } from "@/types/bigrag";

interface Props {
  open: boolean;
  onClose: () => void;
  editing: EmbeddingPreset | null;
}

const DEFAULT_MODELS: Record<"openai" | "cohere", { model: string; dimension: number }> = {
  openai: { model: "text-embedding-3-small", dimension: 1536 },
  cohere: { model: "embed-english-v3.0", dimension: 1024 },
};

export const PresetForm = ({ open, onClose, editing }: Props) => {
  const isEdit = !!editing;
  const create = useCreateEmbeddingPreset();
  const update = useUpdateEmbeddingPreset();
  const { data: catalog } = useEmbeddingModels();

  const [name, setName] = useState("");
  const [provider, setProvider] = useState<"openai" | "cohere">("openai");
  const [model, setModel] = useState("text-embedding-3-small");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [dimension, setDimension] = useState(1536);
  const [error, setError] = useState<string | null>(null);

  // Hydrate when editing; reset on close. `open` is intentional — we want to
  // reset form state every time the modal (re)opens, even for the same preset.
  // biome-ignore lint/correctness/useExhaustiveDependencies: open triggers reset
  useEffect(() => {
    if (editing) {
      setName(editing.name);
      setProvider(editing.provider);
      setModel(editing.model);
      setBaseUrl(editing.base_url ?? "");
      setDimension(editing.dimension);
      setApiKey("");
    } else {
      setName("");
      setProvider("openai");
      setModel(DEFAULT_MODELS.openai.model);
      setApiKey("");
      setBaseUrl("");
      setDimension(DEFAULT_MODELS.openai.dimension);
    }
    setError(null);
  }, [editing, open]);

  // When the chosen model is in the catalog, snap dimension to its canonical value.
  useEffect(() => {
    if (!catalog) return;
    const match = catalog.models.find((m) => m.provider === provider && m.model === model);
    if (match) setDimension(match.dimension);
  }, [catalog, provider, model]);

  const modelOptions =
    catalog?.models
      .filter((m) => m.provider === provider)
      .map((m) => ({
        value: m.model,
        label: `${m.model} · ${m.dimension}d`,
      })) ?? [];

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
      base_url: baseUrl.trim() || null,
      dimension,
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
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Provider"
            value={provider}
            onChange={(v) => {
              const p = v as "openai" | "cohere";
              setProvider(p);
              setModel(DEFAULT_MODELS[p].model);
              setDimension(DEFAULT_MODELS[p].dimension);
            }}
            options={[
              { value: "openai", label: "OpenAI" },
              { value: "cohere", label: "Cohere" },
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
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Dimension"
            description="Must match what the model emits."
            min={64}
            max={4096}
            onChange={(e) => setDimension(Number(e.target.value))}
            type="number"
            value={dimension}
          />
          <Input
            label="Base URL (optional)"
            description="For self-hosted/proxied providers."
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.openai.com/v1"
            type="url"
            value={baseUrl}
          />
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
