"use client";

import { Search, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useCollections } from "@/hooks/use-collections";
import { useRunMultiQuery } from "@/hooks/use-query";
import { cn } from "@/lib/cn";

const PlaygroundPage = () => {
  const { data } = useCollections();
  const run = useRunMultiQuery();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"semantic" | "keyword" | "hybrid">("semantic");
  const [topK, setTopK] = useState(5);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const collections = useMemo(() => data?.collections ?? [], [data]);
  const toggle = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || selected.size === 0) return;
    await run.mutateAsync({
      query,
      collections: Array.from(selected),
      top_k: topK,
      search_mode: mode,
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Playground"
        description="Run a single query across one or many collections — compare retrieval quality side by side."
      />

      <Card>
        <CardContent className="pt-5">
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Input
              placeholder="Ask a question…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              trailing={<Search className="h-4 w-4" />}
            />
            <div>
              <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Collections ({selected.size} selected)
              </div>
              {collections.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No collections yet. Create one first.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {collections.map((c) => {
                    const active = selected.has(c.name);
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => toggle(c.name)}
                        className={cn(
                          "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                          active
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-card text-foreground hover:bg-accent",
                        )}
                      >
                        {c.name}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <Select
                label="Mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as typeof mode)}
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
              <div className="ml-auto">
                <Button
                  type="submit"
                  disabled={run.isPending || !query.trim() || selected.size === 0}
                >
                  {run.isPending ? (
                    <Spinner size="sm" />
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" /> Query
                    </>
                  )}
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {run.data && run.data.total === 0 && <Empty title="No results" />}

      {run.data && run.data.total > 0 && (
        <div className="grid gap-3 md:grid-cols-2">
          {run.data.results.map((group) => (
            <Card key={group.collection}>
              <CardContent className="pt-5">
                <div className="mb-3 flex items-center justify-between">
                  <Link
                    href={`/collections/${encodeURIComponent(group.collection)}`}
                    className="font-semibold text-sm hover:text-primary"
                  >
                    {group.collection}
                  </Link>
                  <Badge variant="neutral">{group.chunks.length}</Badge>
                </div>
                {group.chunks.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No matches.</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {group.chunks.map((c, i) => (
                      <motion.li
                        key={c.id}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.02, duration: 0.18 }}
                        className="rounded-md border border-border p-3"
                      >
                        <div className="mb-1 flex items-center gap-2 text-xs">
                          <Badge variant="accent">{c.score.toFixed(3)}</Badge>
                        </div>
                        <p className="line-clamp-5 text-sm leading-relaxed">{c.text}</p>
                      </motion.li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default PlaygroundPage;
