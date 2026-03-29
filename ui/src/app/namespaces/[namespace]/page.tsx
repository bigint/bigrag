"use client";

import { Tabs } from "@base-ui/react/tabs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import {
  copyNamespace,
  deleteNamespace,
  exportNamespace,
  getDocument,
  type QueryRow,
  queryDocuments,
  triggerCompaction,
  triggerWarm,
  updateSchema,
  writeDocuments
} from "@/lib/api";
import {
  namespaceMetadataQueryOptions,
  schemaQueryOptions
} from "@/lib/queries";
import { formatBytes, formatNumber, timeAgo } from "@/lib/utils";

const NamespaceDetailPage = () => {
  const params = useParams<{ namespace: string }>();
  const router = useRouter();
  const namespace = decodeURIComponent(params.namespace);

  const metaQuery = useQuery(namespaceMetadataQueryOptions(namespace));
  const meta = metaQuery.data ?? null;

  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const compactMutation = useMutation({
    mutationFn: () => triggerCompaction(namespace),
    onError: (err) => setActionMessage(err.message),
    onSuccess: (res) => setActionMessage(res.message || "Compaction triggered")
  });

  const warmMutation = useMutation({
    mutationFn: () => triggerWarm(namespace),
    onError: (err) => setActionMessage(err.message),
    onSuccess: (res) =>
      setActionMessage(res.message || "Cache warming triggered")
  });

  return (
    <div>
      {/* Back link + header */}
      <div className="mb-6">
        <Link
          className="mb-3 inline-flex items-center gap-1.5 text-xs text-text-muted transition-colors hover:text-text"
          href="/namespaces"
        >
          <ChevronLeft className="size-3.5" />
          Back to namespaces
        </Link>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-xl font-semibold text-text">
              {namespace}
            </h1>
            {meta && <StatusBadge status={meta.index.status} />}
          </div>

          <div className="flex items-center gap-2">
            <button
              className="rounded-md px-3 py-1.5 text-xs font-medium text-text-muted transition-colors hover:bg-bg-hover hover:text-text disabled:opacity-50"
              disabled={compactMutation.isPending}
              onClick={() => {
                setActionMessage(null);
                compactMutation.mutate();
              }}
              type="button"
            >
              {compactMutation.isPending ? "Compacting..." : "Compact"}
            </button>
            <button
              className="rounded-md px-3 py-1.5 text-xs font-medium text-text-muted transition-colors hover:bg-bg-hover hover:text-text disabled:opacity-50"
              disabled={warmMutation.isPending}
              onClick={() => {
                setActionMessage(null);
                warmMutation.mutate();
              }}
              type="button"
            >
              {warmMutation.isPending ? "Warming..." : "Warm Cache"}
            </button>
          </div>
        </div>

        {actionMessage && (
          <p className="mt-2 text-xs text-text-muted">{actionMessage}</p>
        )}
      </div>

      {/* Meta loading / error */}
      {metaQuery.isLoading && (
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 rounded bg-bg-hover" />
          <div className="h-40 rounded-lg bg-bg-hover" />
        </div>
      )}

      {metaQuery.error && !metaQuery.isLoading && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {metaQuery.error.message}
        </div>
      )}

      {/* Tabs */}
      {!metaQuery.isLoading && !metaQuery.error && (
        <Tabs.Root defaultValue="documents">
          <Tabs.List className="relative mb-6 flex items-center gap-1 border-b border-border">
            <Tabs.Tab
              className="relative px-4 py-2.5 text-sm font-medium text-text-muted transition-colors hover:text-text data-[selected]:text-text"
              value="documents"
            >
              Documents
            </Tabs.Tab>
            <Tabs.Tab
              className="relative px-4 py-2.5 text-sm font-medium text-text-muted transition-colors hover:text-text data-[selected]:text-text"
              value="write"
            >
              Write
            </Tabs.Tab>
            <Tabs.Tab
              className="relative px-4 py-2.5 text-sm font-medium text-text-muted transition-colors hover:text-text data-[selected]:text-text"
              value="schema"
            >
              Schema
            </Tabs.Tab>
            <Tabs.Tab
              className="relative px-4 py-2.5 text-sm font-medium text-text-muted transition-colors hover:text-text data-[selected]:text-text"
              value="settings"
            >
              Settings
            </Tabs.Tab>
            <Tabs.Indicator className="absolute bottom-0 h-0.5 rounded-full bg-accent transition-all duration-200" />
          </Tabs.List>

          <Tabs.Panel value="documents">
            <DocumentsTab namespace={namespace} />
          </Tabs.Panel>
          <Tabs.Panel value="write">
            <WriteTab namespace={namespace} />
          </Tabs.Panel>
          <Tabs.Panel value="schema">
            <SchemaTab namespace={namespace} />
          </Tabs.Panel>
          <Tabs.Panel value="settings">
            <SettingsTab
              meta={meta}
              namespace={namespace}
              onDeleted={() => router.push("/namespaces")}
            />
          </Tabs.Panel>
        </Tabs.Root>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Documents Tab — with document viewer
// ---------------------------------------------------------------------------
const DocumentsTab = ({ namespace }: { readonly namespace: string }) => {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<readonly QueryRow[]>([]);
  const [nextCursor, setNextCursor] = useState<string | undefined>();
  const [isSearched, setIsSearched] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [docDetail, setDocDetail] = useState<Record<string, unknown> | null>(
    null
  );
  const [docLoading, setDocLoading] = useState(false);

  const queryMutation = useMutation({
    mutationFn: (cursor?: string) => {
      const body: Record<string, unknown> = {
        include_attributes: true,
        top_k: 50
      };
      if (query.trim()) {
        body.rank_by = ["content", "BM25", query.trim()];
      }
      if (cursor) {
        body.cursor = cursor;
      }
      return queryDocuments(namespace, body);
    },
    onSuccess: (res, cursor) => {
      const newRows = res.rows ?? [];
      if (cursor) {
        setRows((prev) => [...prev, ...newRows]);
      } else {
        setRows(newRows);
      }
      setNextCursor(res.next_cursor);
      setIsSearched(true);
    }
  });

  const handleSearch = () => {
    setRows([]);
    setNextCursor(undefined);
    setSelectedDocId(null);
    setDocDetail(null);
    queryMutation.mutate(undefined);
  };

  const handleListAll = () => {
    setQuery("");
    setRows([]);
    setNextCursor(undefined);
    setSelectedDocId(null);
    setDocDetail(null);
    queryMutation.mutate(undefined);
  };

  const handleViewDoc = async (id: string | number) => {
    const idStr = String(id);
    if (selectedDocId === idStr) {
      setSelectedDocId(null);
      setDocDetail(null);
      return;
    }
    setSelectedDocId(idStr);
    setDocLoading(true);
    try {
      const doc = await getDocument(namespace, idStr);
      setDocDetail(doc);
    } catch {
      setDocDetail(null);
    } finally {
      setDocLoading(false);
    }
  };

  const attributeColumns = getAttributeColumns(rows);
  const hasDist = rows.some((r) => r.$dist !== undefined);

  return (
    <div>
      {/* Query bar */}
      <div className="mb-4 flex items-center gap-3">
        <input
          className="flex-1 rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSearch();
          }}
          placeholder="BM25 search query..."
          type="text"
          value={query}
        />
        <button
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          disabled={queryMutation.isPending}
          onClick={handleSearch}
          type="button"
        >
          Search
        </button>
        <button
          className="rounded-md px-4 py-2 text-sm font-medium text-text-muted transition-colors hover:bg-bg-hover hover:text-text disabled:opacity-50"
          disabled={queryMutation.isPending}
          onClick={handleListAll}
          type="button"
        >
          List All
        </button>
      </div>

      {queryMutation.error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {queryMutation.error.message}
        </div>
      )}

      {/* Results */}
      {isSearched && (
        <>
          <div className="mb-3 flex items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-bg-hover px-2.5 py-0.5 font-mono text-[11px] font-medium text-text-muted">
              {formatNumber(rows.length)} documents
            </span>
          </div>

          {rows.length === 0 && !queryMutation.isPending ? (
            <div className="flex flex-col items-center justify-center py-16">
              <p className="text-sm text-text-muted">No documents found</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-bg-card">
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                      ID
                    </th>
                    {hasDist && (
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                        dist
                      </th>
                    )}
                    {attributeColumns.map((col) => (
                      <th
                        className="px-4 py-2.5 text-left text-xs font-medium text-text-muted"
                        key={col}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <>
                      <tr
                        className="cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-bg-hover/50"
                        key={`${row.id}-${i}`}
                        onClick={() => handleViewDoc(row.id)}
                      >
                        <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-accent">
                          {String(row.id)}
                        </td>
                        {hasDist && (
                          <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-text-muted">
                            {row.$dist !== undefined
                              ? row.$dist.toFixed(4)
                              : "-"}
                          </td>
                        )}
                        {attributeColumns.map((col) => (
                          <td
                            className="max-w-48 truncate px-4 py-2.5 text-xs text-text-muted"
                            key={col}
                            title={String(row[col] ?? "")}
                          >
                            {truncateValue(row[col])}
                          </td>
                        ))}
                      </tr>
                      {selectedDocId === String(row.id) && (
                        <tr key={`detail-${row.id}`}>
                          <td
                            className="border-b border-border bg-bg-card/50 px-4 py-3"
                            colSpan={
                              1 + (hasDist ? 1 : 0) + attributeColumns.length
                            }
                          >
                            {docLoading ? (
                              <div className="flex items-center gap-2 py-2 text-xs text-text-muted">
                                <div className="size-3 animate-spin rounded-full border-2 border-border border-t-accent" />
                                Loading document...
                              </div>
                            ) : docDetail ? (
                              <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-text-muted">
                                {JSON.stringify(docDetail, null, 2)}
                              </pre>
                            ) : (
                              <p className="text-xs text-text-dim">
                                Could not load document details.
                              </p>
                            )}
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Load more */}
          {nextCursor && (
            <div className="mt-4 flex justify-center">
              <button
                className="rounded-md px-4 py-2 text-sm font-medium text-text-muted transition-colors hover:bg-bg-hover hover:text-text disabled:opacity-50"
                disabled={queryMutation.isPending}
                onClick={() => queryMutation.mutate(nextCursor)}
                type="button"
              >
                {queryMutation.isPending ? "Loading..." : "Load More"}
              </button>
            </div>
          )}
        </>
      )}

      {queryMutation.isPending && !isSearched && (
        <div className="flex justify-center py-12">
          <div className="size-5 animate-spin rounded-full border-2 border-border border-t-accent" />
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Write Tab
// ---------------------------------------------------------------------------
const WriteTab = ({ namespace }: { readonly namespace: string }) => {
  const [jsonText, setJsonText] = useState(
    JSON.stringify(
      {
        upsert_rows: [{ id: 1, content: "Hello world" }]
      },
      null,
      2
    )
  );
  const [result, setResult] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const writeMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      writeDocuments(namespace, body),
    onSuccess: (res) => {
      setResult(JSON.stringify(res, null, 2));
      queryClient.invalidateQueries({
        queryKey: ["namespace-metadata", { namespace }]
      });
    }
  });

  const handleWrite = () => {
    setResult(null);
    try {
      const parsed = JSON.parse(jsonText);
      writeMutation.mutate(parsed);
    } catch (e) {
      setResult(
        `Parse error: ${e instanceof Error ? e.message : "Invalid JSON"}`
      );
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 text-sm font-medium text-text">
          Write Request Body
        </h3>
        <p className="mb-3 text-xs text-text-dim">
          Supports upsert_rows, upsert_columns, patch_rows, patch_columns,
          deletes, delete_by_filter, patch_by_filter, condition, schema,
          distance_metric
        </p>
        <textarea
          className="w-full resize-y rounded-lg border border-border bg-bg-input px-4 py-3 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
          onChange={(e) => setJsonText(e.target.value)}
          rows={14}
          spellCheck={false}
          value={jsonText}
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          disabled={writeMutation.isPending}
          onClick={handleWrite}
          type="button"
        >
          {writeMutation.isPending ? "Writing..." : "Execute Write"}
        </button>
      </div>

      {writeMutation.error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {writeMutation.error.message}
        </div>
      )}

      {result && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-text">Response</h3>
          <pre className="max-h-64 overflow-auto rounded-lg border border-border bg-bg-card p-4 font-mono text-xs leading-relaxed text-text-muted">
            {result}
          </pre>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Schema Tab
// ---------------------------------------------------------------------------
const SchemaTab = ({ namespace }: { readonly namespace: string }) => {
  const schemaQuery = useQuery(schemaQueryOptions(namespace));
  const [schemaText, setSchemaText] = useState("");
  const [isSynced, setIsSynced] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const queryClient = useQueryClient();

  if (schemaQuery.data && !isSynced) {
    setSchemaText(JSON.stringify(schemaQuery.data, null, 2));
    setIsSynced(true);
  }

  const saveMutation = useMutation({
    mutationFn: (text: string) => {
      const parsed = JSON.parse(text);
      return updateSchema(namespace, parsed);
    },
    onError: (err) => {
      setSaveMessage(
        err instanceof SyntaxError
          ? `Invalid JSON: ${err.message}`
          : err.message
      );
    },
    onSuccess: () => {
      setSaveMessage("Schema updated successfully");
      queryClient.invalidateQueries({ queryKey: ["schema", { namespace }] });
    }
  });

  if (schemaQuery.isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-6 w-32 rounded bg-bg-hover" />
        <div className="h-64 rounded-lg bg-bg-hover" />
      </div>
    );
  }

  const schema = schemaQuery.data;
  const schemaEntries = schema
    ? Object.entries(schema).map(([name, def]) => {
        const d = def as Record<string, unknown> | undefined;
        return {
          filterable: Boolean(d?.filterable),
          hasFullTextSearch:
            d?.full_text_search !== undefined && d?.full_text_search !== false,
          name,
          type: String(d?.type ?? "unknown")
        };
      })
    : [];

  return (
    <div className="space-y-6">
      {schemaEntries.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-medium text-text">
            Schema Definition
          </h3>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-bg-card">
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                    Attribute Name
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                    Type
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                    Filterable
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                    FTS
                  </th>
                </tr>
              </thead>
              <tbody>
                {schemaEntries.map((entry) => (
                  <tr
                    className="border-b border-border last:border-b-0"
                    key={entry.name}
                  >
                    <td className="px-4 py-2.5 font-mono text-xs text-text">
                      {entry.name}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-text-muted">
                      {entry.type}
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      {entry.filterable ? (
                        <span className="text-success">Yes</span>
                      ) : (
                        <span className="text-text-dim">No</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      {entry.hasFullTextSearch ? (
                        <span className="text-success">Yes</span>
                      ) : (
                        <span className="text-text-dim">No</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div>
        <h3 className="mb-3 text-sm font-medium text-text">Edit Schema</h3>
        <textarea
          className="w-full resize-y rounded-lg border border-border bg-bg-input px-4 py-3 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
          onChange={(e) => {
            setSchemaText(e.target.value);
            setSaveMessage(null);
          }}
          rows={16}
          spellCheck={false}
          value={schemaText}
        />

        {saveMutation.error && (
          <p className="mt-2 text-xs text-danger">
            {saveMutation.error.message}
          </p>
        )}
        {saveMessage && (
          <p className="mt-2 text-xs text-success">{saveMessage}</p>
        )}

        <div className="mt-3 flex justify-end">
          <button
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
            disabled={saveMutation.isPending}
            onClick={() => saveMutation.mutate(schemaText)}
            type="button"
          >
            {saveMutation.isPending ? "Saving..." : "Save Schema"}
          </button>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Settings Tab — with export + copy
// ---------------------------------------------------------------------------
interface SettingsTabProps {
  readonly namespace: string;
  readonly meta: {
    readonly approx_row_count: number;
    readonly approx_logical_bytes: number;
    readonly created_at: string;
    readonly updated_at: string;
    readonly index: {
      readonly status: string;
      readonly unindexed_bytes?: number;
    };
  } | null;
  readonly onDeleted: () => void;
}

const SettingsTab = ({ namespace, meta, onDeleted }: SettingsTabProps) => {
  const [confirmText, setConfirmText] = useState("");
  const [copyDest, setCopyDest] = useState("");
  const [copyMessage, setCopyMessage] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: () => deleteNamespace(namespace),
    onSuccess: () => onDeleted()
  });

  const exportMutation = useMutation({
    mutationFn: () => exportNamespace(namespace),
    onSuccess: (res) => {
      const blob = new Blob([res.data], { type: "application/jsonl" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${namespace}-export.jsonl`;
      a.click();
      URL.revokeObjectURL(url);
    }
  });

  const copyMutation = useMutation({
    mutationFn: () => copyNamespace(copyDest.trim(), namespace),
    onSuccess: (res) => {
      setCopyMessage(
        `Copied ${res.documents_copied} documents to "${res.destination_namespace}"`
      );
      setCopyDest("");
    },
    onError: (err) => setCopyMessage(err.message)
  });

  return (
    <div className="space-y-8">
      {/* Metadata */}
      {meta && (
        <div>
          <h3 className="mb-4 text-sm font-medium text-text">
            Namespace Metadata
          </h3>
          <div className="divide-y divide-border rounded-lg border border-border bg-bg-card">
            <MetaRow
              label="Created"
              sub={meta.created_at}
              value={meta.created_at ? timeAgo(meta.created_at) : "-"}
            />
            <MetaRow
              label="Updated"
              sub={meta.updated_at}
              value={meta.updated_at ? timeAgo(meta.updated_at) : "-"}
            />
            <MetaRow
              isMono
              label="Approx. Row Count"
              value={formatNumber(meta.approx_row_count)}
            />
            <MetaRow
              isMono
              label="Approx. Logical Size"
              value={formatBytes(meta.approx_logical_bytes)}
            />
            <MetaRow label="Index Status" value={meta.index.status}>
              <StatusBadge status={meta.index.status} />
            </MetaRow>
            {meta.index.unindexed_bytes !== undefined && (
              <MetaRow
                isMono
                label="Unindexed Bytes"
                value={formatBytes(meta.index.unindexed_bytes)}
              />
            )}
          </div>
        </div>
      )}

      {/* Export */}
      <div>
        <h3 className="mb-4 text-sm font-medium text-text">Export</h3>
        <div className="rounded-lg border border-border bg-bg-card p-5">
          <p className="mb-3 text-xs text-text-muted">
            Download all documents as a JSONL file.
          </p>
          <button
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
            disabled={exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
            type="button"
          >
            {exportMutation.isPending ? "Exporting..." : "Export JSONL"}
          </button>
          {exportMutation.error && (
            <p className="mt-2 text-xs text-danger">
              {exportMutation.error.message}
            </p>
          )}
        </div>
      </div>

      {/* Copy */}
      <div>
        <h3 className="mb-4 text-sm font-medium text-text">Copy Namespace</h3>
        <div className="rounded-lg border border-border bg-bg-card p-5">
          <p className="mb-3 text-xs text-text-muted">
            Copy all documents from this namespace to a new or existing
            namespace.
          </p>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="mb-1 block text-xs text-text-muted">
                Destination namespace
              </label>
              <input
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                onChange={(e) => {
                  setCopyDest(e.target.value);
                  setCopyMessage(null);
                }}
                placeholder="my-namespace-copy"
                type="text"
                value={copyDest}
              />
            </div>
            <button
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
              disabled={!copyDest.trim() || copyMutation.isPending}
              onClick={() => copyMutation.mutate()}
              type="button"
            >
              {copyMutation.isPending ? "Copying..." : "Copy"}
            </button>
          </div>
          {copyMessage && (
            <p
              className={`mt-2 text-xs ${copyMutation.error ? "text-danger" : "text-success"}`}
            >
              {copyMessage}
            </p>
          )}
        </div>
      </div>

      {/* Danger zone */}
      <div>
        <h3 className="mb-4 text-sm font-medium text-danger">Danger Zone</h3>
        <div className="rounded-lg border border-danger/30 bg-danger/5 p-5">
          <p className="mb-1 text-sm text-text">Delete this namespace</p>
          <p className="mb-4 text-xs text-text-muted">
            This action cannot be undone. All documents, vectors, and schema
            data will be permanently deleted.
          </p>

          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="mb-1.5 block text-xs text-text-muted">
                Type <span className="font-mono text-text">{namespace}</span> to
                confirm
              </label>
              <input
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder={namespace}
                type="text"
                value={confirmText}
              />
            </div>
            <button
              className="whitespace-nowrap rounded-md bg-danger/10 px-4 py-2 text-sm font-medium text-danger transition-colors hover:bg-danger/20 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={confirmText !== namespace || deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
              type="button"
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete Namespace"}
            </button>
          </div>

          {deleteMutation.error && (
            <p className="mt-3 text-xs text-danger">
              {deleteMutation.error.message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Shared Components
// ---------------------------------------------------------------------------
interface MetaRowProps {
  readonly label: string;
  readonly value: string;
  readonly sub?: string;
  readonly isMono?: boolean;
  readonly children?: React.ReactNode;
}

const MetaRow = ({ label, value, sub, isMono, children }: MetaRowProps) => {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-sm text-text-muted">{label}</span>
      <div className="flex items-center gap-2">
        {children ?? (
          <span
            className={`text-sm text-text ${isMono ? "font-mono" : ""}`}
            title={sub}
          >
            {value}
          </span>
        )}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function getAttributeColumns(rows: readonly QueryRow[]): readonly string[] {
  const ignored = new Set(["id", "$dist"]);
  const counts = new Map<string, number>();

  for (const row of rows.slice(0, 20)) {
    for (const key of Object.keys(row)) {
      if (!ignored.has(key)) {
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
    }
  }

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([key]) => key);
}

function truncateValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") {
    return value.length > 80 ? `${value.slice(0, 80)}...` : value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `[${value.length} items]`;
  }
  if (typeof value === "object") {
    const str = JSON.stringify(value);
    return str.length > 80 ? `${str.slice(0, 80)}...` : str;
  }
  return String(value);
}

export default NamespaceDetailPage;
