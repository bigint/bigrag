"use client";

import { Trash2, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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

const CollectionSettings = ({ params }: { params: Promise<{ name: string }> }) => {
  const { name: rawName } = use(params);
  const name = decodeURIComponent(rawName);
  const router = useRouter();
  const { data: collection } = useCollection(name);
  const update = useUpdateCollection(name);
  const truncate = useTruncateCollection(name);
  const remove = useDeleteCollection();

  const [description, setDescription] = useState("");
  const [topK, setTopK] = useState(10);
  const [searchMode, setSearchMode] = useState<"semantic" | "keyword" | "hybrid">("semantic");
  const [rerankingEnabled, setRerankingEnabled] = useState(false);

  useEffect(() => {
    if (!collection) return;
    setDescription(collection.description);
    setTopK(collection.default_top_k);
    setSearchMode(collection.default_search_mode);
    setRerankingEnabled(collection.reranking_enabled);
  }, [collection]);

  if (!collection) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  const save = async () => {
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

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Defaults</CardTitle>
          <CardDescription>
            Applied to queries when they don't specify their own values.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Textarea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3">
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
              onChange={(e) => setSearchMode(e.target.value as typeof searchMode)}
              options={[
                { value: "semantic", label: "Semantic" },
                { value: "keyword", label: "Keyword" },
                { value: "hybrid", label: "Hybrid" },
              ]}
            />
          </div>
          <label className="flex items-center justify-between gap-3 rounded-md border border-[var(--color-border)] bg-[var(--color-muted)]/40 p-3">
            <div>
              <div className="font-medium text-sm">Rerank results</div>
              <p className="text-xs text-[var(--color-muted-foreground)]">
                Requires a Cohere rerank key on the collection.
              </p>
            </div>
            <Switch checked={rerankingEnabled} onCheckedChange={setRerankingEnabled} />
          </label>
          <div className="flex justify-end">
            <Button onClick={save} disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-[var(--color-destructive)]/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TriangleAlert className="h-4 w-4 text-[var(--color-destructive)]" />
            Danger zone
          </CardTitle>
          <CardDescription>Irreversible operations.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3 rounded-md border border-[var(--color-border)] p-3">
            <div>
              <div className="font-medium text-sm">Truncate</div>
              <p className="text-xs text-[var(--color-muted-foreground)]">
                Delete every document and vector. The collection stays.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={async () => {
                if (!confirm(`Truncate all documents in "${name}"?`)) return;
                await truncate.mutateAsync();
              }}
            >
              Truncate
            </Button>
          </div>
          <div className="flex items-center justify-between gap-3 rounded-md border border-[var(--color-destructive)]/50 p-3">
            <div>
              <div className="font-medium text-sm">Delete collection</div>
              <p className="text-xs text-[var(--color-muted-foreground)]">
                Permanently removes the collection, its documents, and its vectors.
              </p>
            </div>
            <Button
              variant="destructive"
              onClick={async () => {
                const input = prompt(`Type the collection name "${name}" to confirm:`);
                if (input !== name) return;
                await remove.mutateAsync(name);
                router.replace("/collections");
              }}
            >
              <Trash2 className="h-4 w-4" /> Delete
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default CollectionSettings;
