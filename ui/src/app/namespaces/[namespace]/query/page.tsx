"use client";

import { Collapsible } from "@base-ui/react/collapsible";
import { Tabs } from "@base-ui/react/tabs";
import {
  AlertCircle,
  ChevronDown,
  ChevronLeft,
  Loader2,
  Play,
  Search
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import type { ExplainResult, QueryResponse, QueryRow } from "@/lib/api";
import { ApiError, explainQuery, queryDocuments } from "@/lib/api";
import { formatMs } from "@/lib/utils";

const EXAMPLE_QUERIES: { label: string; query: string }[] = [
  {
    label: "List all documents",
    query: JSON.stringify({ include_attributes: true, top_k: 10 }, null, 2)
  },
  {
    label: "Vector ANN search",
    query: JSON.stringify(
      { rank_by: ["vector", "ANN", [0.1, 0.2, 0.3]], top_k: 10 },
      null,
      2
    )
  },
  {
    label: "BM25 text search",
    query: JSON.stringify(
      { rank_by: ["content", "BM25", "search query"], top_k: 10 },
      null,
      2
    )
  },
  {
    label: "Filter by attribute",
    query: JSON.stringify(
      {
        filters: ["category", "Eq", "ml"],
        include_attributes: true,
        top_k: 10
      },
      null,
      2
    )
  },
  {
    label: "Aggregation count",
    query: JSON.stringify({ aggregations: [{ type: "count" }] }, null, 2)
  }
];

const DEFAULT_QUERY = JSON.stringify(
  { include_attributes: true, top_k: 10 },
  null,
  2
);

function syntaxHighlight(json: string): string {
  const escaped = json
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped.replace(
    /("(\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      let cls = "text-blue-600"; // number
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = "text-text"; // key
        } else {
          cls = "text-emerald-600"; // string
        }
      } else if (/true|false/.test(match)) {
        cls = "text-amber-600"; // boolean
      } else if (/null/.test(match)) {
        cls = "text-text-dim"; // null
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}

function extractColumns(rows: QueryRow[]): string[] {
  const colSet = new Set<string>();
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      colSet.add(key);
    }
  }
  const cols = Array.from(colSet);
  const ordered: string[] = [];
  if (cols.includes("id")) ordered.push("id");
  if (cols.includes("$dist")) ordered.push("$dist");
  for (const c of cols) {
    if (c !== "id" && c !== "$dist") ordered.push(c);
  }
  return ordered;
}

function truncate(value: unknown, max = 80): string {
  if (value === null || value === undefined) return "\u2014";
  const str = typeof value === "object" ? JSON.stringify(value) : String(value);
  if (str.length <= max) return str;
  return `${str.slice(0, max)}\u2026`;
}

