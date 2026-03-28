"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  getHealth,
  listNamespaces,
  getNamespaceMetadata,
  type NamespaceMetadata,
} from "@/lib/api";
import { formatBytes, formatNumber, timeAgo } from "@/lib/utils";

interface NamespaceRow {
  name: string;
  metadata: NamespaceMetadata | null;
}

function Pulse({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-[#27272a] ${className ?? ""}`}
    />
  );
}

export default function DashboardPage() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [version, setVersion] = useState<string>("");
  const [namespaceCount, setNamespaceCount] = useState<number>(0);
  const [namespaces, setNamespaces] = useState<NamespaceRow[]>([]);
  const [totalDocs, setTotalDocs] = useState<number>(0);
  const [totalStorage, setTotalStorage] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const [health, nsList] = await Promise.all([
          getHealth().catch(() => null),
          listNamespaces(undefined, undefined, 100).catch(() => null),
        ]);

        if (cancelled) return;

        if (health) {
          setConnected(true);
          setVersion(health.version);
        } else {
          setConnected(false);
        }

        if (!nsList) {
          setConnected(false);
          setLoading(false);
          return;
        }

        const allNames = nsList.namespaces.map((ns) => ns.id);
        setNamespaceCount(allNames.length);

        const top = allNames.slice(0, 10);
        const metadataResults = await Promise.allSettled(
          top.map((name) => getNamespaceMetadata(name))
        );

        if (cancelled) return;

        let docs = 0;
        let storage = 0;
        const rows: NamespaceRow[] = top.map((name, i) => {
          const result = metadataResults[i];
          if (result.status === "fulfilled") {
            const md = result.value;
            docs += md.approx_row_count;
            storage += md.approx_logical_bytes;
            return { name, metadata: md };
          }
          return { name, metadata: null };
        });

        setTotalDocs(docs);
        setTotalStorage(storage);
        setNamespaces(rows);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load data");
          setConnected(false);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchData();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#09090b] text-[#fafafa]">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <div className="mt-1 flex items-center gap-2 text-[13px] text-[#a1a1aa]">
            {connected === null ? (
              <Pulse className="h-3 w-20" />
            ) : connected ? (
              <>
                <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                <span>Connected</span>
              </>
            ) : (
              <>
                <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
                <span>Disconnected</span>
              </>
            )}
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
            {error}
          </div>
        )}

        {/* Stats grid */}
        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-5">
            <p className="text-[13px] text-[#a1a1aa]">Namespaces</p>
            {loading ? (
              <Pulse className="mt-2 h-7 w-16" />
            ) : (
              <p className="mt-1 text-2xl font-semibold font-mono">
                {formatNumber(namespaceCount)}
              </p>
            )}
          </div>

          <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-5">
            <p className="text-[13px] text-[#a1a1aa]">Documents</p>
            {loading ? (
              <Pulse className="mt-2 h-7 w-20" />
            ) : (
              <p className="mt-1 text-2xl font-semibold font-mono">
                {formatNumber(totalDocs)}
              </p>
            )}
          </div>

          <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-5">
            <p className="text-[13px] text-[#a1a1aa]">Storage</p>
            {loading ? (
              <Pulse className="mt-2 h-7 w-24" />
            ) : (
              <p className="mt-1 text-2xl font-semibold font-mono">
                {formatBytes(totalStorage)}
              </p>
            )}
          </div>

          <div className="rounded-lg border border-[#27272a] bg-[#18181b] p-5">
            <p className="text-[13px] text-[#a1a1aa]">Server</p>
            {loading ? (
              <Pulse className="mt-2 h-7 w-28" />
            ) : (
              <p className="mt-1 text-2xl font-semibold font-mono">
                {version || "—"}
              </p>
            )}
          </div>
        </div>

        {/* Recent namespaces table */}
        <div className="rounded-lg border border-[#27272a] bg-[#18181b]">
          <div className="border-b border-[#27272a] px-5 py-4">
            <h2 className="text-sm font-medium text-[#fafafa]">
              Recent Namespaces
            </h2>
          </div>

          {loading ? (
            <div className="divide-y divide-[#27272a]">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 px-5 py-3.5">
                  <Pulse className="h-4 w-40" />
                  <Pulse className="h-4 w-16 ml-auto" />
                  <Pulse className="h-4 w-20" />
                  <Pulse className="h-4 w-16" />
                </div>
              ))}
            </div>
          ) : namespaces.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-[#71717a]">
              No namespaces found. Create one to get started.
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#27272a] text-left text-[13px] text-[#71717a]">
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium text-right">
                    Documents
                  </th>
                  <th className="px-5 py-3 font-medium text-right">Updated</th>
                  <th className="px-5 py-3 font-medium text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#27272a]">
                {namespaces.map((ns) => (
                  <tr key={ns.name} className="group">
                    <td className="px-5 py-3.5">
                      <Link
                        href={`/namespaces/${ns.name}`}
                        className="block font-mono text-sm text-[#fafafa] group-hover:text-blue-500 transition-colors"
                      >
                        {ns.name}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-sm text-[#a1a1aa]">
                      {ns.metadata
                        ? formatNumber(ns.metadata.approx_row_count)
                        : "—"}
                    </td>
                    <td className="px-5 py-3.5 text-right text-sm text-[#a1a1aa]">
                      {ns.metadata ? timeAgo(ns.metadata.updated_at) : "—"}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {ns.metadata ? (
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                            ns.metadata.index.status === "ready"
                              ? "bg-green-500/10 text-green-500"
                              : ns.metadata.index.status === "indexing"
                                ? "bg-yellow-500/10 text-yellow-500"
                                : "bg-[#27272a] text-[#a1a1aa]"
                          }`}
                        >
                          <span
                            className={`inline-block h-1.5 w-1.5 rounded-full ${
                              ns.metadata.index.status === "ready"
                                ? "bg-green-500"
                                : ns.metadata.index.status === "indexing"
                                  ? "bg-yellow-500"
                                  : "bg-[#71717a]"
                            }`}
                          />
                          {ns.metadata.index.status}
                        </span>
                      ) : (
                        <span className="text-sm text-[#71717a]">—</span>
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
}
