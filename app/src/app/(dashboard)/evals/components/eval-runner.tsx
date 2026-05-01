"use client";

import { useMutation } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type Column, DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
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

const formatMetric = (value: number) => value.toFixed(3);

const columns: Column<EvalPerCase>[] = [
  {
    header: "Query",
    key: "query",
    render: (item) => (
      <div className="min-w-64">
        <div className="line-clamp-2 font-medium">{item.query}</div>
        <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
          {item.expected_ids.join(", ")}
        </div>
      </div>
    ),
  },
  {
    className: "text-right",
    header: "Recall",
    headerClassName: "text-right",
    key: "recall",
    render: (item) => formatMetric(item.recall_at_k),
  },
  {
    className: "text-right",
    header: "RR",
    headerClassName: "text-right",
    key: "rr",
    render: (item) => formatMetric(item.reciprocal_rank),
  },
  {
    className: "text-right",
    header: "nDCG",
    headerClassName: "text-right",
    key: "ndcg",
    render: (item) => formatMetric(item.ndcg_at_k),
  },
];

export const EvalRunner = () => {
  const { data: collectionsData } = useCollections();
  const collections = collectionsData?.collections ?? [];
  const collectionOptions = collections.map((c) => ({ label: c.name, value: c.name }));

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
      toast.success(`Evaluated ${r.total_cases} cases - recall@k ${r.recall_at_k_avg}`);
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed");
    },
  });

  const run = (e: FormEvent) => {
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
    <div className="flex flex-col gap-4">
      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Batch run</CardTitle>
          <CardDescription>
            Upload a batch of{" "}
            <code className="rounded-full bg-muted px-1.5 py-0.5 font-mono text-[11px]">
              {"{query, relevant_ids}"}
            </code>{" "}
            cases and compare retrieved chunks against known relevant IDs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={run} className="flex flex-col gap-4">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_8rem]">
              <Select
                disabled={collectionOptions.length === 0}
                id="eval-col"
                label="Collection"
                onChange={setCollection}
                options={collectionOptions}
                placeholder={
                  collectionOptions.length > 0 ? "Pick a collection..." : "No collections available"
                }
                value={collection}
              />

              <Input
                label="Top K"
                max={100}
                min={1}
                onChange={(e) => setTopK(Number(e.target.value))}
                type="number"
                value={topK}
              />
            </div>

            <Textarea
              className="min-h-52 font-mono text-xs leading-5"
              id="eval-cases"
              label="Cases (JSON)"
              onChange={(e) => setCases(e.target.value)}
              placeholder={SAMPLE}
              rows={10}
              spellCheck={false}
              value={cases}
            />

            <div className="flex justify-end">
              <Button disabled={mutation.isPending || !collection || topK < 1} type="submit">
                {mutation.isPending ? (
                  <Spinner className="border-primary-foreground border-t-transparent" size="sm" />
                ) : (
                  <Play className="size-4" />
                )}
                {mutation.isPending ? "Running..." : "Run eval"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {result && (
        <section aria-live="polite" className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Recall@k avg" value={formatMetric(result.recall_at_k_avg)} />
            <StatCard label="MRR" value={formatMetric(result.mrr)} />
            <StatCard label="nDCG@k avg" value={formatMetric(result.ndcg_at_k_avg)} />
          </div>
          <DataTable
            columns={columns}
            data={result.per_case}
            keyExtractor={(item) => `${item.query}:${item.expected_ids.join(",")}`}
          />
        </section>
      )}
    </div>
  );
};

const StatCard = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-3xl border border-border bg-card p-4">
    <div className="text-xs font-semibold text-muted-foreground">{label}</div>
    <div className="mt-2 text-2xl font-semibold tabular-nums text-foreground">{value}</div>
  </div>
);
