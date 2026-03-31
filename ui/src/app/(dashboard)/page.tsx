"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { collectionsQueryOptions, healthQueryOptions } from "@/lib/queries";
import { formatNumber, timeAgo } from "@/lib/utils";

const Pulse = ({ className }: { readonly className?: string }) => {
  return (
    <div
      className={`animate-pulse rounded-md bg-bg-hover ${className ?? ""}`}
    />
  );
};

const DashboardPage = () => {
  const healthQuery = useQuery(healthQueryOptions());
  const collectionsQuery = useQuery(collectionsQueryOptions());

  const collections = collectionsQuery.data?.collections ?? [];
  const isLoading = collectionsQuery.isLoading;
  const isConnected = healthQuery.isSuccess;

  const totalDocs = collections.reduce(
    (sum, c) => sum + (c.document_count ?? 0),
    0
  );

  return (
    <div className="min-h-screen text-text">
      <div className="mx-auto max-w-6xl px-6 py-10">
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

        {collectionsQuery.error && (
          <div className="mb-6 rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            {collectionsQuery.error.message}
          </div>
        )}

        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard isLoading={isLoading} label="Collections">
            {formatNumber(collections.length)}
          </StatCard>
          <StatCard isLoading={isLoading} label="Documents">
            {formatNumber(totalDocs)}
          </StatCard>
          <StatCard isLoading={isLoading} label="Server">
            {healthQuery.data?.version ?? "—"}
          </StatCard>
          <StatCard isLoading={isLoading} label="Status">
            {isConnected ? "Healthy" : "—"}
          </StatCard>
        </div>

        <div className="rounded-lg border border-border bg-bg-card">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-sm font-medium text-text">Collections</h2>
          </div>

          {isLoading ? (
            <div className="divide-y divide-border">
              {Array.from({ length: 5 }).map((_, i) => (
                <div className="flex items-center gap-4 px-5 py-3.5" key={i}>
                  <Pulse className="h-4 w-40" />
                  <Pulse className="ml-auto h-4 w-16" />
                  <Pulse className="h-4 w-20" />
                </div>
              ))}
            </div>
          ) : collections.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-text-dim">
              No collections yet.{" "}
              <Link className="text-accent hover:underline" href="/collections">
                Create one
              </Link>{" "}
              to get started.
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border text-left text-[13px] text-text-dim">
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Model</th>
                  <th className="px-5 py-3 text-right font-medium">
                    Documents
                  </th>
                  <th className="px-5 py-3 text-right font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {collections.map((col) => (
                  <tr className="group" key={col.id}>
                    <td className="px-5 py-3.5">
                      <Link
                        className="block font-mono text-sm text-text transition-colors group-hover:text-accent"
                        href={`/collections/${col.name}`}
                      >
                        {col.name}
                      </Link>
                      {col.description && (
                        <p className="mt-0.5 text-xs text-text-dim">
                          {col.description}
                        </p>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-text-muted">
                      <span className="font-mono">{col.embedding_model}</span>
                      <span className="ml-1 text-text-dim">
                        ({col.dimension}d)
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-sm text-text-muted">
                      {formatNumber(col.document_count)}
                    </td>
                    <td className="px-5 py-3.5 text-right text-sm text-text-muted">
                      {timeAgo(col.updated_at)}
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

export default DashboardPage;
