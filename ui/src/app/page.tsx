"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  healthQueryOptions,
  namespaceMetadataQueryOptions,
  namespacesQueryOptions
} from "@/lib/queries";
import { formatBytes, formatNumber, timeAgo } from "@/lib/utils";

const Pulse = ({ className }: { readonly className?: string }) => {
  return (
    <div
      className={`animate-pulse rounded-md bg-bg-hover ${className ?? ""}`}
    />
  );
};

const DashboardPage = () => {
  const healthQuery = useQuery(healthQueryOptions());
  const namespacesQuery = useQuery(namespacesQueryOptions());

  const allNames = namespacesQuery.data?.namespaces.map((ns) => ns.id) ?? [];
  const top = allNames.slice(0, 10);

  const metadataQueries = useQueries({
    queries: top.map((name) => namespaceMetadataQueryOptions(name))
  });

  const isLoading = namespacesQuery.isLoading;
  const isConnected = healthQuery.isSuccess;

  const namespaces = top.map((name, i) => ({
    metadata:
      metadataQueries[i]?.status === "success" ? metadataQueries[i].data : null,
    name
  }));

  const totalDocs = namespaces.reduce(
    (sum, ns) => sum + (ns.metadata?.approx_row_count ?? 0),
    0
  );
  const totalStorage = namespaces.reduce(
    (sum, ns) => sum + (ns.metadata?.approx_logical_bytes ?? 0),
    0
  );

  return (
    <div className="min-h-screen text-text">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <div className="mt-1 flex items-center gap-2 text-[13px] text-text-muted">
            {healthQuery.isLoading ? (
              <Pulse className="h-3 w-20" />
            ) : isConnected ? (
              <>
                <span className="inline-block size-2 rounded-full bg-success" />
                <span>Connected</span>
              </>
            ) : (
              <>
                <span className="inline-block size-2 rounded-full bg-danger" />
                <span>Disconnected</span>
              </>
            )}
          </div>
        </div>

        {/* Error banner */}
        {namespacesQuery.error && (
          <div className="mb-6 rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            {namespacesQuery.error.message}
          </div>
        )}

        {/* Stats grid */}
        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard isLoading={isLoading} label="Namespaces">
            {formatNumber(allNames.length)}
          </StatCard>
          <StatCard isLoading={isLoading} label="Documents">
            {formatNumber(totalDocs)}
          </StatCard>
          <StatCard isLoading={isLoading} label="Storage">
            {formatBytes(totalStorage)}
          </StatCard>
          <StatCard isLoading={isLoading} label="Server">
            {healthQuery.data?.version ?? "—"}
          </StatCard>
        </div>

        {/* Recent namespaces table */}
        <div className="rounded-lg border border-border bg-bg-card">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-sm font-medium text-text">Recent Namespaces</h2>
          </div>

          {isLoading ? (
            <div className="divide-y divide-border">
              {Array.from({ length: 5 }).map((_, i) => (
                <div className="flex items-center gap-4 px-5 py-3.5" key={i}>
                  <Pulse className="h-4 w-40" />
                  <Pulse className="ml-auto h-4 w-16" />
                  <Pulse className="h-4 w-20" />
                  <Pulse className="h-4 w-16" />
                </div>
              ))}
            </div>
          ) : namespaces.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-text-dim">
              No namespaces found. Create one to get started.
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border text-left text-[13px] text-text-dim">
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 text-right font-medium">
                    Documents
                  </th>
                  <th className="px-5 py-3 text-right font-medium">Updated</th>
                  <th className="px-5 py-3 text-right font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {namespaces.map((ns) => (
                  <tr className="group" key={ns.name}>
                    <td className="px-5 py-3.5">
                      <Link
                        className="block font-mono text-sm text-text transition-colors group-hover:text-accent"
                        href={`/namespaces/${ns.name}`}
                      >
                        {ns.name}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-sm text-text-muted">
                      {ns.metadata
                        ? formatNumber(ns.metadata.approx_row_count)
                        : "—"}
                    </td>
                    <td className="px-5 py-3.5 text-right text-sm text-text-muted">
                      {ns.metadata ? timeAgo(ns.metadata.updated_at) : "—"}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {ns.metadata ? (
                        <IndexStatusBadge status={ns.metadata.index.status} />
                      ) : (
                        <span className="text-sm text-text-dim">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

interface StatCardProps {
  readonly label: string;
  readonly isLoading: boolean;
  readonly children: React.ReactNode;
}

const StatCard = ({ label, isLoading, children }: StatCardProps) => {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-5">
      <p className="text-[13px] text-text-muted">{label}</p>
      {isLoading ? (
        <Pulse className="mt-2 h-7 w-16" />
      ) : (
        <p className="mt-1 font-mono text-2xl font-semibold">{children}</p>
      )}
    </div>
  );
};

const IndexStatusBadge = ({ status }: { readonly status: string }) => {
  const isReady = status === "ready" || status === "up-to-date";
  const isBuilding = status === "indexing";

  const colorClasses = isReady
    ? "bg-success/10 text-success"
    : isBuilding
      ? "bg-warning/10 text-warning"
      : "bg-bg-hover text-text-muted";

  const dotClasses = isReady
    ? "bg-success"
    : isBuilding
      ? "bg-warning"
      : "bg-text-dim";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${colorClasses}`}
    >
      <span className={`inline-block size-1.5 rounded-full ${dotClasses}`} />
      {status}
    </span>
  );
};

export default DashboardPage;
