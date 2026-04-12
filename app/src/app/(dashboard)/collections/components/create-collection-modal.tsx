"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateCollection } from "@/hooks/use-collections";
import { useEmbeddingModels } from "@/hooks/use-platform";

type Props = { open: boolean; onOpenChange: (open: boolean) => void };

const slugify = (v: string) =>
  v
    .toLowerCase()
    .replace(/[^a-z0-9_\- ]+/g, "")
    .replace(/\s+/g, "_")
    .slice(0, 48);

export const CreateCollectionModal = ({ open, onOpenChange }: Props) => {
  const create = useCreateCollection();
  const { data: models } = useEmbeddingModels();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [provider, setProvider] = useState<"openai" | "cohere">("openai");
  const [model, setModel] = useState("text-embedding-3-small");
  const [apiKey, setApiKey] = useState("");
  const [dimension, setDimension] = useState(1536);
  const [chunkSize, setChunkSize] = useState(512);
  const [chunkOverlap, setChunkOverlap] = useState(50);

  useEffect(() => {
    if (!models) return;
    const match = models.models.find((m) => m.provider === provider && m.model === model);
    if (match) setDimension(match.dimension);
  }, [model, provider, models]);

  const modelOptions =
    models?.models
      .filter((m) => m.provider === provider)
      .map((m) => ({ value: m.model, label: `${m.model} (${m.dimension}d)` })) ?? [];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await create.mutateAsync({
        name: slugify(name),
        description,
        embedding_provider: provider,
        embedding_model: model,
        embedding_api_key: apiKey,
        dimension,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
      });
      onOpenChange(false);
      setName("");
      setDescription("");
      setApiKey("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="New collection"
        description="Collections isolate vectors, chunking, and embedding config."
      >
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Input
            label="Name"
            placeholder="product-docs"
            value={name}
            onChange={(e) => setName(e.target.value)}
            description="Lowercase letters, numbers, dashes and underscores."
            required
            autoFocus
          />
          <Textarea
            label="Description"
            placeholder="Optional"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Embedding provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value as "openai" | "cohere")}
              options={[
                { value: "openai", label: "OpenAI" },
                { value: "cohere", label: "Cohere" },
              ]}
            />
            <Select
              label="Model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              options={
                modelOptions.length
                  ? modelOptions
                  : [{ value: model, label: `${model} (loading…)` }]
              }
            />
          </div>
          <Input
            label="Provider API key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            description="Stored encrypted on the server. Used to embed documents in this collection."
            required
          />
          <div className="grid grid-cols-3 gap-3">
            <Input
              label="Dimension"
              type="number"
              min={64}
              max={4096}
              value={dimension}
              onChange={(e) => setDimension(Number(e.target.value))}
            />
            <Input
              label="Chunk size"
              type="number"
              min={128}
              max={10000}
              value={chunkSize}
              onChange={(e) => setChunkSize(Number(e.target.value))}
            />
            <Input
              label="Chunk overlap"
              type="number"
              min={0}
              max={5000}
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(Number(e.target.value))}
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <DialogClose render={<Button variant="ghost" type="button">Cancel</Button>} />
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create collection"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
