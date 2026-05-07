import { createFileRoute, Link } from "@tanstack/react-router";
import { Search, Sparkles } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { useCollection } from "@/hooks/use-collections";
import { useRunQuery } from "@/hooks/use-query";

export const Route = createFileRoute("/_dashboard/collections/$name/search")({
  component: () => <SearchTab />,
});

const SearchTab = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeURIComponent(rawName);
  const { data: collection } = useCollection(name);
  const run = useRunQuery(name);

  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"semantic" | "keyword" | "hybrid">("semantic");
  const [topK, setTopK] = useState(5);
  const [rerank, setRerank] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    await run.mutateAsync({ query, top_k: topK, search_mode: mode, rerank });
  };

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent className="pt-5">
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Input
              placeholder="Ask a question of this collection…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              trailing={<Search className="h-4 w-4" />}
              autoFocus
            />
            <div className="flex flex-wrap items-end gap-3">
              <Select
                label="Mode"
                value={mode}
                onChange={(v) => setMode(v as typeof mode)}
                options={[
                  { value: "semantic", label: "Semantic" },
                  { value: "keyword", label: "Keyword" },
                  { value: "hybrid", label: "Hybrid" },
                ]}
                className="w-40"
              />
              <Input
                label="Top K"
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-24"
              />
              {collection?.reranking_enabled && (
                <div className="flex items-center gap-2 text-sm">
                  <Switch
                    checked={rerank}
                    onCheckedChange={setRerank}
                    aria-label="Rerank results"
                  />
                  <span>Rerank</span>
                </div>
              )}
              <div className="ml-auto">
                <Button type="submit" disabled={run.isPending || !query.trim()}>
                  {run.isPending ? (
                    <Spinner size="sm" />
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" /> Run query
                    </>
                  )}
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {run.data && run.data.results.length === 0 && (
        <Empty
          icon={<Search className="size-6" />}
          title="No results"
          description="Try a different query, mode, or raise min score."
        />
      )}

      {run.data && run.data.results.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">
            {run.data.total} result{run.data.total === 1 ? "" : "s"} for "{run.data.query}"
          </div>
          {run.data.results.map((r) => (
            <article key={r.id} className="rounded-xl border border-border bg-card p-4">
              <div className="mb-2 flex items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant="primary">score {r.score.toFixed(3)}</Badge>
                  {r.document_id && (
                    <Link
                      params={{ docId: r.document_id, name }}
                      to="/collections/$name/documents/$docId"
                      className="font-mono text-muted-foreground hover:text-primary"
                    >
                      {r.document_id.slice(0, 8)}#{r.chunk_index}
                    </Link>
                  )}
                </div>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{r.text}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
};
