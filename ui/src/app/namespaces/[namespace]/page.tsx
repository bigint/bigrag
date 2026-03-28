"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getNamespaceMetadata,
  getSchema,
  updateSchema,
  queryDocuments,
  deleteNamespace,
  triggerCompaction,
  triggerWarm,
  type NamespaceMetadata,
  type QueryRow,
} from "@/lib/api";
import { formatNumber, formatBytes, timeAgo } from "@/lib/utils";

type Tab = "documents" | "schema" | "settings";

export default function NamespaceDetailPage() {
  const params = useParams<{ namespace: string }>();
  const router = useRouter();
  const namespace = decodeURIComponent(params.namespace);

  const [activeTab, setActiveTab] = useState<Tab>("documents");
  const [meta, setMeta] = useState<NamespaceMetadata | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaError, setMetaError] = useState<string | null>(null);

  // Action states
  const [compacting, setCompacting] = useState(false);
  const [warming, setWarming] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchMeta = useCallback(async () => {
    setMetaLoading(true);
    setMetaError(null);
    try {
      const data = await getNamespaceMetadata(namespace);
      setMeta(data);
    } catch (err) {
      setMetaError(
        err instanceof Error ? err.message : "Failed to load metadata"
      );
    } finally {
      setMetaLoading(false);
    }
  }, [namespace]);

  useEffect(() => {
    fetchMeta();
  }, [fetchMeta]);

  const handleCompact = async () => {
    setCompacting(true);
    setActionMessage(null);
    try {
      const res = await triggerCompaction(namespace);
      setActionMessage(res.message || "Compaction triggered");
    } catch (err) {
      setActionMessage(
        err instanceof Error ? err.message : "Compaction failed"
      );
    } finally {
      setCompacting(false);
    }
  };

  const handleWarm = async () => {
    setWarming(true);
    setActionMessage(null);
    try {
      const res = await triggerWarm(namespace);
      setActionMessage(res.message || "Cache warming triggered");
    } catch (err) {
      setActionMessage(
        err instanceof Error ? err.message : "Cache warming failed"
      );
    } finally {
      setWarming(false);
    }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: "documents", label: "Documents" },
    { id: "schema", label: "Schema" },
    { id: "settings", label: "Settings" },
  ];

  return (
    <div>
      {/* Back link + header */}
      <div className="mb-6">
        <Link
          href="/namespaces"
          className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-text transition-colors mb-3"
        >
          <ArrowLeftIcon className="size-3.5" />
          Back to namespaces
        </Link>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-text font-mono">
              {namespace}
            </h1>
            {meta && <StatusBadge status={meta.index.status} />}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCompact}
              disabled={compacting}
              className="px-3 py-1.5 rounded-md text-xs font-medium text-text-muted hover:bg-bg-hover hover:text-text transition-colors disabled:opacity-50"
            >
              {compacting ? "Compacting..." : "Compact"}
            </button>
            <button
              onClick={handleWarm}
              disabled={warming}
              className="px-3 py-1.5 rounded-md text-xs font-medium text-text-muted hover:bg-bg-hover hover:text-text transition-colors disabled:opacity-50"
            >
              {warming ? "Warming..." : "Warm Cache"}
            </button>
          </div>
        </div>

        {actionMessage && (
          <p className="text-xs text-text-muted mt-2">{actionMessage}</p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-border mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
              activeTab === tab.id
                ? "text-text"
                : "text-text-muted hover:text-text"
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent rounded-full" />
            )}
          </button>
        ))}
      </div>

      {/* Meta loading / error */}
      {metaLoading && (
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-bg-hover rounded" />
          <div className="h-40 bg-bg-hover rounded-lg" />
        </div>
      )}

      {metaError && !metaLoading && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {metaError}
        </div>
      )}

      {/* Tab content */}
      {!metaLoading && !metaError && (
        <>
          {activeTab === "documents" && (
            <DocumentsTab namespace={namespace} />
          )}
          {activeTab === "schema" && <SchemaTab namespace={namespace} />}
          {activeTab === "settings" && (
            <SettingsTab
              namespace={namespace}
              meta={meta}
              onDeleted={() => router.push("/namespaces")}
            />
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Documents Tab
// ---------------------------------------------------------------------------
function DocumentsTab({ namespace }: { namespace: string }) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<QueryRow[]>([]);
  const [nextCursor, setNextCursor] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const doQuery = async (cursor?: string) => {
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        top_k: 50,
        include_attributes: true,
      };

      if (query.trim()) {
        body.rank_by = { bm25: { query: query.trim(), fields: [] } };
      }

      if (cursor) {
        body.cursor = cursor;
      }

      const res = await queryDocuments(namespace, body);
      const newRows = res.rows || [];

      if (cursor) {
        setRows((prev) => [...prev, ...newRows]);
      } else {
        setRows(newRows);
      }
      setNextCursor(res.next_cursor);
      setSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setRows([]);
    setNextCursor(undefined);
    doQuery();
  };

  const handleListAll = () => {
    setQuery("");
    setRows([]);
    setNextCursor(undefined);
    doQuery();
  };

  // Derive attribute columns from the first few rows
  const attributeColumns = getAttributeColumns(rows);

  return (
    <div>
      {/* Query bar */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="BM25 search query..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          className="flex-1 bg-bg-input border border-border rounded-md px-3 py-2 text-sm text-text placeholder:text-text-dim focus:outline-none focus:border-border-hover"
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="px-4 py-2 rounded-md text-sm font-medium bg-accent hover:bg-accent-hover text-white transition-colors disabled:opacity-50"
        >
          Search
        </button>
        <button
          onClick={handleListAll}
          disabled={loading}
          className="px-4 py-2 rounded-md text-sm font-medium text-text-muted hover:bg-bg-hover hover:text-text transition-colors disabled:opacity-50"
        >
          List All
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger mb-4">
          {error}
        </div>
      )}

      {/* Results */}
      {searched && (
        <>
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-flex items-center rounded-full bg-bg-hover px-2.5 py-0.5 text-[11px] font-medium text-text-muted font-mono">
              {formatNumber(rows.length)} documents
            </span>
          </div>

          {rows.length === 0 && !loading ? (
            <div className="flex flex-col items-center justify-center py-16">
              <p className="text-text-muted text-sm">No documents found</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-bg-card">
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-text-muted">
                      ID
                    </th>
                    {rows.some((r) => r.$dist !== undefined) && (
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-text-muted">
                        dist
                      </th>
                    )}
                    {attributeColumns.map((col) => (
                      <th
                        key={col}
                        className="text-left px-4 py-2.5 text-xs font-medium text-text-muted"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr
                      key={`${row.id}-${i}`}
                      className="border-b border-border last:border-b-0 hover:bg-bg-hover/50 transition-colors"
                    >
                      <td className="px-4 py-2.5 font-mono text-xs text-text whitespace-nowrap">
                        {String(row.id)}
                      </td>
                      {rows.some((r) => r.$dist !== undefined) && (
                        <td className="px-4 py-2.5 font-mono text-xs text-text-muted whitespace-nowrap">
                          {row.$dist !== undefined
                            ? row.$dist.toFixed(4)
                            : "-"}
                        </td>
                      )}
                      {attributeColumns.map((col) => (
                        <td
                          key={col}
                          className="px-4 py-2.5 text-xs text-text-muted max-w-48 truncate"
                          title={String(row[col] ?? "")}
                        >
                          {truncateValue(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Load more */}
          {nextCursor && (
            <div className="flex justify-center mt-4">
              <button
                onClick={() => doQuery(nextCursor)}
                disabled={loading}
                className="px-4 py-2 rounded-md text-sm font-medium text-text-muted hover:bg-bg-hover hover:text-text transition-colors disabled:opacity-50"
              >
                {loading ? "Loading..." : "Load More"}
              </button>
            </div>
          )}
        </>
      )}

      {loading && !searched && (
        <div className="flex justify-center py-12">
          <div className="size-5 border-2 border-border border-t-accent rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Schema Tab
// ---------------------------------------------------------------------------
function SchemaTab({ namespace }: { namespace: string }) {
  const [schema, setSchema] = useState<Record<string, unknown> | null>(null);
  const [schemaText, setSchemaText] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getSchema(namespace)
      .then((data) => {
        if (cancelled) return;
        setSchema(data);
        setSchemaText(JSON.stringify(data, null, 2));
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load schema");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [namespace]);

  const handleSave = async () => {
    setSaving(true);
    setSaveMessage(null);
    setError(null);
    try {
      const parsed = JSON.parse(schemaText);
      await updateSchema(namespace, parsed);
      setSchema(parsed);
      setSaveMessage("Schema updated successfully");
    } catch (err) {
      if (err instanceof SyntaxError) {
        setError("Invalid JSON: " + err.message);
      } else {
        setError(
          err instanceof Error ? err.message : "Failed to update schema"
        );
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-6 w-32 bg-bg-hover rounded" />
        <div className="h-64 bg-bg-hover rounded-lg" />
      </div>
    );
  }

  // Parse schema into table rows
  const schemaEntries = schema
    ? Object.entries(schema).map(([name, def]) => {
        const d = def as Record<string, unknown> | undefined;
        return {
          name,
          type: String(d?.type ?? "unknown"),
          filterable: Boolean(d?.filterable),
          full_text_search:
            d?.full_text_search !== undefined && d?.full_text_search !== false,
        };
      })
    : [];

  return (
    <div className="space-y-6">
      {/* Schema table */}
      {schemaEntries.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-text mb-3">
            Schema Definition
          </h3>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-bg-card">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-text-muted">
                    Attribute Name
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-text-muted">
                    Type
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-text-muted">
                    Filterable
                  </th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-text-muted">
                    FTS
                  </th>
                </tr>
              </thead>
              <tbody>
                {schemaEntries.map((entry) => (
                  <tr
                    key={entry.name}
                    className="border-b border-border last:border-b-0"
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
                      {entry.full_text_search ? (
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

      {/* JSON editor */}
      <div>
        <h3 className="text-sm font-medium text-text mb-3">Edit Schema</h3>
        <textarea
          value={schemaText}
          onChange={(e) => {
            setSchemaText(e.target.value);
            setSaveMessage(null);
          }}
          rows={16}
          spellCheck={false}
          className="w-full bg-bg-input border border-border rounded-lg px-4 py-3 text-sm font-mono text-text placeholder:text-text-dim focus:outline-none focus:border-border-hover resize-y"
        />

        {error && (
          <p className="text-xs text-danger mt-2">{error}</p>
        )}
        {saveMessage && (
          <p className="text-xs text-success mt-2">{saveMessage}</p>
        )}

        <div className="flex justify-end mt-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-md text-sm font-medium bg-accent hover:bg-accent-hover text-white transition-colors disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Schema"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings Tab
// ---------------------------------------------------------------------------
function SettingsTab({
  namespace,
  meta,
  onDeleted,
}: {
  namespace: string;
  meta: NamespaceMetadata | null;
  onDeleted: () => void;
}) {
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDelete = async () => {
    if (confirmText !== namespace) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteNamespace(namespace);
      onDeleted();
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete namespace"
      );
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Metadata */}
      {meta && (
        <div>
          <h3 className="text-sm font-medium text-text mb-4">
            Namespace Metadata
          </h3>
          <div className="rounded-lg border border-border bg-bg-card divide-y divide-border">
            <MetaRow label="Created" value={meta.created_at ? timeAgo(meta.created_at) : "-"} sub={meta.created_at} />
            <MetaRow label="Updated" value={meta.updated_at ? timeAgo(meta.updated_at) : "-"} sub={meta.updated_at} />
            <MetaRow
              label="Approx. Row Count"
              value={formatNumber(meta.approx_row_count)}
              mono
            />
            <MetaRow
              label="Approx. Logical Size"
              value={formatBytes(meta.approx_logical_bytes)}
              mono
            />
            <MetaRow label="Index Status" value={meta.index.status}>
              <StatusBadge status={meta.index.status} />
            </MetaRow>
            {meta.index.unindexed_bytes !== undefined && (
              <MetaRow
                label="Unindexed Bytes"
                value={formatBytes(meta.index.unindexed_bytes)}
                mono
              />
            )}
          </div>
        </div>
      )}

      {/* Danger zone */}
      <div>
        <h3 className="text-sm font-medium text-danger mb-4">Danger Zone</h3>
        <div className="rounded-lg border border-danger/30 bg-danger/5 p-5">
          <p className="text-sm text-text mb-1">Delete this namespace</p>
          <p className="text-xs text-text-muted mb-4">
            This action cannot be undone. All documents, vectors, and schema
            data will be permanently deleted.
          </p>

          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-xs text-text-muted mb-1.5">
                Type <span className="font-mono text-text">{namespace}</span> to
                confirm
              </label>
              <input
                type="text"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder={namespace}
                className="w-full bg-bg-input border border-border rounded-md px-3 py-2 text-sm font-mono text-text placeholder:text-text-dim focus:outline-none focus:border-border-hover"
              />
            </div>
            <button
              onClick={handleDelete}
              disabled={confirmText !== namespace || deleting}
              className="px-4 py-2 rounded-md text-sm font-medium bg-danger/10 text-danger hover:bg-danger/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {deleting ? "Deleting..." : "Delete Namespace"}
            </button>
          </div>

          {deleteError && (
            <p className="text-xs text-danger mt-3">{deleteError}</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared Components
// ---------------------------------------------------------------------------
function MetaRow({
  label,
  value,
  sub,
  mono,
  children,
}: {
  label: string;
  value: string;
  sub?: string;
  mono?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-sm text-text-muted">{label}</span>
      <div className="flex items-center gap-2">
        {children || (
          <span
            className={`text-sm text-text ${mono ? "font-mono" : ""}`}
            title={sub}
          >
            {value}
          </span>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const isReady = status === "ready" || status === "indexed";
  const isBuilding = status === "building" || status === "indexing";

  let colorClasses: string;
  if (isReady) {
    colorClasses = "bg-success/10 text-success";
  } else if (isBuilding) {
    colorClasses = "bg-warning/10 text-warning";
  } else {
    colorClasses = "bg-bg-hover text-text-muted";
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium shrink-0 ${colorClasses}`}
    >
      <span
        className={`size-1.5 rounded-full ${
          isReady
            ? "bg-success"
            : isBuilding
              ? "bg-warning animate-pulse"
              : "bg-text-dim"
        }`}
      />
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------
function ArrowLeftIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10 3L5 8l5 5" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function getAttributeColumns(rows: QueryRow[]): string[] {
  const ignored = new Set(["id", "$dist"]);
  const counts = new Map<string, number>();

  for (const row of rows.slice(0, 20)) {
    for (const key of Object.keys(row)) {
      if (!ignored.has(key)) {
        counts.set(key, (counts.get(key) || 0) + 1);
      }
    }
  }

  // Sort by frequency, take top 4
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([key]) => key);
}

function truncateValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") {
    return value.length > 80 ? value.slice(0, 80) + "..." : value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `[${value.length} items]`;
  }
  if (typeof value === "object") {
    const str = JSON.stringify(value);
    return str.length > 80 ? str.slice(0, 80) + "..." : str;
  }
  return String(value);
}
