"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { FileText, Loader2, Search } from "lucide-react";
import { useState } from "react";
import type { QueryResponse } from "@bigrag/client";
import { getClient } from "@/lib/client";
import { collectionsQueryOptions } from "@/lib/queries";

const QueryPage = () => {
  const collectionsQuery = useQuery(collectionsQueryOptions());
  const [selectedCollection, setSelectedCollection] = useState("");
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [minScore, setMinScore] = useState(0);
  const [searchMode, setSearchMode] = useState<"semantic" | "keyword" | "hybrid">("semantic");
  const [rerank, setRerank] = useState(false);
  const [results, setResults] = useState<QueryResponse | null>(null);

  const queryMutation = useMutation({
    mutationFn: () =>
      getClient().query(selectedCollection, {
        query,
        top_k: topK,
        search_mode: searchMode,
        ...(minScore > 0 ? { min_score: minScore / 100 } : {}),
        ...(rerank ? { rerank: true } : {})
      }),
    onSuccess: setResults
  });

  const collections = collectionsQuery.data?.collections ?? [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-text">Query</h1>
        <p className="mt-1 text-sm text-text-muted">
          Search across your document collections using natural language
        </p>
      </div>

      <div className="mb-6 space-y-4 rounded-lg border border-border bg-bg-card p-5">
        <div className="flex flex-wrap gap-4">
          <select
            className="w-64 rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text focus:border-border-hover focus:outline-none"
            onChange={(e) => setSelectedCollection(e.target.value)}
            value={selectedCollection}
          >
            <option value="">Select a collection</option>
            {collections.map((c) => (
              <option key={c.id} value={c.name}>
                {c.name} ({c.document_count} docs)
              </option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            <label className="text-sm text-text-muted" htmlFor="topk">
              Top K:
            </label>
            <input
              className="w-20 rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text focus:border-border-hover focus:outline-none"
              id="topk"
              max={100}
              min={1}
              onChange={(e) => setTopK(Number(e.target.value))}
              type="number"
              value={topK}
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-text-muted" htmlFor="minscore">
              Min Score:
            </label>
            <input
              className="w-20 rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text focus:border-border-hover focus:outline-none"
              id="minscore"
              max={100}
              min={0}
              onChange={(e) => setMinScore(Number(e.target.value))}
              type="number"
              value={minScore}
            />
            <span className="text-xs text-text-dim">%</span>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-text-muted" htmlFor="search-mode">Mode:</label>
            <select
              className="rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text focus:border-border-hover focus:outline-none"
              id="search-mode"
              onChange={(e) => setSearchMode(e.target.value as "semantic" | "keyword" | "hybrid")}
              value={searchMode}
            >
              <option value="semantic">Semantic</option>
              <option value="keyword">Keyword</option>
              <option value="hybrid">Hybrid</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <input
              checked={rerank}
              id="rerank"
              onChange={(e) => setRerank(e.target.checked)}
              type="checkbox"
            />
            <label className="text-sm text-text-muted" htmlFor="rerank">
              Rerank
            </label>
          </div>
        </div>

        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-dim" />
            <input
              className="w-full rounded-md border border-border bg-bg-input py-2.5 pl-9 pr-3 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && selectedCollection && query)
                  queryMutation.mutate();
              }}
              placeholder="Ask a question about your documents..."
              value={query}
            />
          </div>
          <button
            className="flex items-center gap-1.5 rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50"
            disabled={!selectedCollection || !query || queryMutation.isPending}
            onClick={() => queryMutation.mutate()}
            type="button"
          >
            {queryMutation.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Search className="size-4" />
            )}
            Search
          </button>
        </div>
      </div>

      {queryMutation.error && (
        <div className="mb-6 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {queryMutation.error.message}
        </div>
      )}

      {results && (
        <div>
          <p className="mb-4 text-sm text-text-muted">
            {results.total} results for &ldquo;{results.query}&rdquo; in{" "}
            <span className="font-mono">{results.collection}</span>
          </p>

          <div className="space-y-3">
            {results.results.map((result, idx) => (
              <div
                className="rounded-lg border border-border bg-bg-card p-4"
                key={result.id}
              >
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="flex size-6 items-center justify-center rounded-full bg-bg-hover text-xs font-mono text-text-muted">
                      {idx + 1}
                    </span>
                    <FileText className="size-3.5 text-text-dim" />
                    {result.document_id && (
                      <span className="font-mono text-xs text-text-dim">
                        doc:{result.document_id.slice(0, 8)}
                      </span>
                    )}
                    {result.chunk_index !== null && (
                      <span className="text-xs text-text-dim">
                        chunk #{result.chunk_index}
                      </span>
                    )}
                  </div>
                  <span className="rounded-full bg-accent/10 px-2 py-0.5 font-mono text-xs text-accent">
                    {(result.score * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-muted">
                  {result.text}
                </p>
              </div>
            ))}

            {results.results.length === 0 && (
              <div className="py-12 text-center text-sm text-text-dim">
                No matching results found
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default QueryPage;
