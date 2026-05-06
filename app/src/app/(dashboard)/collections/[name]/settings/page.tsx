"use client";

import { KeyRound, Trash2, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  useCollection,
  useDeleteCollection,
  useTruncateCollection,
  useUpdateCollection,
} from "@/hooks/use-collections";
import { useEmbeddingPresets } from "@/hooks/use-embedding-presets";
import { ALL_FILE_TYPES, FILE_TYPE_CATEGORIES, getAllowedFileTypes } from "@/lib/file-types";

const CollectionSettings = ({ params }: { params: Promise<{ name: string }> }) => {
  const { name: rawName } = use(params);
  const name = decodeURIComponent(rawName);
  const router = useRouter();
  const { data: collection } = useCollection(name);
  const presetsQuery = useEmbeddingPresets();
  const update = useUpdateCollection(name);
  const truncate = useTruncateCollection(name);
  const remove = useDeleteCollection();

  const [description, setDescription] = useState("");
  const [topK, setTopK] = useState(10);
  const [searchMode, setSearchMode] = useState<"semantic" | "keyword" | "hybrid">("semantic");
  const [rerankingEnabled, setRerankingEnabled] = useState(false);
  const [embeddingKeyDraft, setEmbeddingKeyDraft] = useState("");
  const [allowedTypes, setAllowedTypes] = useState<Set<string>>(new Set(ALL_FILE_TYPES));
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [confirmTruncateOpen, setConfirmTruncateOpen] = useState(false);

  useEffect(() => {
    if (!collection) return;
    setDescription(collection.description);
    setTopK(collection.default_top_k);
    setSearchMode(collection.default_search_mode);
    setRerankingEnabled(collection.reranking_enabled);
    const stored = getAllowedFileTypes(collection.metadata);
    setAllowedTypes(new Set(stored.length ? stored : ALL_FILE_TYPES));
  }, [collection]);

  if (!collection) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  const toggleType = (t: string) => {
    setAllowedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const toggleCategory = (types: string[]) => {
    const allSelected = types.every((t) => allowedTypes.has(t));
    setAllowedTypes((prev) => {
      const next = new Set(prev);
      for (const t of types) {
        if (allSelected) next.delete(t);
        else next.add(t);
      }
      return next;
    });
  };

  const saveDefaults = async () => {
    try {
      await update.mutateAsync({
        description,
        default_top_k: topK,
        default_search_mode: searchMode,
        reranking_enabled: rerankingEnabled,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  };

  const saveEmbeddingKey = async () => {
    const trimmed = embeddingKeyDraft.trim();
    if (!trimmed) return;
    try {
      await update.mutateAsync({ embedding_api_key: trimmed });
      setEmbeddingKeyDraft("");
      toast.success("Embedding API key updated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  };

  const saveFileTypes = async () => {
    const list = Array.from(allowedTypes).sort();
    const unrestricted = list.length === ALL_FILE_TYPES.length;
    try {
      await update.mutateAsync({
        metadata: {
          ...(collection.metadata ?? {}),
          allowed_file_types: unrestricted ? [] : list,
        },
      });
      toast.success(
        unrestricted
          ? "All file types allowed"
          : `Restricted to ${list.length} type${list.length === 1 ? "" : "s"}`,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  };

  const allSelected = allowedTypes.size === ALL_FILE_TYPES.length;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Defaults</CardTitle>
          <CardDescription>
            Applied to queries when they don't specify their own values.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="space-y-4">
            <Input
              label="Default top K"
              type="number"
              min={1}
              max={1000}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            />
            <Select
              label="Default search mode"
              value={searchMode}
              onChange={(v) => setSearchMode(v as typeof searchMode)}
              options={[
                { value: "semantic", label: "Semantic" },
                { value: "keyword", label: "Keyword" },
                { value: "hybrid", label: "Hybrid" },
              ]}
            />
          </div>
          <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-muted/40 p-3">
            <div>
              <div className="text-sm font-medium">Rerank results</div>
              <p className="text-xs text-muted-foreground">
                Requires a Cohere rerank key on the collection.
              </p>
            </div>
            <Switch
              checked={rerankingEnabled}
              onCheckedChange={setRerankingEnabled}
              aria-label="Rerank results"
            />
          </div>
          <div className="flex justify-end">
            <Button onClick={saveDefaults} disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-4" />
            Embedding API key
          </CardTitle>
          <CardDescription>
            {collection.embedding_preset_id ? (
              <>
                Inherits from preset{" "}
                <strong>
                  {presetsQuery.data?.presets.find((p) => p.id === collection.embedding_preset_id)
                    ?.name ?? "(loading…)"}
                </strong>
                . Update the key on the preset and every linked collection picks it up
                automatically. Saving a key below switches this collection to a per-collection
                override.
              </>
            ) : (
              <>
                Used to embed query text and ingested chunks. Updates here are validated against{" "}
                {collection.embedding_provider} before saving.{" "}
                <strong>
                  {collection.has_api_key ? "A key is currently saved." : "No key is saved."}
                </strong>
              </>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {collection.embedding_preset_id && (
            <div className="flex justify-end">
              <Link href="/models">
                <Button size="sm" variant="outline">
                  Manage preset
                </Button>
              </Link>
            </div>
          )}
          <Input
            label={
              collection.embedding_preset_id
                ? `Override with a per-collection ${collection.embedding_provider} key`
                : `New ${collection.embedding_provider} API key`
            }
            type="password"
            autoComplete="off"
            placeholder={collection.has_api_key ? "Paste a replacement key" : "sk-..."}
            value={embeddingKeyDraft}
            onChange={(e) => setEmbeddingKeyDraft(e.target.value)}
          />
          <div className="flex justify-end">
            <Button
              onClick={saveEmbeddingKey}
              disabled={update.isPending || !embeddingKeyDraft.trim()}
            >
              {update.isPending ? "Validating…" : "Save key"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Allowed file types</CardTitle>
          <CardDescription>
            Only files whose extension is checked below can be uploaded to this collection.{" "}
            <strong>
              {allSelected
                ? "All types are allowed."
                : `${allowedTypes.size} of ${ALL_FILE_TYPES.length} types allowed.`}
            </strong>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-4 rounded-md border border-border p-3">
            {Object.entries(FILE_TYPE_CATEGORIES).map(([category, types]) => {
              const allInCategory = types.every((t) => allowedTypes.has(t));
              const someInCategory = !allInCategory && types.some((t) => allowedTypes.has(t));
              return (
                <div key={category}>
                  <Checkbox
                    aria-label={`Select all ${category}`}
                    checked={allInCategory}
                    className="text-sm font-medium"
                    indeterminate={someInCategory}
                    label={category}
                    onCheckedChange={() => toggleCategory(types)}
                  />
                  <div className="ml-6 mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {types.map((t) => (
                      <Checkbox
                        key={t}
                        checked={allowedTypes.has(t)}
                        className="text-sm text-muted-foreground"
                        label={`.${t}`}
                        onCheckedChange={() => toggleType(t)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex items-center justify-between gap-2">
            <div className="flex gap-2">
              <Button
                onClick={() => setAllowedTypes(new Set(ALL_FILE_TYPES))}
                size="sm"
                variant="ghost"
                disabled={allSelected}
              >
                Allow all
              </Button>
              <Button
                onClick={() => setAllowedTypes(new Set())}
                size="sm"
                variant="ghost"
                disabled={allowedTypes.size === 0}
              >
                Clear
              </Button>
            </div>
            <Button onClick={saveFileTypes} disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save file types"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TriangleAlert className="size-4 text-destructive" />
            Danger zone
          </CardTitle>
          <CardDescription>Irreversible operations.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between gap-3 rounded-md border border-border p-3">
            <div>
              <div className="text-sm font-medium">Truncate</div>
              <p className="text-xs text-muted-foreground">
                Delete every document and vector. The collection stays.
              </p>
            </div>
            <Button variant="outline" onClick={() => setConfirmTruncateOpen(true)}>
              Truncate
            </Button>
          </div>
          <div className="flex items-center justify-between gap-3 rounded-md border border-destructive/50 p-3">
            <div>
              <div className="text-sm font-medium">Delete collection</div>
              <p className="text-xs text-muted-foreground">
                Permanently removes the collection, its documents, and its vectors.
              </p>
            </div>
            <Button variant="destructive" onClick={() => setConfirmDeleteOpen(true)}>
              <Trash2 className="size-4" /> Delete
            </Button>
          </div>
        </CardContent>
      </Card>

      <ConfirmDialog
        confirmLabel="Truncate"
        description={`Delete all documents in "${name}"? Vectors are removed; the collection itself stays.`}
        loading={truncate.isPending}
        onClose={() => setConfirmTruncateOpen(false)}
        onConfirm={async () => {
          await truncate.mutateAsync();
          setConfirmTruncateOpen(false);
        }}
        open={confirmTruncateOpen}
        title="Truncate collection"
      />

      <ConfirmDialog
        confirmLabel="Delete forever"
        description={`Permanently delete "${name}" and every document + vector inside? This cannot be undone.`}
        loading={remove.isPending}
        onClose={() => setConfirmDeleteOpen(false)}
        onConfirm={async () => {
          await remove.mutateAsync(name);
          router.replace("/collections");
        }}
        open={confirmDeleteOpen}
        title="Delete collection"
      />
    </div>
  );
};

export default CollectionSettings;
