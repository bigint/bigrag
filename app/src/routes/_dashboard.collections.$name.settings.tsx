import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { KeyRound, Trash2, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
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
import { ALL_FILE_TYPES, FILE_TYPE_CATEGORIES, getAllowedFileTypes } from "@/lib/file-types";
import type { Collection } from "@/types/rag-computer";

export const Route = createFileRoute("/_dashboard/collections/$name/settings")({
  component: () => <CollectionSettings />,
});

type SearchMode = "semantic" | "keyword" | "hybrid";

type CollectionSettingsDraftSetters = {
  readonly setAllowedTypes: (types: Set<string>) => void;
  readonly setDescription: (description: string) => void;
  readonly setRerankingEnabled: (enabled: boolean) => void;
  readonly setSearchMode: (mode: SearchMode) => void;
  readonly setTopK: (topK: number) => void;
};

const CollectionSettings = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeURIComponent(rawName);
  const navigate = useNavigate();
  const { data: collection } = useCollection(name);
  const update = useUpdateCollection(name);
  const truncate = useTruncateCollection(name);
  const remove = useDeleteCollection();

  const [description, setDescription] = useState("");
  const [topK, setTopK] = useState(10);
  const [searchMode, setSearchMode] = useState<SearchMode>("semantic");
  const [rerankingEnabled, setRerankingEnabled] = useState(false);
  const [embeddingKeyDraft, setEmbeddingKeyDraft] = useState("");
  const [allowedTypes, setAllowedTypes] = useState<Set<string>>(new Set(ALL_FILE_TYPES));
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [confirmTruncateOpen, setConfirmTruncateOpen] = useState(false);

  useCollectionSettingsDraft(collection, {
    setAllowedTypes,
    setDescription,
    setRerankingEnabled,
    setSearchMode,
    setTopK,
  });

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
      if (next.has(t)) {
        next.delete(t);
      } else {
        next.add(t);
      }
      return next;
    });
  };

  const toggleCategory = (types: string[]) => {
    const allSelected = types.every((t) => allowedTypes.has(t));
    setAllowedTypes((prev) => {
      const next = new Set(prev);
      for (const t of types) {
        if (allSelected) {
          next.delete(t);
        } else {
          next.add(t);
        }
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
  const noneSelected = allowedTypes.size === 0;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to="/collections/$name/documents"
          params={{ name }}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back to collection
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Retrieval defaults</CardTitle>
          <CardDescription>
            Update query defaults and reranking for this collection.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Textarea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="grid gap-4 sm:grid-cols-3">
            <Input
              label="Default top K"
              type="number"
              min={1}
              max={100}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            />
            <Select
              label="Search mode"
              value={searchMode}
              onChange={(v) => setSearchMode(v as typeof searchMode)}
              options={[
                { value: "semantic", label: "Semantic" },
                { value: "keyword", label: "Keyword" },
                { value: "hybrid", label: "Hybrid" },
              ]}
            />
            <Switch
              label="Reranking enabled"
              checked={rerankingEnabled}
              onCheckedChange={setRerankingEnabled}
            />
          </div>
          <div>
            <Button onClick={saveDefaults} disabled={update.isPending}>
              Save defaults
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-4" />
            Embedding key
          </CardTitle>
          <CardDescription>
            Replace the collection-specific embedding key without changing the model.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Input
            label="New API key"
            type="password"
            value={embeddingKeyDraft}
            onChange={(e) => setEmbeddingKeyDraft(e.target.value)}
            placeholder="sk-..."
          />
          <div>
            <Button
              onClick={saveEmbeddingKey}
              disabled={update.isPending || !embeddingKeyDraft.trim()}
            >
              Update embedding key
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Allowed file types</CardTitle>
          <CardDescription>
            Restrict uploads by extension. Leave all selected to allow the default ingest set.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => setAllowedTypes(new Set(ALL_FILE_TYPES))}
              disabled={allSelected}
            >
              Select all
            </Button>
            <Button
              variant="secondary"
              onClick={() => setAllowedTypes(new Set())}
              disabled={noneSelected}
            >
              Clear all
            </Button>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {Object.entries(FILE_TYPE_CATEGORIES).map(([category, types]) => {
              const allInCategory = types.every((t) => allowedTypes.has(t));
              return (
                <div key={category} className="rounded-md border border-border p-3">
                  <Checkbox
                    checked={allInCategory}
                    label={category}
                    onCheckedChange={() => toggleCategory(types)}
                  />
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {types.map((t) => (
                      <Checkbox
                        key={t}
                        checked={allowedTypes.has(t)}
                        label={`.${t}`}
                        onCheckedChange={() => toggleType(t)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div>
            <Button onClick={saveFileTypes} disabled={update.isPending}>
              Save file types
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <TriangleAlert className="size-4" />
            Danger zone
          </CardTitle>
          <CardDescription>Destructive actions cannot be undone.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setConfirmTruncateOpen(true)}>
            <Trash2 className="size-4" />
            Remove all documents
          </Button>
          <Button variant="destructive" onClick={() => setConfirmDeleteOpen(true)}>
            <Trash2 className="size-4" />
            Delete collection
          </Button>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmTruncateOpen}
        onClose={() => setConfirmTruncateOpen(false)}
        title="Remove all documents?"
        description="The collection stays, but all documents and vectors are removed."
        confirmLabel="Remove documents"
        loading={truncate.isPending}
        onConfirm={async () => {
          await truncate.mutateAsync();
          setConfirmTruncateOpen(false);
        }}
      />

      <ConfirmDialog
        open={confirmDeleteOpen}
        onClose={() => setConfirmDeleteOpen(false)}
        title={`Delete ${collection.name}?`}
        description="This permanently removes the collection, documents, and vectors."
        confirmLabel="Delete collection"
        variant="destructive"
        loading={remove.isPending}
        onConfirm={async () => {
          await remove.mutateAsync(collection.name);
          navigate({ to: "/collections", replace: true });
        }}
      />
    </div>
  );
};

const useCollectionSettingsDraft = (
  collection: Collection | undefined,
  {
    setAllowedTypes,
    setDescription,
    setRerankingEnabled,
    setSearchMode,
    setTopK,
  }: CollectionSettingsDraftSetters,
) => {
  useEffect(() => {
    if (!collection) return;
    setDescription(collection.description);
    setTopK(collection.default_top_k);
    setSearchMode(collection.default_search_mode);
    setRerankingEnabled(collection.reranking_enabled);
    const stored = getAllowedFileTypes(collection.metadata);
    setAllowedTypes(new Set(stored.length ? stored : ALL_FILE_TYPES));
  }, [collection, setAllowedTypes, setDescription, setRerankingEnabled, setSearchMode, setTopK]);
};
