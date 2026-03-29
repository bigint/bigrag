"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  listNamespaces,
  getNamespaceMetadata,
  type NamespaceListItem,
  type NamespaceMetadata,
} from "@/lib/api";
import { formatNumber, formatBytes, timeAgo } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";

interface NamespaceWithMeta extends NamespaceListItem {
  meta?: NamespaceMetadata;
  metaLoading: boolean;
}

export default function NamespacesPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [namespaces, setNamespaces] = useState<NamespaceWithMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchNamespaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listNamespaces(
        debouncedSearch || undefined,
        undefined,
        100
      );
      const items: NamespaceWithMeta[] = res.namespaces.map((ns) => ({
        ...ns,
        metaLoading: true,
      }));
      setNamespaces(items);
      setLoading(false);

      // Fetch metadata for each namespace in parallel
      const metaResults = await Promise.allSettled(
        items.map((ns) => getNamespaceMetadata(ns.id))
      );

      setNamespaces((prev) =>
        prev.map((ns, i) => {
          const result = metaResults[i];
          return {
            ...ns,
            meta: result.status === "fulfilled" ? result.value : undefined,
            metaLoading: false,
          };
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load namespaces");
      setLoading(false);
    }
  }, [debouncedSearch]);

  useEffect(() => {
    fetchNamespaces();
  }, [fetchNamespaces]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-text">Namespaces</h1>
        <div className="relative">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-text-dim" />
          <input
            type="text"
            placeholder="Search by prefix..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-bg-input border border-border rounded-md pl-9 pr-3 py-2 text-sm text-text placeholder:text-text-dim focus:outline-none focus:border-border-hover w-72"
          />
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-bg-card p-5 animate-pulse"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="h-4 w-40 bg-bg-hover rounded" />
                <div className="h-5 w-14 bg-bg-hover rounded-full" />
              </div>
              <div className="h-3.5 w-28 bg-bg-hover rounded mt-2" />
              <div className="h-3 w-20 bg-bg-hover rounded mt-2" />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && namespaces.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20">
          <EmptyIcon className="size-10 text-text-dim mb-3" />
          <p className="text-text-muted text-sm">No namespaces found</p>
          {debouncedSearch && (
            <p className="text-text-dim text-xs mt-1">
              Try a different search prefix
            </p>
          )}
        </div>
      )}

      {/* Namespace grid */}
      {!loading && !error && namespaces.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {namespaces.map((ns) => (
            <Link
              key={ns.id}
              href={`/namespaces/${encodeURIComponent(ns.id)}`}
              className="group rounded-lg border border-border bg-bg-card p-5 transition-colors hover:border-border-hover hover:bg-bg-hover/30"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-text truncate mr-3 font-mono">
                  {ns.id}
                </span>
                {ns.metaLoading ? (
                  <div className="h-5 w-14 bg-bg-hover rounded-full animate-pulse shrink-0" />
                ) : ns.meta ? (
                  <StatusBadge status={ns.meta.index.status} />
                ) : null}
              </div>

              {ns.metaLoading ? (
                <>
                  <div className="h-3.5 w-28 bg-bg-hover rounded animate-pulse mt-2" />
                  <div className="h-3 w-20 bg-bg-hover rounded animate-pulse mt-2" />
                </>
              ) : ns.meta ? (
                <>
                  <p className="text-xs text-text-muted mt-1">
                    <span className="font-mono">
                      {formatNumber(ns.meta.approx_row_count)}
                    </span>{" "}
                    documents
                    <span className="text-text-dim mx-1.5">&middot;</span>
                    <span className="font-mono">
                      {formatBytes(ns.meta.approx_logical_bytes)}
                    </span>
                  </p>
                  <p className="text-xs text-text-dim mt-1">
                    Updated {timeAgo(ns.meta.updated_at)}
                  </p>
                </>
              ) : (
                <p className="text-xs text-text-dim mt-1">
                  Failed to load metadata
                </p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function SearchIcon({ className }: { className?: string }) {
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
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5L14 14" />
    </svg>
  );
}

function EmptyIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7" />
      <path d="M1 4h22v3H1z" />
      <path d="M10 12h4" />
    </svg>
  );
}
