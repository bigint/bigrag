"use client";

import { useMutation } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCollections } from "@/hooks/use-collections";
import { apiClient } from "@/lib/api";

type EvalCase = { query: string; relevant_ids: string[] };

type EvalPerCase = {
  query: string;
  hit_ids: string[];
  expected_ids: string[];
  recall_at_k: number;
  reciprocal_rank: number;
  ndcg_at_k: number;
};

type EvalResponse = {
  collection: string;
  total_cases: number;
  recall_at_k_avg: number;
  mrr: number;
  ndcg_at_k_avg: number;
  per_case: EvalPerCase[];
};

const SAMPLE = `[
  { "query": "how do I create a collection?", "relevant_ids": ["doc-abc"] },
  { "query": "what embedding models are supported?", "relevant_ids": ["doc-def"] }
]`;

export const EvalTab = () => {
  const { data: collectionsData } = useCollections();
  const collections = collectionsData?.collections ?? [];

  const [collection, setCollection] = useState("");
  const [cases, setCases] = useState(SAMPLE);
  const [topK, setTopK] = useState(10);
  const [result, setResult] = useState<EvalResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (body: {
      collection: string;
      cases: EvalCase[];
      top_k: number;
      search_mode: string;
    }) => apiClient.post<EvalResponse>("v1/evaluation", body),
    onSuccess: (r) => {
      setResult(r);
      toast.success(`Evaluated ${r.total_cases} cases — recall@k ${r.recall_at_k_avg}`);
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed");
    },
  });

  const run = (e: React.FormEvent) => {
    e.preventDefault();
    let parsed: EvalCase[];
    try {
      parsed = JSON.parse(cases);
      if (!Array.isArray(parsed) || parsed.length === 0) {
        throw new Error("Expected a non-empty JSON array of cases");
      }
    } catch (err) {
      toast.error(err instanceof Error ? `Invalid JSON: ${err.message}` : "Invalid JSON");
      return;
    }
    mutation.mutate({ collection, cases: parsed, top_k: topK, search_mode: "semantic" });
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Retrieval evaluation</CardTitle>
          <CardDescription>
            Upload a batch of <code className="text-xs">{"{query, relevant_ids}"}</code> cases and
            compute recall@k, MRR, and nDCG@k. Useful for catching regressions when you change
            chunking or re-embed a collection.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={run} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-foreground" htmlFor="eval-col">
                Collection
              </label>
              <select
                id="eval-col"
                value={collection}
                onChange={(e) => setCollection(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                required
              >
                <option value="" disabled>
                  Pick a collection…
                </option>
                {collections.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            <Input
              label="top_k"
              type="number"
              min={1}
              max={100}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            />

            <div className="flex flex-col gap-2">
              <label htmlFor="eval-cases" className="text-sm font-medium text-foreground">
                Cases (JSON)
              </label>
              <Textarea
                id="eval-cases"
                rows={8}
                value={cases}
                onChange={(e) => setCases(e.target.value)}
                placeholder={SAMPLE}
                spellCheck={false}
                className="font-mono text-xs"
              />
            </div>

            <div className="flex justify-end">
              <Button type="submit" disabled={mutation.isPending || !collection}>
                <Play className="size-4" />
                {mutation.isPending ? "Running…" : "Run eval"}
              </Button>
            </div>
          </form>

          {result && (
            <div className="mt-6 space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <StatCard label="Recall@k avg" value={result.recall_at_k_avg.toFixed(3)} />
                <StatCard label="MRR" value={result.mrr.toFixed(3)} />
                <StatCard label="nDCG@k avg" value={result.ndcg_at_k_avg.toFixed(3)} />
              </div>
              <div className="overflow-hidden rounded-md border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Query</th>
                      <th className="px-3 py-2 text-right font-medium">Recall</th>
                      <th className="px-3 py-2 text-right font-medium">RR</th>
                      <th className="px-3 py-2 text-right font-medium">nDCG</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.per_case.map((c) => (
                      <tr key={c.query} className="border-t border-border">
                        <td className="px-3 py-2 text-xs text-foreground">
                          <div className="line-clamp-2">{c.query}</div>
                        </td>
                        <td className="px-3 py-2 text-right text-xs">{c.recall_at_k}</td>
                        <td className="px-3 py-2 text-right text-xs">{c.reciprocal_rank}</td>
                        <td className="px-3 py-2 text-right text-xs">{c.ndcg_at_k}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

const StatCard = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-md border border-border bg-card p-3">
    <div className="text-xs text-muted-foreground">{label}</div>
    <div className="mt-1 text-lg font-semibold text-foreground">{value}</div>
  </div>
);
