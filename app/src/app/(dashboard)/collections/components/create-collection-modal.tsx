"use client";

import { ArrowRight, Cpu } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateCollection } from "@/hooks/use-collections";
import { useEmbeddingPresets } from "@/hooks/use-embedding-presets";

type Props = { open: boolean; onClose: () => void };

const slugify = (v: string) =>
  v
    .toLowerCase()
    .replace(/[^a-z0-9_\- ]+/g, "")
    .replace(/\s+/g, "_")
    .slice(0, 48);

export const CreateCollectionModal = ({ open, onClose }: Props) => {
  const create = useCreateCollection();
  const { data: presetsData } = useEmbeddingPresets();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [presetId, setPresetId] = useState<string>("");
  const [chunkSize, setChunkSize] = useState(512);
  const [chunkOverlap, setChunkOverlap] = useState(50);

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

  useEffect(() => {
    const first = presets[0];
    if (open && first && !presetId) setPresetId(first.id);
  }, [open, presets, presetId]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!presetId) {
      toast.error("Pick an embedding preset first");
      return;
    }
    try {
      await create.mutateAsync({
        name: slugify(name),
        description,
        embedding_preset_id: presetId,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
      });
      onClose();
      setName("");
      setDescription("");
      setPresetId("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create");
    }
  };

  return (
    <Modal onClose={onClose} open={open} title="New collection">
      <p className="mb-4 text-sm text-muted-foreground">
        Collections share a preset's provider, model, and API key. Manage presets on the{" "}
        <Link className="font-medium text-foreground underline" href="/models">
          Models
        </Link>{" "}
        page.
      </p>
      <form onSubmit={submit} className="space-y-4">
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
              href="/models"
              className="inline-flex items-center gap-1 text-xs font-medium text-foreground"
            >
              Go to Models <ArrowRight className="size-3" />
            </Link>
          </div>
        ) : (
          <Select
            label="Embedding preset"
            value={presetId}
            onChange={setPresetId}
            options={options}
          />
        )}
        <div className="grid grid-cols-2 gap-3">
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
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending || !presetId}>
            {create.isPending ? "Creating…" : "Create collection"}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
