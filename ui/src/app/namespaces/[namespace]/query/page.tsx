"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import type { QueryResponse, QueryRow } from "@/lib/api";
import { ApiError, queryDocuments } from "@/lib/api";
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
      let cls = "text-blue-400"; // number
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = "text-[#fafafa]"; // key
        } else {
          cls = "text-emerald-400"; // string
        }
      } else if (/true|false/.test(match)) {
        cls = "text-amber-400"; // boolean
      } else if (/null/.test(match)) {
        cls = "text-[#71717a]"; // null
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-5 w-5 text-blue-500"
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        fill="currentColor"
      />
    </svg>
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
  const [activeTab, setActiveTab] = useState<"table" | "json">("table");
  const [examplesOpen, setExamplesOpen] = useState(false);
  const execTimeRef = useRef<number | null>(null);

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
    <div className="min-h-screen bg-[#09090b] text-[#fafafa]">
      <div className="max-w-[1600px] mx-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <Link
            className="text-sm text-[#a1a1aa] hover:text-[#fafafa] transition-colors inline-flex items-center gap-1"
            href={`/namespaces/${encodeURIComponent(namespace)}`}
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                d="M15 19l-7-7 7-7"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
              />
            </svg>
            Back to {namespace}
          </Link>
          <h1 className="text-2xl font-semibold mt-2">Query Playground</h1>
          <p className="text-sm text-[#71717a] mt-1">
            Execute queries against{" "}
            <span className="font-mono text-[#a1a1aa]">{namespace}</span>
          </p>
        </div>

        {/* Two-panel layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Panel — Query Editor */}
          <div className="flex flex-col gap-4">
            <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-5 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-[#a1a1aa] uppercase tracking-wider">
                  Query Editor
                </h2>
                <span className="text-xs font-mono text-[#71717a] bg-[#27272a] px-2 py-1 rounded-md">
                  {namespace}
                </span>
              </div>

              <textarea
                className="bg-[#09090b] border border-[#27272a] rounded-md p-3 font-mono text-sm text-[#fafafa] focus:outline-none focus:border-[#3f3f46] resize-none w-full transition-colors"
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
                <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-md px-3 py-2 font-mono">
                  {parseError}
                </div>
              )}

              <div className="flex items-center gap-3">
                <button
                  className="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-md px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-2"
                  disabled={loading}
                  onClick={handleExecute}
                  type="button"
                >
                  {loading ? (
                    <>
                      <Spinner />
                      Executing...
                    </>
                  ) : (
                    <>
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                        />
                        <path
                          d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                        />
                      </svg>
                      Execute
                    </>
                  )}
                </button>
                <button
                  className="text-[#a1a1aa] hover:text-[#fafafa] hover:bg-[#27272a] rounded-md px-4 py-2 text-sm font-medium transition-colors"
                  onClick={handleClear}
                  type="button"
                >
                  Clear
                </button>
                <span className="text-xs text-[#71717a] ml-auto hidden sm:inline">
                  {"\u2318"}+Enter to execute
                </span>
              </div>
            </div>

            {/* Example Queries */}
            <div className="bg-[#18181b] border border-[#27272a] rounded-lg overflow-hidden">
              <button
                className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-[#a1a1aa] hover:text-[#fafafa] transition-colors"
                onClick={() => setExamplesOpen(!examplesOpen)}
                type="button"
              >
                <span>Example Queries</span>
                <svg
                  className={`w-4 h-4 transition-transform ${examplesOpen ? "rotate-180" : ""}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    d="M19 9l-7 7-7-7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                  />
                </svg>
              </button>
              {examplesOpen && (
                <div className="border-t border-[#27272a] px-2 py-2 flex flex-col gap-1">
                  {EXAMPLE_QUERIES.map((ex) => (
                    <button
                      className="text-left px-3 py-2 rounded-md text-sm text-[#a1a1aa] hover:text-[#fafafa] hover:bg-[#27272a] transition-colors"
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
              )}
            </div>
          </div>

          {/* Right Panel — Results */}
          <div className="flex flex-col gap-4">
            <div className="bg-[#18181b] border border-[#27272a] rounded-lg p-5 flex flex-col gap-4 min-h-[500px]">
              {/* Tab toggle */}
              <div className="flex items-center gap-1 bg-[#09090b] rounded-md p-1 self-start">
                <button
                  className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                    activeTab === "table"
                      ? "bg-[#27272a] text-[#fafafa]"
                      : "text-[#71717a] hover:text-[#a1a1aa]"
                  }`}
                  onClick={() => setActiveTab("table")}
                  type="button"
                >
                  Table
                </button>
                <button
                  className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                    activeTab === "json"
                      ? "bg-[#27272a] text-[#fafafa]"
                      : "text-[#71717a] hover:text-[#a1a1aa]"
                  }`}
                  onClick={() => setActiveTab("json")}
                  type="button"
                >
                  JSON
                </button>
              </div>

              {/* Content area */}
              <div className="flex-1 overflow-auto">
                {loading && (
                  <div className="flex items-center justify-center h-full min-h-[300px]">
                    <div className="flex flex-col items-center gap-3">
                      <Spinner />
                      <span className="text-sm text-[#71717a]">
                        Executing query...
                      </span>
                    </div>
                  </div>
                )}

                {!loading && error && (
                  <div className="bg-red-400/10 border border-red-400/20 rounded-md p-4">
                    <div className="flex items-start gap-3">
                      <svg
                        className="w-5 h-5 text-red-400 mt-0.5 shrink-0"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                        />
                      </svg>
                      <div>
                        <p className="text-sm font-medium text-red-400">
                          Query Error
                        </p>
                        <p className="text-sm text-red-400/80 font-mono mt-1">
                          {error}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {!loading && !error && !result && (
                  <div className="flex items-center justify-center h-full min-h-[300px]">
                    <div className="text-center">
                      <svg
                        className="w-12 h-12 text-[#27272a] mx-auto mb-3"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                        />
                      </svg>
                      <p className="text-[#71717a] text-sm">
                        Execute a query to see results
                      </p>
                    </div>
                  </div>
                )}

                {!loading &&
                  !error &&
                  result &&
                  activeTab === "table" &&
                  (rows.length === 0 && !result.aggregations ? (
                    <div className="flex items-center justify-center h-full min-h-[200px]">
                      <p className="text-[#71717a] text-sm">
                        Query returned no rows
                      </p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-4">
                      {rows.length > 0 && (
                        <div className="overflow-x-auto rounded-md border border-[#27272a]">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b border-[#27272a] bg-[#09090b]">
                                {columns.map((col) => (
                                  <th
                                    className="text-left px-3 py-2 text-xs font-medium text-[#71717a] uppercase tracking-wider whitespace-nowrap"
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
                                  className="border-b border-[#27272a] last:border-0 hover:bg-[#27272a]/50 transition-colors"
                                  key={
                                    row.id === undefined ? i : String(row.id)
                                  }
                                >
                                  {columns.map((col) => (
                                    <td
                                      className={`px-3 py-2 whitespace-nowrap ${
                                        col === "id" || col === "$dist"
                                          ? "font-mono text-[#fafafa]"
                                          : "text-[#a1a1aa]"
                                      } ${col === "$dist" ? "text-blue-400" : ""}`}
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
                          <h3 className="text-xs font-medium text-[#71717a] uppercase tracking-wider mb-2">
                            Aggregations
                          </h3>
                          <pre className="bg-[#09090b] border border-[#27272a] rounded-md p-3 font-mono text-sm overflow-x-auto">
                            <code
                              dangerouslySetInnerHTML={{
                                __html: syntaxHighlight(
                                  JSON.stringify(result.aggregations, null, 2)
                                )
                              }}
                            />
                          </pre>
                        </div>
                      )}
                    </div>
                  ))}

                {!loading && !error && result && activeTab === "json" && (
                  <pre className="bg-[#09090b] border border-[#27272a] rounded-md p-4 font-mono text-sm overflow-auto max-h-[600px]">
                    <code
                      dangerouslySetInnerHTML={{
                        __html: syntaxHighlight(JSON.stringify(result, null, 2))
                      }}
                    />
                  </pre>
                )}
              </div>

              {/* Performance bar */}
              {!loading && result && (
                <div className="flex items-center gap-4 border-t border-[#27272a] pt-3 mt-auto">
                  {serverMs !== undefined && (
                    <span className="text-xs text-[#71717a] font-mono">
                      Server:{" "}
                      <span className="text-[#a1a1aa]">
                        {formatMs(serverMs as number)}
                      </span>
                    </span>
                  )}
                  {execTimeRef.current !== null && (
                    <span className="text-xs text-[#71717a] font-mono">
                      Round-trip:{" "}
                      <span className="text-[#a1a1aa]">
                        {formatMs(execTimeRef.current)}
                      </span>
                    </span>
                  )}
                  <span className="text-xs text-[#71717a] font-mono">
                    Rows: <span className="text-[#a1a1aa]">{rows.length}</span>
                  </span>
                  {cacheTemp !== undefined && (
                    <span className="text-xs text-[#71717a] font-mono">
                      Cache:{" "}
                      <span className="text-[#a1a1aa]">
                        {String(cacheTemp)}
                      </span>
                    </span>
                  )}
                  {result.next_cursor && (
                    <span className="text-xs text-[#71717a] font-mono ml-auto">
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
