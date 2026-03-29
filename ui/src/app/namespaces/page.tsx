"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { Inbox, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import {
  namespaceMetadataQueryOptions,
  namespacesQueryOptions
} from "@/lib/queries";
import { formatBytes, formatNumber, timeAgo } from "@/lib/utils";

const NamespacesPage = () => {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const namespacesQuery = useQuery(
    namespacesQueryOptions({
      pageSize: 100,
      prefix: debouncedSearch || undefined
    })
  );

  const items = namespacesQuery.data?.namespaces ?? [];

  const metadataQueries = useQueries({
    queries: items.map((ns) => namespaceMetadataQueryOptions(ns.id))
  });

  const namespaces = items.map((ns, i) => ({
    ...ns,
    isMetaLoading: metadataQueries[i]?.isLoading ?? true,
    meta:
      metadataQueries[i]?.status === "success"
        ? metadataQueries[i].data
        : undefined
  }));

  const isLoading = namespacesQuery.isLoading;
  const error = namespacesQuery.error;

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text">Namespaces</h1>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-dim" />
          <input
            className="w-72 rounded-md border border-border bg-bg-input py-2 pl-9 pr-3 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by prefix..."
            type="text"
            value={search}
          />
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {error.message}
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              className="animate-pulse rounded-lg border border-border bg-bg-card p-5"
              key={i}
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="h-4 w-40 rounded bg-bg-hover" />
                <div className="h-5 w-14 rounded-full bg-bg-hover" />
              </div>
              <div className="mt-2 h-3.5 w-28 rounded bg-bg-hover" />
              <div className="mt-2 h-3 w-20 rounded bg-bg-hover" />
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && namespaces.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20">
          <Inbox className="mb-3 size-10 text-text-dim" />
          <p className="text-sm text-text-muted">No namespaces found</p>
          {debouncedSearch && (
            <p className="mt-1 text-xs text-text-dim">
              Try a different search prefix
            </p>
          )}
        </div>
      )}

      {/* Namespace grid */}
      {!isLoading && !error && namespaces.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {namespaces.map((ns) => (
            <Link
              className="group rounded-lg border border-border bg-bg-card p-5 transition-colors hover:border-border-hover hover:bg-bg-hover/30"
              href={`/namespaces/${encodeURIComponent(ns.id)}`}
              key={ns.id}
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="mr-3 truncate font-mono text-sm font-medium text-text">
                  {ns.id}
                </span>
                {ns.isMetaLoading ? (
                  <div className="h-5 w-14 shrink-0 animate-pulse rounded-full bg-bg-hover" />
                ) : ns.meta ? (
                  <StatusBadge status={ns.meta.index.status} />
                ) : null}
              </div>

              {ns.isMetaLoading ? (
                <>
                  <div className="mt-2 h-3.5 w-28 animate-pulse rounded bg-bg-hover" />
                  <div className="mt-2 h-3 w-20 animate-pulse rounded bg-bg-hover" />
                </>
              ) : ns.meta ? (
                <>
                  <p className="mt-1 text-xs text-text-muted">
                    <span className="font-mono">
                      {formatNumber(ns.meta.approx_row_count)}
                    </span>{" "}
                    documents
                    <span className="mx-1.5 text-text-dim">&middot;</span>
                    <span className="font-mono">
                      {formatBytes(ns.meta.approx_logical_bytes)}
                    </span>
                  </p>
                  <p className="mt-1 text-xs text-text-dim">
                    Updated {timeAgo(ns.meta.updated_at)}
                  </p>
                </>
              ) : (
                <p className="mt-1 text-xs text-text-dim">
                  Failed to load metadata
                </p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

const SearchIcon = ({ className }: { readonly className?: string }) => {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.5"
      viewBox="0 0 16 16"
    >
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5L14 14" />
    </svg>
  );
};

const EmptyIcon = ({ className }: { readonly className?: string }) => {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.5"
      viewBox="0 0 24 24"
    >
      <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V7" />
      <path d="M1 4h22v3H1z" />
      <path d="M10 12h4" />
    </svg>
  );
};

export default NamespacesPage;