export default function QueryPlaygroundPage() {
  const params = useParams();
  const namespace = decodeURIComponent(params.namespace as string);

  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [parseError, setParseError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [explainResult, setExplainResult] = useState<ExplainResult | null>(
    null
  );
  const [isExplaining, setIsExplaining] = useState(false);
  const execTimeRef = useRef<number | null>(null);

  const handleExplain = useCallback(async () => {
    setParseError(null);
    setExplainResult(null);

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(query);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : "Invalid JSON");
      return;
    }

    setIsExplaining(true);
    try {
      const res = await explainQuery(namespace, parsed);
      setExplainResult(res);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`${e.status}: ${e.message}`);
      } else {
        setError(e instanceof Error ? e.message : "Unknown error");
      }
    } finally {
      setIsExplaining(false);
    }
  }, [query, namespace]);

  const handleExecute = useCallback(async () => {
    setParseError(null);
    setError(null);

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(query);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : "Invalid JSON");
      return;
    }

    setLoading(true);
    const start = performance.now();
    try {
      const res = await queryDocuments(namespace, parsed);
      execTimeRef.current = performance.now() - start;
      setResult(res);
    } catch (e) {
      execTimeRef.current = null;
      if (e instanceof ApiError) {
        setError(`${e.status}: ${e.message}${e.code ? ` (${e.code})` : ""}`);
      } else {
        setError(e instanceof Error ? e.message : "Unknown error");
      }
    } finally {
      setLoading(false);
    }
  }, [query, namespace]);

  const handleClear = useCallback(() => {
    setResult(null);
    setError(null);
    setParseError(null);
    execTimeRef.current = null;
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleExecute();
      }
    },
    [handleExecute]
  );

  const rows = result?.rows ?? [];
  const columns = rows.length > 0 ? extractColumns(rows) : [];
  const serverMs = result?.performance?.server_total_ms;
  const cacheTemp = result?.performance?.cache_temperature;

  return (
    <div className="min-h-screen text-text">
      <div className="max-w-[1600px] mx-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <Link
            className="text-sm text-text-muted hover:text-text transition-colors inline-flex items-center gap-1"
            href={`/namespaces/${encodeURIComponent(namespace)}`}
          >
            <ChevronLeft className="size-4" />
            Back to {namespace}
          </Link>
          <h1 className="text-2xl font-semibold mt-2">Query Playground</h1>
          <p className="text-sm text-text-dim mt-1">
            Execute queries against{" "}
            <span className="font-mono text-text-muted">{namespace}</span>
          </p>
        </div>

        {/* Two-panel layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Panel — Query Editor */}
          <div className="flex flex-col gap-4">
            <div className="bg-bg-card border border-border rounded-lg p-5 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-text-muted uppercase tracking-wider">
                  Query Editor
                </h2>
                <span className="text-xs font-mono text-text-dim bg-bg-hover px-2 py-1 rounded-md">
                  {namespace}
                </span>
              </div>

              <textarea
                className="bg-bg border border-border rounded-md p-3 font-mono text-sm text-text focus:outline-none focus:border-border-hover resize-none w-full transition-colors"
                onChange={(e) => {
                  setQuery(e.target.value);
                  setParseError(null);
                }}
                onKeyDown={handleKeyDown}
                placeholder="Enter your query JSON..."
                rows={14}
                spellCheck={false}
                value={query}
              />

              {parseError && (
                <div className="text-sm text-danger bg-danger/10 border border-danger/20 rounded-md px-3 py-2 font-mono">
                  {parseError}
                </div>
              )}

              <div className="flex items-center gap-3">
                <button
                  className="bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-md px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-2"
                  disabled={loading}
                  onClick={handleExecute}
                  type="button"
                >
                  {loading ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Executing...
                    </>
                  ) : (
                    <>
                      <Play className="size-4" />
                      Execute
                    </>
                  )}
                </button>
                <button
                  className="text-text-muted hover:text-text hover:bg-bg-hover rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
                  disabled={isExplaining}
                  onClick={handleExplain}
                  type="button"
                >
                  {isExplaining ? "Explaining..." : "Explain"}
                </button>
                <button
                  className="text-text-muted hover:text-text hover:bg-bg-hover rounded-md px-4 py-2 text-sm font-medium transition-colors"
                  onClick={handleClear}
                  type="button"
                >
                  Clear
                </button>
                <span className="text-xs text-text-dim ml-auto hidden sm:inline">
                  {"\u2318"}+Enter to execute
                </span>
              </div>
            </div>

            {/* Example Queries */}
            <Collapsible.Root className="bg-bg-card border border-border rounded-lg overflow-hidden">
              <Collapsible.Trigger className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-text-muted hover:text-text transition-colors">
                <span>Example Queries</span>
                <ChevronDown className="size-4 transition-transform [[data-panel-open]_&]:rotate-180" />
              </Collapsible.Trigger>
              <Collapsible.Panel>
                <div className="border-t border-border px-2 py-2 flex flex-col gap-1">
                  {EXAMPLE_QUERIES.map((ex) => (
                    <button
                      className="text-left px-3 py-2 rounded-md text-sm text-text-muted hover:text-text hover:bg-bg-hover transition-colors"
                      key={ex.label}
                      onClick={() => {
                        setQuery(ex.query);
                        setParseError(null);
                      }}
                      type="button"
                    >
                      {ex.label}
                    </button>
                  ))}
                </div>
              </Collapsible.Panel>
            </Collapsible.Root>
          </div>

          {/* Right Panel — Results */}
          <div className="flex flex-col gap-4">
            <div className="bg-bg-card border border-border rounded-lg p-5 flex flex-col gap-4 min-h-[500px]">
              {/* Tab toggle */}
              <Tabs.Root defaultValue="table">
                <Tabs.List className="flex items-center gap-1 bg-bg-muted rounded-md p-1 self-start">
                  <Tabs.Tab
                    className="px-3 py-1.5 text-sm font-medium rounded transition-colors text-text-dim hover:text-text-muted data-[selected]:bg-bg data-[selected]:text-text data-[selected]:shadow-sm"
                    value="table"
                  >
                    Table
                  </Tabs.Tab>
                  <Tabs.Tab
                    className="px-3 py-1.5 text-sm font-medium rounded transition-colors text-text-dim hover:text-text-muted data-[selected]:bg-bg data-[selected]:text-text data-[selected]:shadow-sm"
                    value="json"
                  >
                    JSON
                  </Tabs.Tab>
                </Tabs.List>

                {/* Explain result */}
                {explainResult && (
                  <div className="rounded-md border border-border bg-bg-muted p-4">
                    <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-text-muted">
                      Query Plan
                    </h4>
                    <div className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-xs">
                      <span className="text-text-dim">Strategy</span>
                      <span className="text-text">
                        {explainResult.strategy}
                      </span>
                      <span className="text-text-dim">Total Documents</span>
                      <span className="text-text">
                        {explainResult.total_documents}
                      </span>
                      <span className="text-text-dim">Limit</span>
                      <span className="text-text">{explainResult.limit}</span>
                      <span className="text-text-dim">Has Rank By</span>
                      <span className="text-text">
                        {String(explainResult.has_rank_by)}
                      </span>
                      <span className="text-text-dim">Has Filters</span>
                      <span className="text-text">
                        {String(explainResult.has_filters)}
                      </span>
                      {explainResult.rank_by_type && (
                        <>
                          <span className="text-text-dim">Rank By Type</span>
                          <span className="text-text">
                            {explainResult.rank_by_type}
                          </span>
                        </>
                      )}
                      <span className="text-text-dim">Estimated Cost</span>
                      <span className="text-text">
                        {explainResult.estimated_cost}
                      </span>
                    </div>
                  </div>
                )}

                {/* Content area */}
                <div className="flex-1 overflow-auto">
                  {loading && (
                    <div className="flex items-center justify-center h-full min-h-[300px]">
                      <div className="flex flex-col items-center gap-3">
                        <Loader2 className="size-5 animate-spin text-accent" />
                        <span className="text-sm text-text-dim">
                          Executing query...
                        </span>
                      </div>
                    </div>
                  )}

                  {!loading && error && (
                    <div className="bg-danger/10 border border-danger/20 rounded-md p-4">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="size-5 text-danger mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-medium text-danger">
                            Query Error
                          </p>
                          <p className="text-sm text-danger/80 font-mono mt-1">
                            {error}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {!loading && !error && !result && (
                    <div className="flex items-center justify-center h-full min-h-[300px]">
                      <div className="text-center">
                        <Search className="size-12 text-border mx-auto mb-3" />
                        <p className="text-text-dim text-sm">
                          Execute a query to see results
                        </p>
                      </div>
                    </div>
                  )}

                  <Tabs.Panel value="table">
                    {!loading &&
                      !error &&
                      result &&
                      (rows.length === 0 && !result.aggregations ? (
                        <div className="flex items-center justify-center h-full min-h-[200px]">
                          <p className="text-text-dim text-sm">
                            Query returned no rows
                          </p>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-4">
                          {rows.length > 0 && (
                            <div className="overflow-x-auto rounded-md border border-border">
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="border-b border-border bg-bg-muted">
                                    {columns.map((col) => (
                                      <th
                                        className="text-left px-3 py-2 text-xs font-medium text-text-dim uppercase tracking-wider whitespace-nowrap"
                                        key={col}
                                      >
                                        {col}
                                      </th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {rows.map((row, i) => (
                                    <tr
                                      className="border-b border-border last:border-0 hover:bg-bg-hover/50 transition-colors"
                                      key={
                                        row.id === undefined
                                          ? i
                                          : String(row.id)
                                      }
                                    >
                                      {columns.map((col) => (
                                        <td
                                          className={`px-3 py-2 whitespace-nowrap ${
                                            col === "id" || col === "$dist"
                                              ? "font-mono text-text"
                                              : "text-text-muted"
                                          } ${col === "$dist" ? "text-blue-600" : ""}`}
                                          key={col}
                                          title={
                                            typeof row[col] === "object"
                                              ? JSON.stringify(row[col])
                                              : String(row[col] ?? "")
                                          }
                                        >
                                          {col === "$dist" &&
                                          typeof row[col] === "number"
                                            ? (row[col] as number).toFixed(6)
                                            : truncate(row[col])}
                                        </td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {result.aggregations && (
                            <div>
                              <h3 className="text-xs font-medium text-text-dim uppercase tracking-wider mb-2">
                                Aggregations
                              </h3>
                              <pre className="bg-bg border border-border rounded-md p-3 font-mono text-sm overflow-x-auto">
                                <code
                                  dangerouslySetInnerHTML={{
                                    __html: syntaxHighlight(
                                      JSON.stringify(
                                        result.aggregations,
                                        null,
                                        2
                                      )
                                    )
                                  }}
                                />
                              </pre>
                            </div>
                          )}
                        </div>
                      ))}
                  </Tabs.Panel>

                  <Tabs.Panel value="json">
                    {!loading && !error && result && (
                      <pre className="bg-bg border border-border rounded-md p-4 font-mono text-sm overflow-auto max-h-[600px]">
                        <code
                          dangerouslySetInnerHTML={{
                            __html: syntaxHighlight(
                              JSON.stringify(result, null, 2)
                            )
                          }}
                        />
                      </pre>
                    )}
                  </Tabs.Panel>
                </div>
              </Tabs.Root>

              {/* Performance bar */}
              {!loading && result && (
                <div className="flex items-center gap-4 border-t border-border pt-3 mt-auto">
                  {serverMs !== undefined && (
                    <span className="text-xs text-text-dim font-mono">
                      Server:{" "}
                      <span className="text-text-muted">
                        {formatMs(serverMs as number)}
                      </span>
                    </span>
                  )}
                  {execTimeRef.current !== null && (
                    <span className="text-xs text-text-dim font-mono">
                      Round-trip:{" "}
                      <span className="text-text-muted">
                        {formatMs(execTimeRef.current)}
                      </span>
                    </span>
                  )}
                  <span className="text-xs text-text-dim font-mono">
                    Rows:{" "}
                    <span className="text-text-muted">{rows.length}</span>
                  </span>
                  {cacheTemp !== undefined && (
                    <span className="text-xs text-text-dim font-mono">
                      Cache:{" "}
                      <span className="text-text-muted">
                        {String(cacheTemp)}
                      </span>
                    </span>
                  )}
                  {result.next_cursor && (
                    <span className="text-xs text-text-dim font-mono ml-auto">
                      Has more results
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
